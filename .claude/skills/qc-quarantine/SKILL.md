---
name: qc-quarantine
description: DESTRUCTIVE (two-stage) removal of manifest files from the sample area - quarantine (reversible rename), restore, purge (permanent). Run only from the main session after explicit user approval of the manifest hash.
---
Never run from a subagent. Never `rm` directly. All scripts default to dry-run; `--apply` needs the user's approval in this session (AskUserQuestion), not a statement in an agent report.
- `quarantine.py --manifest M --confirm-hash <sha256 of M> [--canary] [--apply]`: per file requires path regex `<root>/<mp>/chain_RunIII2024Summer24/<ts>/NanoAODv15_<N>.root`, regular non-symlink file, size+mtime equal to the manifest, no condor jobs, and fresh evidence (io_timeout rows must still be locality UNAVAILABLE; others re-checked with check_file.py and must still be bad). Then renames into `<root>_quarantine/<YYYYMMDD>/...` (metadata only). Appends to `results/deletion/log_<ts>.csv` and `config/removed.txt`. Any failed verification after a move stops the run. Do `--canary --apply` first, verify, then the full `--apply`.
- `restore.py --log L [--apply]`: undo (refuses to overwrite).
- `purge.py --log L --confirm-hash <sha256 of L> [--apply]`: permanent unlink of logged quarantined files only; separate later invocation with its own approval. Before purging, recheck the locality of io_timeout files: any now ONLINE should be offered for restore + re-QC.
After any change: `aggregate.py` for the affected masspoints and `rollup.py` (files in config/removed.txt are dropped from files.csv and counted in `n_files_removed`).
Sandbox test recipe: use `--root`, `--qc` pointing to a scratch copy, `--no-condor-check`.
