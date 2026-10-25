// rnt_readbench FILE.root [TREE=Events] [REPS=3]  ->  one JSON line with the best-of-REPS read times (seconds, file in page cache,
// so the numbers are dominated by decompression + deserialization):
//   full_s   : read every entry with every field/branch
//   subset_s : read 10 typical analysis fields only (Electron/Muon/Jet pt+eta, nElectron, HLT_IsoMu24, event, MET_pt)
// Works for a TTree file (GetEntry) and for an RNTuple file (RNTupleReader). Used to judge compression settings.
#include <ROOT/RNTupleReader.hxx>
#include <ROOT/RNTupleView.hxx>
#include <ROOT/RVec.hxx>
#include <TError.h>
#include <TFile.h>
#include <TKey.h>
#include <TROOT.h>
#include <TTree.h>

#include <chrono>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

using clk = std::chrono::steady_clock;
static double Since(clk::time_point t) { return std::chrono::duration<double>(clk::now() - t).count(); }

int main(int argc, char **argv) {
  if (argc < 2) { std::fprintf(stderr, "usage: rnt_readbench FILE [TREE] [REPS]\n"); return 64; }
  const std::string file = argv[1], name = argc > 2 ? argv[2] : "Events";
  const int reps = argc > 3 ? std::atoi(argv[3]) : 3;
  gROOT->SetBatch(true);
  gErrorIgnoreLevel = kError;
  bool isTree = false;
  {
    std::unique_ptr<TFile> f(TFile::Open(file.c_str()));
    if (!f || f->IsZombie()) { std::fprintf(stderr, "cannot open\n"); return 1; }
    auto *k = f->GetKey(name.c_str());
    isTree = k && std::string(k->GetClassName()) == "TTree";
  }
  double best_full = 1e99, best_sub = 1e99;
  long long entries = 0;
  double chk = 0;
  for (int r = 0; r < reps; ++r) {
    if (isTree) {
      std::unique_ptr<TFile> f(TFile::Open(file.c_str()));
      auto *t = static_cast<TTree *>(f->Get(name.c_str()));
      entries = t->GetEntries();
      auto t0 = clk::now();
      for (long long i = 0; i < entries; ++i) t->GetEntry(i);
      best_full = std::min(best_full, Since(t0));
      t->SetBranchStatus("*", 0);
      static const char *keep[] = {"Electron_pt", "Electron_eta", "Muon_pt", "Muon_eta", "Jet_pt", "Jet_eta", "nElectron", "HLT_IsoMu24", "event", "PuppiMET_pt"};
      for (auto *b : keep) t->SetBranchStatus(b, 1);
      t0 = clk::now();
      for (long long i = 0; i < entries; ++i) t->GetEntry(i);
      best_sub = std::min(best_sub, Since(t0));
    } else {
      auto reader = ROOT::RNTupleReader::Open(name, file);
      entries = (long long)reader->GetNEntries();
      auto t0 = clk::now();
      for (long long i = 0; i < entries; ++i) reader->LoadEntry(i);
      best_full = std::min(best_full, Since(t0));
      auto r2 = ROOT::RNTupleReader::Open(name, file);
      auto ept = r2->GetView<ROOT::RVec<float>>("Electron_pt"), eeta = r2->GetView<ROOT::RVec<float>>("Electron_eta");
      auto mpt = r2->GetView<ROOT::RVec<float>>("Muon_pt"), meta = r2->GetView<ROOT::RVec<float>>("Muon_eta");
      auto jpt = r2->GetView<ROOT::RVec<float>>("Jet_pt"), jeta = r2->GetView<ROOT::RVec<float>>("Jet_eta");
      auto ne = r2->GetView<ROOT::RNTupleCardinality<std::uint32_t>>("nElectron");
      auto trg = r2->GetView<bool>("HLT_IsoMu24");
      auto ev = r2->GetView<std::uint64_t>("event");
      auto met = r2->GetView<float>("PuppiMET_pt");
      t0 = clk::now();
      for (long long i = 0; i < entries; ++i) {
        chk += ept(i).size() + eeta(i).size() + mpt(i).size() + meta(i).size() + jpt(i).size() + jeta(i).size() + (std::uint32_t)ne(i) + trg(i) + (ev(i) & 1) + met(i);
      }
      best_sub = std::min(best_sub, Since(t0));
    }
  }
  std::printf("{\"file\":\"%s\",\"kind\":\"%s\",\"entries\":%lld,\"full_s\":%.3f,\"subset_s\":%.3f,\"chk\":%g}\n", file.c_str(), isTree ? "TTree" : "RNTuple", entries, best_full, best_sub, chk);
  return 0;
}
