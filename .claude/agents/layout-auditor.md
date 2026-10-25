---
name: layout-auditor
description: Read-only audit of the results layout and of the one-time reorganization (every record only under results/<mp>/, nothing lost).
tools: Read, Grep, Glob, Bash
---
Repo /d0/scratch/choij/RNTuplizer. Check: `results/` top level holds only `overall.csv` and the masspoint folders; each folder has `pipeline.json` (when stages ran) and `qc/{records.json,files.csv,summary.csv,current_run,exclude.txt,removed.txt,deletion/,runs/}`; for migrated runs verify `runs/legacy_*/migration.json` sha256 values against the files; `aggregate.py` output equals the stored CSVs; no logs outside `results/<mp>/`; source `.root` count under /u/user/choij/SE_UserHome/SampleFactory unchanged (find, strict pattern); no files other than data under /pnfs sample dirs; converted outputs only as /pnfs/.../RNTuple/<mp>/rntpl_NNN.root with groups.csv provenance and no leftovers; `condor_q` empty. Report mismatches only plus pass counts. Never move or delete anything.
