---
name: rnt-validate
description: Stage 3 - independent validation of every converted output of one masspoint (against the chain of its source files) (structure + values) and cross-check against QC.
---
`bash scripts/rnt_run_mp.sh <mp> validate [--only-failed]` -> `python/rnt_make_jobs.py --validate` (3 outputs per job; inputs of each output taken from the latest manifest) -> condor (`scripts/rnt_validate.sh` -> `bin/rnt_validate --inputs <sources>`) -> `python/rnt_validate_report.py` -> `results/<mp>/rntuple/{validation,summary}.csv` -> gate C.
Per output: RNTuple opens and is not recovered; entries equal per converted tree; RNTuple field set == resolved KEPT branch set (dropped absent, 8 custom electron fields included); type compatibility; value identity per field (count, NaN, sum, sum of squares, min, max, order-sensitive checksums, jagged sizes). Cross-checks per masspoint: sum Events entries == QC n_events_clean, sum Runs.genEventCount == QC, filter efficiency from the RNTuple LuminosityBlocks == QC. Failures are listed and re-runnable with `--only-failed`; outputs are never auto-deleted.
