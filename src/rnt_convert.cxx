// rnt_convert [--branches TABLE.csv] [--json OUT.json] [--compression N] (IN.root | --inputs LIST.txt) OUT.root
//
// With --inputs LIST.txt (one path per line) the trees of several NanoAOD files are concatenated, in list order, into ONE output
// (Events, Runs, LuminosityBlocks get one entry per input resp. all events); all inputs must have the same trees and branches.
// Converts every TTree of a NanoAOD file into an RNTuple of the same name inside ONE output file, using ROOT's stock
// RNTupleImporter. Branch selection: TABLE.csv has lines "tree,branch,KEEP|DROP" (resolved from config/rntuple_branches.conf
// by python/rnt_branches.py); trees without rows are converted completely, a branch missing from the table of a tree that has
// rows is an error (schema drift). Dropped branches are removed by cloning only the kept branches into a temporary file first.
// Trees with `edm::` branches (ParameterSets) and non-tree objects (tag) cannot be imported and are reported as not converted.
// Output is written to OUT.root.part and renamed atomically; an existing OUT.root is never overwritten.
// Exit codes: 0 ok, 1 error (partial output removed), 3 wrong ROOT version, 64 usage.
#include <ROOT/RNTupleImporter.hxx>
#include <ROOT/RNTupleReader.hxx>
#include <ROOT/RNTupleWriteOptions.hxx>
#include <TBranch.h>
#include <TFile.h>
#include <TKey.h>
#include <TError.h>
#include <TROOT.h>
#include <TTree.h>

#include <sys/stat.h>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include <unistd.h>

namespace {
struct TreeRec {
  std::string name, status, reason;
  long long entries = 0, rntEntries = -1;
  int nIn = 0, nKept = 0, nDropped = 0;
};

std::string Esc(const std::string &s) {
  std::string o;
  for (char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += c; }
    else if (c == '\n') o += "\\n";
    else o += c;
  }
  return o;
}

long long FileSize(const std::string &p) {
  struct stat st;
  return stat(p.c_str(), &st) == 0 ? (long long)st.st_size : -1;
}

bool HasEdm(TTree *t) {
  for (auto *bb : *t->GetListOfBranches()) {
    auto *b = static_cast<TBranch *>(bb);
    if (b->GetClassName() && std::strstr(b->GetClassName(), "edm::")) return true;
  }
  return false;
}
} // namespace

