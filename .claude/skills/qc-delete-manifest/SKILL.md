---
name: qc-delete-manifest
description: Build the deletion manifest (+sha256 and healthy-events guard) of one masspoint's corrupted files. Read-only; never reads file data and never moves anything.
---
`python3 python/make_manifest.py <mp> [--min-healthy 300000]` -> `results/<mp>/qc/deletion/manifest_<ts>.csv` (+`.sha256`): path, realpath, masspoint, reason, size_bytes, mtime, locality, healthy_events_after. Exit 3 = healthy events would fall below the guard (stop), 4 = nothing corrupted. Files in `qc/exclude.txt` are never in a manifest.
