// rnt_validate [--table TABLE.csv] [--json OUT.json] (IN.root | --inputs LIST.txt) OUT.root
//
// Independent check of one converted file (shares no code with rnt_convert): compares every TTree of IN.root (or the concatenation of
// all files in LIST.txt, in order) that is importable with the RNTuple of the same name in OUT.root.
//   * same entry count
//   * RNTuple field set == expected branch set (all branches, or the KEEP rows of TABLE.csv "tree,branch,decision,..."),
//     anonymous "_collection*" fields ignored; missing and unexpected fields are listed
//   * type compatibility per field (TTree leaf type <-> RNTuple field type)
//   * value-level identity per kept field: count, NaN count, sum, sum of squares, min, max, an order-sensitive weighted sum, and for
//     jagged fields the total size and an order-sensitive sum of per-entry sizes (TTree read with TTreeReader, RNTuple with
//     RNTupleView; accumulation order is identical, so equality is exact)
// Trees with `edm::` branches and non-tree objects are expected to be absent. Extra sums needed for the QC cross-check
// (Runs.genEventCount, LuminosityBlocks.GenFilter_numEventsPassed/Total, Events entries) are taken from the RNTuple.
// Exit: 0 all checks passed, 1 at least one check failed, 3 wrong ROOT version, 64 usage.
#include <ROOT/RNTupleDescriptor.hxx>
#include <ROOT/RNTupleReader.hxx>
#include <ROOT/RNTupleView.hxx>
#include <ROOT/RVec.hxx>
#include <TBranch.h>
#include <TChain.h>
#include <TError.h>
#include <TFile.h>
#include <TKey.h>
#include <TLeaf.h>
#include <TROOT.h>
#include <TTree.h>
#include <TTreeReader.h>
#include <TTreeReaderArray.h>
#include <TTreeReaderValue.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace {
struct Acc {
  long double sum = 0, sumsq = 0, wsum = 0;
  long double mn = std::numeric_limits<long double>::infinity(), mx = -std::numeric_limits<long double>::infinity();
  long long n = 0, nan = 0, entries = 0, sizetot = 0;
  long double sizew = 0;
  template <class V> void add(V v) {
    long double x = static_cast<long double>(v);
    if (std::isnan(x)) { ++nan; return; }
    sum += x; sumsq += x * x; wsum += x * static_cast<long double>((n % 1009) + 1);
    if (x < mn) mn = x;
    if (x > mx) mx = x;
    ++n;
  }
  void addSize(size_t s) { sizetot += s; sizew += static_cast<long double>(s) * static_cast<long double>((entries % 97) + 1); }
  bool operator==(const Acc &o) const {
    return n == o.n && nan == o.nan && sum == o.sum && sumsq == o.sumsq && wsum == o.wsum && mn == o.mn && mx == o.mx &&
           entries == o.entries && sizetot == o.sizetot && sizew == o.sizew;
  }
  std::string Str() const {
    char b[256];
    std::snprintf(b, sizeof b, "n=%lld nan=%lld sum=%.10Lg min=%.6Lg max=%.6Lg sizetot=%lld", n, nan, sum, mn, mx, sizetot);
    return b;
  }
};

std::string Esc(const std::string &s) {
  std::string o;
  for (char c : s) { if (c == '"' || c == '\\') { o += '\\'; o += c; } else if (c == '\n') o += "\\n"; else o += c; }
  return o;
}

bool HasEdm(TTree *t) {
  for (auto *bb : *t->GetListOfBranches()) {
    auto *b = static_cast<TBranch *>(bb);
    if (b->GetClassName() && std::strstr(b->GetClassName(), "edm::")) return true;
  }
  return false;
}

// ---- TTree side: dispatch on the leaf type name --------------------------------------------------------------------
using Step = std::function<void()>;

template <class T> Step TreeScalar(TTreeReader &r, const std::string &name, Acc &acc) {
  auto rv = std::make_shared<TTreeReaderValue<T>>(r, name.c_str());
  return [rv, &acc] { acc.add(**rv); ++acc.entries; };
}
template <class T> Step TreeArray(TTreeReader &r, const std::string &name, Acc &acc) {
  auto ra = std::make_shared<TTreeReaderArray<T>>(r, name.c_str());
  return [ra, &acc] {
    acc.addSize(ra->GetSize());
    for (size_t i = 0; i < ra->GetSize(); ++i) acc.add((*ra)[i]);
    ++acc.entries;
  };
}
bool MakeTreeStep(const std::string &tn, bool jagged, TTreeReader &r, const std::string &name, Acc &acc, Step &out) {
#define TT(NAME, CT) if (tn == NAME) { out = jagged ? TreeArray<CT>(r, name, acc) : TreeScalar<CT>(r, name, acc); return true; }
  TT("Bool_t", bool) TT("Char_t", char) TT("UChar_t", unsigned char) TT("Short_t", short) TT("UShort_t", unsigned short)
  TT("Int_t", int) TT("UInt_t", unsigned int) TT("Long64_t", long long) TT("ULong64_t", unsigned long long)
  TT("Float_t", float) TT("Double_t", double)
#undef TT
  return false;
}

