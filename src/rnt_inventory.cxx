// rnt_inventory IN.root  ->  CSV on stdout: kind,tree,branch,type,entries,zip_bytes,tot_bytes
// Lists every TTree branch (type, compressed/total bytes) and every non-tree key of a ROOT file. Read-only.
#include <TBranch.h>
#include <TFile.h>
#include <TKey.h>
#include <TLeaf.h>
#include <TError.h>
#include <TROOT.h>
#include <TTree.h>

#include <cstdio>
#include <memory>
#include <string>

static std::string TypeOf(TBranch *b) {
  auto *leaves = b->GetListOfLeaves();
  if (!leaves || leaves->GetEntries() == 0) return "?";
  if (leaves->GetEntries() > 1) return std::string("leaflist:") + b->GetClassName();
  auto *l = static_cast<TLeaf *>(leaves->At(0));
  std::string t = l->GetTypeName();
  if (l->GetLeafCount()) t += "[" + std::string(l->GetLeafCount()->GetName()) + "]";
  else if (l->GetLen() > 1) t += "[" + std::to_string(l->GetLen()) + "]";
  if (b->GetClassName() && *b->GetClassName()) t = std::string(b->GetClassName());
  for (auto &c : t) if (c == ',') c = ';';   // keep the CSV well-formed (template arguments)
  return t;
}

int main(int argc, char **argv) {
  if (argc != 2) { std::fprintf(stderr, "usage: rnt_inventory IN.root\n"); return 64; }
  gROOT->SetBatch(true);
  gErrorIgnoreLevel = kError;   // silence "no dictionary for edm::..." warnings
  std::unique_ptr<TFile> f(TFile::Open(argv[1]));
  if (!f || f->IsZombie()) { std::fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
  std::printf("kind,tree,branch,type,entries,zip_bytes,tot_bytes\n");
  for (auto *k : *f->GetListOfKeys()) {
    auto *key = static_cast<TKey *>(k);
    std::string cls = key->GetClassName();
    if (cls == "TTree") {
      std::unique_ptr<TTree> t(static_cast<TTree *>(key->ReadObj()));
      for (auto *bb : *t->GetListOfBranches()) {
        auto *b = static_cast<TBranch *>(bb);
        std::printf("branch,%s,%s,%s,%lld,%lld,%lld\n", t->GetName(), b->GetName(), TypeOf(b).c_str(),
                    (long long)t->GetEntries(), (long long)b->GetZipBytes("*"), (long long)b->GetTotBytes("*"));
      }
    } else {
      std::printf("object,%s,,%s,,,\n", key->GetName(), cls.c_str());
    }
  }
  return 0;
}
