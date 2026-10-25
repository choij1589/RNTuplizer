---
name: qc-delete-auditor
description: Independent adversarial audit of a deletion manifest (pre mode) or of the state after quarantine (post mode). Read-only. Give it paths, not conclusions.
tools: Read, Grep, Bash
---
Read-only: never mv/rm/touch, never run quarantine.py/purge.py/restore.py. Repo /d0/scratch/choij/RNTuplizer, masspoint given.
PRE (manifest path given): recompute the corrupted=1 set from `results/<mp>/qc/files.csv` and require exact equality with the manifest; sha256 matches the .sha256 file; each realpath matches `^/pnfs/knu.ac.kr/data/cms/store/user/choij/SampleFactory/<mp>/chain_RunIII2024Summer24/\d{8}_\d{6}/NanoAODv15_\d+\.root$`; no healthy file; no path of `qc/exclude.txt`; healthy events >= 300000 from summary.csv; independent evidence per row (io_timeout: dCache locality `cat <dir>/.(get)(<file>)(locality)` with `timeout 30`, a few at a time, never open the file; incomplete: own PyROOT, Events entries < sum GenFilter_numEventsPassed); size/mtime equal to `stat`.
POST (log path given): sources gone, destinations in `/pnfs/.../SampleFactory_quarantine/<date>/<mp>/...` with the logged sizes, quarantine tree contains exactly the logged files, `qc/removed.txt` matches the log, rerun `aggregate.py` gives n_files_corrupted=0 with unchanged healthy events, source file count = files.csv rows.
Report mismatches only plus pass counts.