// ---- RNTuple side: dispatch on the field type name -------------------------------------------------------------------
template <class T> Step NtScalar(ROOT::RNTupleReader &r, const std::string &name, Acc &acc, long long n) {
  auto v = std::make_shared<ROOT::RNTupleView<T>>(r.GetView<T>(name));
  auto i = std::make_shared<long long>(0);
  return [v, i, &acc] { acc.add(static_cast<long double>((*v)(*i))); ++acc.entries; ++*i; };
}
template <class T> Step NtArray(ROOT::RNTupleReader &r, const std::string &name, Acc &acc, long long n) {
  auto v = std::make_shared<ROOT::RNTupleView<ROOT::RVec<T>>>(r.GetView<ROOT::RVec<T>>(name));
  auto i = std::make_shared<long long>(0);
  return [v, i, &acc] {
    auto x = (*v)(*i);
    acc.addSize(x.size());
    for (size_t k = 0; k < x.size(); ++k) acc.add(x[k]);
    ++acc.entries; ++*i;
  };
}
template <class S> Step NtCard(ROOT::RNTupleReader &r, const std::string &name, Acc &acc) {
  auto v = std::make_shared<ROOT::RNTupleView<ROOT::RNTupleCardinality<S>>>(r.GetView<ROOT::RNTupleCardinality<S>>(name));
  auto i = std::make_shared<long long>(0);
  return [v, i, &acc] { acc.add(static_cast<S>((*v)(*i))); ++acc.entries; ++*i; };
}
bool MakeNtStep(const std::string &ft, ROOT::RNTupleReader &r, const std::string &name, Acc &acc, long long n, Step &out, bool &jagged) {
  std::string t = ft;
  jagged = false;
  for (const char *pre : {"ROOT::VecOps::RVec<", "ROOT::RVec<", "std::vector<"})
    if (t.rfind(pre, 0) == 0 && t.back() == '>') { t = t.substr(std::strlen(pre), t.size() - std::strlen(pre) - 1); jagged = true; break; }
  if (t == "ROOT::RNTupleCardinality<std::uint32_t>") { out = NtCard<std::uint32_t>(r, name, acc); return true; }
  if (t == "ROOT::RNTupleCardinality<std::uint64_t>") { out = NtCard<std::uint64_t>(r, name, acc); return true; }
#define NT(NAME, CT) if (t == NAME) { out = jagged ? NtArray<CT>(r, name, acc, n) : NtScalar<CT>(r, name, acc, n); return true; }
  NT("bool", bool) NT("char", char) NT("std::int8_t", std::int8_t) NT("std::uint8_t", std::uint8_t) NT("std::int16_t", std::int16_t)
  NT("std::uint16_t", std::uint16_t) NT("std::int32_t", std::int32_t) NT("std::uint32_t", std::uint32_t)
  NT("std::int64_t", std::int64_t) NT("std::uint64_t", std::uint64_t) NT("float", float) NT("double", double)
#undef NT
  return false;
}

bool TypesCompatible(const std::string &tt, const std::string &ft) {
  std::string t = ft;
  for (const char *pre : {"ROOT::VecOps::RVec<", "ROOT::RVec<", "std::vector<"})
    if (t.rfind(pre, 0) == 0 && t.back() == '>') { t = t.substr(std::strlen(pre), t.size() - std::strlen(pre) - 1); break; }
  static const std::map<std::string, std::set<std::string>> ok = {
      {"Bool_t", {"bool"}}, {"Char_t", {"char", "std::int8_t"}}, {"UChar_t", {"std::uint8_t"}}, {"Short_t", {"std::int16_t"}},
      {"UShort_t", {"std::uint16_t"}}, {"Int_t", {"std::int32_t", "ROOT::RNTupleCardinality<std::uint32_t>", "ROOT::RNTupleCardinality<std::uint64_t>"}},
      {"UInt_t", {"std::uint32_t", "ROOT::RNTupleCardinality<std::uint32_t>", "ROOT::RNTupleCardinality<std::uint64_t>"}},
      {"Long64_t", {"std::int64_t"}}, {"ULong64_t", {"std::uint64_t"}}, {"Float_t", {"float"}}, {"Double_t", {"double"}}};
  auto it = ok.find(tt);
  return it != ok.end() && it->second.count(t);
}