int main(int argc, char **argv) {
  std::string table, jsonPath, listPath, out;
  std::vector<std::string> inputs;
  int compression = -1;
  std::vector<std::string> pos;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--branches" && i + 1 < argc) table = argv[++i];
    else if (a == "--json" && i + 1 < argc) jsonPath = argv[++i];
    else if (a == "--compression" && i + 1 < argc) compression = std::atoi(argv[++i]);
    else if (a == "--inputs" && i + 1 < argc) listPath = argv[++i];
    else pos.push_back(a);
  }
  if (!listPath.empty()) {
    if (pos.size() != 1) { std::fprintf(stderr, "usage: rnt_convert [opts] --inputs LIST OUT\n"); return 64; }
    std::ifstream lf(listPath);
    std::string l;
    while (std::getline(lf, l)) if (!l.empty()) inputs.push_back(l);
    out = pos[0];
  } else {
    if (pos.size() != 2) { std::fprintf(stderr, "usage: rnt_convert [--branches T.csv] [--json O.json] [--compression N] (IN | --inputs LIST) OUT\n"); return 64; }
    inputs.push_back(pos[0]);
    out = pos[1];
  }
  if (inputs.empty()) { std::fprintf(stderr, "no inputs\n"); return 64; }
  const std::string in = inputs[0];
  const std::string rootVersion = gROOT->GetVersion();
  if (std::strlen(RNT_PINNED_ROOT) && rootVersion != RNT_PINNED_ROOT) {
    std::fprintf(stderr, "rnt_convert: built for ROOT %s but running with %s\n", RNT_PINNED_ROOT, rootVersion.c_str());
    return 3;
  }
  gROOT->SetBatch(true);
  gErrorIgnoreLevel = kError;   // silence "no dictionary for edm::..." warnings
  if (FileSize(out) >= 0) { std::fprintf(stderr, "rnt_convert: refusing to overwrite %s\n", out.c_str()); return 1; }
  const std::string part = out + ".part";
  std::remove(part.c_str());

  // KEEP/DROP table
  std::map<std::string, std::map<std::string, bool>> keep;   // tree -> branch -> keep
  if (!table.empty()) {
    std::ifstream tf(table);
    std::string line;
    while (std::getline(tf, line)) {
      if (line.empty() || line[0] == '#') continue;
      std::stringstream ss(line);
      std::string t, b, d;
      std::getline(ss, t, ','); std::getline(ss, b, ','); std::getline(ss, d, ',');
      if (t == "tree") continue;   // header
      keep[t][b] = (d == "KEEP");
    }
  }

  auto t0 = std::chrono::steady_clock::now();
  std::vector<TreeRec> trees;
  std::vector<std::pair<std::string, std::string>> notTrees;   // name, class
  std::string error;
  std::unique_ptr<TFile> fin(TFile::Open(in.c_str()));
  if (!fin || fin->IsZombie()) { error = "cannot open input " + in; }
  const std::string tmpClone = part + ".clone.root";
  if (error.empty()) {
    for (auto *k : *fin->GetListOfKeys()) {
      auto *key = static_cast<TKey *>(k);
      std::string cls = key->GetClassName();
      if (cls != "TTree") { notTrees.emplace_back(key->GetName(), cls); continue; }
      std::unique_ptr<TTree> tree(static_cast<TTree *>(key->ReadObj()));
      TreeRec rec;
      rec.name = tree->GetName();
      rec.entries = tree->GetEntries();
      rec.nIn = tree->GetListOfBranches()->GetEntries();
      if (HasEdm(tree.get())) { rec.status = "skipped"; rec.reason = "edm branches (not importable)"; trees.push_back(rec); continue; }
      try {
        std::unique_ptr<ROOT::Experimental::RNTupleImporter> imp;
        std::unique_ptr<TFile> fclone;
        TTree *clone = nullptr;
        auto it = keep.find(rec.name);
        const bool useClone = (it != keep.end()) || inputs.size() > 1;
        if (!useClone) {                              // single input, no selection: import the tree directly
          rec.nKept = rec.nIn;
          imp = ROOT::Experimental::RNTupleImporter::Create(tree.get(), part);
        } else {
          fclone.reset(TFile::Open(tmpClone.c_str(), "RECREATE"));
          rec.entries = 0;
          for (size_t fi = 0; fi < inputs.size(); ++fi) {
            std::unique_ptr<TFile> fnext;                 // later inputs: tree lives as long as its file (scope of this iteration)
            TTree *t = nullptr;
            if (fi == 0) t = tree.get();              // first input is already open as `fin`
            else {
              fnext.reset(TFile::Open(inputs[fi].c_str()));
              if (!fnext || fnext->IsZombie()) throw std::runtime_error("cannot open input " + inputs[fi]);
              t = dynamic_cast<TTree *>(fnext->Get(rec.name.c_str()));
              if (!t) throw std::runtime_error("tree " + rec.name + " missing in " + inputs[fi]);
            }
            if (t->GetListOfBranches()->GetEntries() != rec.nIn) throw std::runtime_error("different branch count in " + inputs[fi] + " for tree " + rec.name);
            int kept = 0, dropped = 0;
            if (it != keep.end()) {
              t->SetBranchStatus("*", 0);
              for (auto *bb : *t->GetListOfBranches()) {
                std::string bn = static_cast<TBranch *>(bb)->GetName();
                auto kb = it->second.find(bn);
                if (kb == it->second.end()) throw std::runtime_error("schema drift: branch '" + bn + "' of tree " + rec.name + " not in the KEEP/DROP table");
                if (kb->second) { t->SetBranchStatus(bn.c_str(), 1); ++kept; } else ++dropped;
              }
            } else kept = rec.nIn;
            if (fi == 0) { rec.nKept = kept; rec.nDropped = dropped; clone = t->CloneTree(0); clone->SetDirectory(fclone.get()); }
            else if (kept != rec.nKept) throw std::runtime_error("different kept-branch count in " + inputs[fi]);
            rec.entries += t->GetEntries();
            if (clone->CopyEntries(t, -1, "fast") < 0 && clone->CopyEntries(t, -1) < 0) throw std::runtime_error("CopyEntries failed for " + inputs[fi]);
          }
          fclone->cd();
          clone->Write();
          if (clone->GetEntries() != rec.entries) throw std::runtime_error("merged tree entry count mismatch in " + rec.name);
          imp = ROOT::Experimental::RNTupleImporter::Create(clone, part);
        }
        imp->SetConvertDotsInBranchNames(true);
        imp->SetIsQuiet(true);
        if (compression >= 0) { auto o = imp->GetWriteOptions(); o.SetCompression(compression); imp->SetWriteOptions(o); }
        imp->Import();
        rec.status = "converted";
        imp.reset(); fclone.reset();
        std::remove(tmpClone.c_str());
      } catch (const std::exception &e) {
        rec.status = "failed"; rec.reason = e.what();
        error = "tree " + rec.name + ": " + e.what();
      }
      trees.push_back(rec);
      if (!error.empty()) break;
    }
  }
  // self-check: entry counts of what was written
  if (error.empty()) {
    for (auto &r : trees) {
      if (r.status != "converted") continue;
      try {
        auto rd = ROOT::RNTupleReader::Open(r.name, part);
        r.rntEntries = (long long)rd->GetNEntries();
        if (r.rntEntries != r.entries) { error = "entry count mismatch in " + r.name; r.status = "failed"; r.reason = error; }
      } catch (const std::exception &e) { error = std::string("cannot reopen ") + r.name + ": " + e.what(); r.status = "failed"; r.reason = error; }
    }
  }
  std::remove(tmpClone.c_str());
  bool ok = error.empty();
  bool anyConv = false;
  for (auto &r : trees) anyConv |= (r.status == "converted");
  if (ok && !anyConv) { ok = false; error = "no tree could be converted"; }
  if (ok) { if (std::rename(part.c_str(), out.c_str()) != 0) { ok = false; error = "rename of .part failed"; } }
  else std::remove(part.c_str());
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

  std::ostringstream js;
  js << "{\"input\":\"" << Esc(in) << "\",\"n_inputs\":" << inputs.size() << ",\"output\":\"" << Esc(out) << "\",\"ok\":" << (ok ? "true" : "false")
     << ",\"error\":\"" << Esc(error) << "\",\"root_version\":\"" << rootVersion << "\",\"in_bytes\":" << FileSize(in)
     << ",\"in_bytes_all\":" << [&]{ long long t = 0; for (auto &f : inputs) t += std::max(0LL, FileSize(f)); return t; }() << ",\"out_bytes\":" << (ok ? FileSize(out) : -1) << ",\"seconds\":" << secs << ",\"compression\":" << compression
     << ",\"trees\":[";
  for (size_t i = 0; i < trees.size(); ++i) {
    auto &r = trees[i];
    js << (i ? "," : "") << "{\"name\":\"" << Esc(r.name) << "\",\"status\":\"" << r.status << "\",\"reason\":\"" << Esc(r.reason)
       << "\",\"entries\":" << r.entries << ",\"rntuple_entries\":" << r.rntEntries << ",\"branches_in\":" << r.nIn
       << ",\"kept\":" << r.nKept << ",\"dropped\":" << r.nDropped << "}";
  }
  js << "],\"not_trees\":[";
  for (size_t i = 0; i < notTrees.size(); ++i)
    js << (i ? "," : "") << "{\"name\":\"" << Esc(notTrees[i].first) << "\",\"class\":\"" << Esc(notTrees[i].second) << "\"}";
  js << "]}\n";
  if (!jsonPath.empty()) { std::ofstream(jsonPath) << js.str(); } else std::fputs(js.str().c_str(), stdout);
  if (!ok) std::fprintf(stderr, "rnt_convert: FAILED: %s\n", error.c_str());
  return ok ? 0 : 1;
}
