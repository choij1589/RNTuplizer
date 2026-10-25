---
name: qc-delete-manifest
description: Build the manifest (+sha256 and per-masspoint healthy-events guard) of corrupted files proposed for removal. Read-only: never reads file data, never moves anything.
---
`python3 scripts/make_manifest.py [--min-healthy 300000]` (planner agent runs it). Output `results/deletion/manifest_<ts>.csv` (+ `.sha256`): path, realpath, masspoint, reason, size_bytes, mtime, locality, healthy_events_after. Exit 3 = a masspoint would fall under the guard: stop. Removing corrupted files does not change healthy events, since they are already excluded. Stray/excluded files (config/exclude.txt) are never in the manifest.