struct TreeResult {
  std::string name;
  long long entries = 0, rntEntries = -1;
  int expected = 0, compared = 0;
  std::vector<std::string> missing, extra, mismatches, typeBad, unsupported;
  std::map<std::string, long double> rntSums, treeSums;
  std::string error;
  bool Ok() const { return error.empty() && entries == rntEntries && missing.empty() && extra.empty() && mismatches.empty() && typeBad.empty() && unsupported.empty(); }
};
} // namespace

int main(int argc, char **argv) {
  std::string table, jsonPath, listPath;
  std::vector<std::string> pos, inputs;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--table" && i + 1 < argc) table = argv[++i];
    else if (a == "--json" && i + 1 < argc) jsonPath = argv[++i];
    else if (a == "--inputs" && i + 1 < argc) listPath = argv[++i];
    else pos.push_back(a);
  }
  if (!listPath.empty()) {
    std::ifstream lf(listPath);
    std::string l;
    while (std::getline(lf, l)) if (!l.empty()) inputs.push_back(l);
    if (pos.size() != 1 || inputs.empty()) { std::fprintf(stderr, "usage: rnt_validate [opts] --inputs LIST OUT\n"); return 64; }
    pos.insert(pos.begin(), inputs[0]);
  } else {
    if (pos.size() != 2) { std::fprintf(stderr, "usage: rnt_validate [--table T.csv] [--json O.json] (IN | --inputs LIST) OUT\n"); return 64; }
    inputs.push_back(pos[0]);
  }
  const std::string rootVersion = gROOT->GetVersion();
  if (std::strlen(RNT_PINNED_ROOT) && rootVersion != RNT_PINNED_ROOT) {
    std::fprintf(stderr, "rnt_validate: built for ROOT %s but running with %s\n", RNT_PINNED_ROOT, rootVersion.c_str());
    return 3;
  }
  gROOT->SetBatch(true);
  gErrorIgnoreLevel = kError;
  auto t0 = std::chrono::steady_clock::now();
  std::map<std::string, std::map<std::string, bool>> keep;
  if (!table.empty()) {
    std::ifstream tf(table);
    std::string line;
    while (std::getline(tf, line)) {
      if (line.empty() || line[0] == '#') continue;
      std::stringstream ss(line);
      std::string t, b, d;
      std::getline(ss, t, ','); std::getline(ss, b, ','); std::getline(ss, d, ',');
      if (t == "tree") continue;
      keep[t][b] = (d == "KEEP");
    }
  }

  std::vector<TreeResult> results;
  std::vector<std::string> fileErrors;
  std::unique_ptr<TFile> fin(TFile::Open(pos[0].c_str()));
  std::unique_ptr<TFile> fout(TFile::Open(pos[1].c_str()));
  if (!fin || fin->IsZombie()) fileErrors.push_back("cannot open input");
  if (!fout || fout->IsZombie()) fileErrors.push_back("cannot open output");
  else if (fout->TestBit(TFile::kRecovered)) fileErrors.push_back("output file was recovered (not closed properly)");
  if (fileErrors.empty()) {
    for (auto *k : *fin->GetListOfKeys()) {
      auto *key = static_cast<TKey *>(k);
      if (std::string(key->GetClassName()) != "TTree") continue;
      std::unique_ptr<TTree> first(static_cast<TTree *>(key->ReadObj()));
      if (HasEdm(first.get())) continue;   // not importable, expected to be absent
      TreeResult res;
      res.name = first->GetName();
      auto chain = std::make_unique<TChain>(res.name.c_str());
      for (const auto &f : inputs) chain->Add(f.c_str());
      TTree *tree = chain.get();
      if (chain->LoadTree(0) < 0) { res.error = "cannot load the input chain"; results.push_back(res); continue; }
      res.entries = chain->GetEntries();
      try {
        auto reader = ROOT::RNTupleReader::Open(res.name, pos[1]);
        res.rntEntries = (long long)reader->GetNEntries();
        // expected branch set
        std::map<std::string, std::string> leafType;   // branch -> TTree type
        std::map<std::string, bool> isJagged;
        auto it = keep.find(res.name);
        std::set<std::string> expected;
        for (auto *bb : *tree->GetListOfBranches()) {
          auto *b = static_cast<TBranch *>(bb);
          std::string bn = b->GetName();
          bool kept = true;
          if (it != keep.end()) { auto kb = it->second.find(bn); kept = (kb == it->second.end()) ? true : kb->second; }
          if (!kept) continue;
          expected.insert(bn);
          auto *leaf = static_cast<TLeaf *>(b->GetListOfLeaves()->At(0));
          leafType[bn] = b->GetListOfLeaves()->GetEntries() == 1 ? leaf->GetTypeName() : "leaflist";
          isJagged[bn] = leaf->GetLeafCount() != nullptr || leaf->GetLen() > 1;
        }
        res.expected = (int)expected.size();
        std::map<std::string, std::string> fieldType;
        for (const auto &f : reader->GetDescriptor().GetTopLevelFields()) {
          std::string fn = f.GetFieldName();
          if (fn.rfind("_collection", 0) == 0) continue;
          fieldType[fn] = f.GetTypeName();
        }
        for (const auto &e : expected) if (!fieldType.count(e)) res.missing.push_back(e);
        for (const auto &f : fieldType) if (!expected.count(f.first)) res.extra.push_back(f.first);
        // values
        TTreeReader tr(tree);
        std::map<std::string, Acc> tacc, nacc;
        std::vector<Step> tsteps, nsteps;
        std::vector<std::string> names;
        for (const auto &bn : expected) {
          if (!fieldType.count(bn)) continue;
          if (!TypesCompatible(leafType[bn], fieldType[bn])) { res.typeBad.push_back(bn + ":" + leafType[bn] + "->" + fieldType[bn]); continue; }
          Step ts, ns;
          bool njag = false;
          if (!MakeTreeStep(leafType[bn], isJagged[bn], tr, bn, tacc[bn], ts) || !MakeNtStep(fieldType[bn], *reader, bn, nacc[bn], res.rntEntries, ns, njag)) {
            res.unsupported.push_back(bn + ":" + leafType[bn] + "/" + fieldType[bn]);
            continue;
          }
          if (njag != isJagged[bn]) { res.typeBad.push_back(bn + ": scalar/array kind differs"); continue; }
          tsteps.push_back(ts); nsteps.push_back(ns); names.push_back(bn);
        }
        if (res.entries == res.rntEntries) {
          while (tr.Next()) for (auto &s : tsteps) s();
          for (long long i = 0; i < res.rntEntries; ++i) for (auto &s : nsteps) s();
          for (const auto &bn : names) {
            ++res.compared;
            if (!(tacc[bn] == nacc[bn])) {
              if (res.mismatches.size() < 20) res.mismatches.push_back(bn + " TTree[" + tacc[bn].Str() + "] RNTuple[" + nacc[bn].Str() + "]");
              else if (res.mismatches.size() == 20) res.mismatches.push_back("...");
            }
          }
          for (const char *want : {"genEventCount", "GenFilter_numEventsPassed", "GenFilter_numEventsTotal"})
            if (nacc.count(want)) { res.rntSums[want] = nacc[want].sum; res.treeSums[want] = tacc[want].sum; }
        }
      } catch (const std::exception &e) {
        res.error = e.what();
      }
      results.push_back(res);
    }
  }
  bool ok = fileErrors.empty() && !results.empty();
  for (auto &r : results) ok = ok && r.Ok();
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

  auto arr = [](const std::vector<std::string> &v) {
    std::string s = "[";
    for (size_t i = 0; i < v.size(); ++i) s += (i ? ",\"" : "\"") + Esc(v[i]) + "\"";
    return s + "]";
  };
  std::ostringstream js;
  js << "{\"input\":\"" << Esc(pos[0]) << "\",\"output\":\"" << Esc(pos[1]) << "\",\"ok\":" << (ok ? "true" : "false")
     << ",\"root_version\":\"" << rootVersion << "\",\"seconds\":" << secs << ",\"file_errors\":" << arr(fileErrors) << ",\"trees\":[";
  for (size_t i = 0; i < results.size(); ++i) {
    auto &r = results[i];
    js << (i ? "," : "") << "{\"name\":\"" << Esc(r.name) << "\",\"ok\":" << (r.Ok() ? "true" : "false") << ",\"entries\":" << r.entries
       << ",\"rntuple_entries\":" << r.rntEntries << ",\"expected_fields\":" << r.expected << ",\"fields_compared\":" << r.compared
       << ",\"missing\":" << arr(r.missing) << ",\"extra\":" << arr(r.extra) << ",\"type_mismatch\":" << arr(r.typeBad)
       << ",\"unsupported\":" << arr(r.unsupported) << ",\"value_mismatch\":" << arr(r.mismatches) << ",\"error\":\"" << Esc(r.error) << "\"";
    js << ",\"rntuple_sums\":{";
    bool first = true;
    for (auto &kv : r.rntSums) { js << (first ? "" : ",") << "\"" << kv.first << "\":" << (double)kv.second; first = false; }
    js << "}}";
  }
  js << "]}\n";
  if (!jsonPath.empty()) std::ofstream(jsonPath) << js.str(); else std::fputs(js.str().c_str(), stdout);
  return ok ? 0 : 1;
}
