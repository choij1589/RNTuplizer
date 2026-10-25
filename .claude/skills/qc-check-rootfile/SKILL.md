---
name: qc-check-rootfile
description: Corruption definition and checker for custom NanoAODv15 files (8 electron custom branches, GenFilter counters in LuminosityBlocks). Use to check one or a few files locally.
---
`python3 scripts/check_file.py OUT.json FILE...` (after `qc-env`). Writes one JSON record per file.

Corrupted (any reason => corrupted=1): `zombie` (cannot open / truncated, footer missing), `recovered`, `size0` (<1000 bytes), `no_tree` (Events/Runs/LuminosityBlocks missing), `zero_events`, `read_error` (GetEntry<0 on Events/Runs/LuminosityBlocks, i.e. bad baskets), `missing_branch` (any of Electron_superclusterPhi, _superclusterEnergy, _DeltaEtaInSC, _DeltaPhiInSC, _DeltaPhiInSeed, _ecalPFClusIso, _hcalPFClusIso, _dr03HcalTowerSumEt), `check_exception`, `io_timeout` (no result within QC_FILE_TIMEOUT=300 s per file: storage read hangs in D state; seen on /pnfs files that even `cat` cannot read. Each file is checked in its own subprocess so one hanging file cannot block a chunk; n_events is unknown=0).
`incomplete` is added at aggregation (qc-report), not in check_file.py: file is readable but Events entries < sum GenFilter_numEventsPassed (events silently lost; events_missing = difference). Found in the MA-65 pilot (210230/NanoAODv15_21.root: 1350 vs 3514).
Warnings (not corruption): `count_mismatch` (Events entries != sum Runs.genEventCount), `no_genfilter_branches`.
Fields: n_events (Events entries; 0 if unreadable), n_events_readable, gen_passed/gen_total (sum of LuminosityBlocks GenFilter_numEventsPassed/Total).
Note: Runs.genEventCount is post-filter; the generator filter efficiency comes from the LuminosityBlocks GenFilter_* branches.
