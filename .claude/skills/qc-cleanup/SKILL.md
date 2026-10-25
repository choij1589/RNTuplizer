---
name: qc-cleanup
description: Remove the corrupted files of one masspoint - plan, audit, human approval, canary, quarantine, post-audit; purge later. Invoke as /qc-cleanup <masspoint> or /qc-cleanup purge <masspoint>.
---
Main session only. 1) `qc-delete-planner` -> manifest (skill qc-delete-manifest); stop if the guard fails. 2) `qc-delete-auditor` (pre) must report zero discrepancies. 3) HUMAN GATE: show files/reasons/size/healthy events left, list io_timeout/UNAVAILABLE files separately (not proven corrupt) and the manifest sha256; ask via AskUserQuestion. 4) quarantine dry-run, `--canary --apply`, verify, `--apply`. 5) `qc-delete-auditor` (post); `aggregate.py`, `rollup.py`; re-check gate A.
Purge is a separate later run: recheck locality (ONLINE files should be restored and re-QC'd), ask again with the hash of the quarantine log, then `purge.py --apply`.
