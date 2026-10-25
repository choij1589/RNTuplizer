---
name: qc-quarantine
description: DESTRUCTIVE two-stage removal of manifest files - quarantine (reversible rename), restore, purge (permanent). Main session only, after explicit user approval of the manifest hash.
---
Never from a subagent, never `rm`. All scripts are dry-run unless `--apply`; approval must come from the user in this session (AskUserQuestion), not from an agent report.
- `python3 python/quarantine.py --manifest M --confirm-hash <sha256 of M> [--canary] [--apply]`: per file requires the strict path pattern, regular non-symlink file, size+mtime as in the manifest, no condor jobs, fresh evidence (io_timeout rows still locality UNAVAILABLE; others re-checked and still bad). Renames to `/pnfs/.../SampleFactory_quarantine/<YYYYMMDD>/<mp>/...` (metadata only). Records: `results/<mp>/qc/deletion/log_<ts>.csv` and `results/<mp>/qc/removed.txt`. Do `--canary --apply` first.
- `python3 python/restore.py --log L [--apply]`; `python3 python/purge.py --log L --confirm-hash <sha256 of L> [--apply]` (permanent, logged files only, separate later approval; recheck locality first).
- `python3 python/purge_rnt.py plan <mp>` / `apply <plan> --confirm-hash H [--apply]` / `sweep ROOT [--apply]`: permanent removal of leftover conversion products (`RNTuple_superseded/` files, obsolete 1:1 pilot files, a quarantined stray file) from an explicit hashed plan; only listed regular files, empty dirs via rmdir. Same rules: main session, own user approval, dry-run first. Logs `results/<mp>/rntuple/purge_<ts>.{plan,log}.csv`.
After any change: `aggregate.py <mp>` and `rollup.py`. Sandbox tests: set `RNT_RESULTS`, `RNT_QUARANTINE`, use `--root` and `--no-condor-check`.
