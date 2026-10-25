---
name: qc-check-rootfile
description: Corruption definition and per-file checker for custom NanoAODv15 files (8 electron custom branches, GenFilter counters). Use to check a few files locally.
---
`source scripts/env.sh; python3 python/check_file.py OUT.json FILE...` writes one JSON record per file. Each file is checked in its own subprocess with a 300 s timeout (`QC_FILE_TIMEOUT`) because reads of unavailable dCache files hang in D state.
Corrupted (any one): `zombie`, `recovered`, `size0` (<1000 B), `no_tree` (Events/Runs/LuminosityBlocks missing), `zero_events`, `read_error` (GetEntry<0), `missing_branch` (any of Electron_superclusterPhi, _superclusterEnergy, _DeltaEtaInSC, _DeltaPhiInSC, _DeltaPhiInSeed, _ecalPFClusIso, _hcalPFClusIso, _dr03HcalTowerSumEt), `check_exception`, `io_timeout`.
`incomplete` is derived in `aggregate.py`: readable file whose Events entries < sum LuminosityBlocks `GenFilter_numEventsPassed` (events silently lost). Warnings only: `count_mismatch`, `no_genfilter_branches`.
Filter efficiency = sum(GenFilter_numEventsPassed) / sum(GenFilter_numEventsTotal) over clean files.
