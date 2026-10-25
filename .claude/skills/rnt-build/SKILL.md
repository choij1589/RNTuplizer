---
name: rnt-build
description: Build the C++ tools (rnt_convert, rnt_inventory, rnt_validate, rnt_readbench) with the pinned LCG view into bin/.
---
`bash scripts/rnt_build.sh` (CMakeLists.txt + src/*.cxx; cmake with `-DRNT_PINNED_ROOT=<ROOT_VERSION>`; the binaries refuse to run on another ROOT). Writes `bin/BUILD_INFO` (date, view, ROOT, compiler, repo commit, sha256 of the binaries). `bin/` and `build/` are gitignored.
`rnt_convert [--branches TABLE] [--json OUT] [--compression N] (IN | --inputs LIST) OUT`: every importable TTree (of IN, or concatenated over all files of LIST in order) -> RNTuple of the same name in one output file (RNTupleImporter, default zstd), `.part` + atomic rename, never overwrites. `rnt_inventory IN`: CSV of trees/branches/types/compressed bytes. `rnt_validate [--table TABLE] [--json OUT] (IN | --inputs LIST) OUT`: independent comparison of the TTree chain and the RNTuple (TTreeReader / RNTupleView, separate type dispatch; not RDataFrame, whose JIT needs ~1 min per 300 columns).
Not importable (reported, not errors): trees with `edm::` branches (MetaData, ParameterSets) and non-tree objects (tag).
`rnt_readbench FILE [TREE] [REPS]`: best-of-N read time of a TTree or RNTuple file, full width and a 10-field analysis subset (used to compare compression settings; file in page cache, so it measures decompression).
