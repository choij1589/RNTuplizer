---
name: results-migration
description: One-time reorganization of old results (results/deletion, run_all.log, .work, global config lists) into results/<mp>/qc/. Already applied; kept for reference and tests.
---
`python3 python/migrate_results.py` (dry-run) / `--apply`. Moves per masspoint: files.csv, summary.csv -> `qc/`; `.work/*` -> `qc/runs/legacy_20261025/`; merges chunk JSON into `qc/records.json`; splits `config/{exclude,removed}.txt`, `results/deletion/*` and global driver logs per masspoint (with `.origin` files holding the original sha256); writes `migration.json` (sha256 of everything moved). Refuses if `qc/` already exists. Verified by re-running `aggregate.py` for all masspoints and diffing against the pre-migration CSVs (must be identical).
