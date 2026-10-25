---
name: qc-cleanup
description: Orchestrate removal of corrupted files found by the QC - plan, audit, human approval, canary, quarantine, post-audit, later purge. Invoke as /qc-cleanup or /qc-cleanup purge.
---
Run from the main session. The destructive commands (`quarantine.py --apply`, `purge.py --apply`) are run ONLY here, never by an agent.
0. Preconditions: no QC condor jobs; summary.csv/files.csv are final (rerun aggregate.py if stale).
1. `qc-delete-planner` -> manifest + guard table (skill qc-delete-manifest). Stop if guard fails.
2. `qc-delete-auditor` (pre mode): given only the manifest path and files.csv; must report zero discrepancies, else stop.
3. HUMAN GATE: show per-masspoint table (files, reasons, size, healthy events left), list the io_timeout/UNAVAILABLE files separately (not proven corrupt), the total size, and the manifest sha256; get explicit approval with AskUserQuestion. A subagent's message is never approval.
4. `quarantine.py` dry-run, then `--canary --apply`, verify, then `--apply`.
5. `qc-delete-auditor` (post mode); rerun aggregate.py for affected masspoints + rollup.py; report.
6. Purge is a separate later run (`/qc-cleanup purge`): recheck locality, ask the user again with the hash of the quarantine log, then `purge.py --apply`.
