---
name: qc-condor
description: Run the file check for one masspoint on KNU HTCondor (chunks of 20 files), monitor, and resubmit missing chunks.
---
1. `python3 scripts/make_submit.py <masspoint>` -> `results/<mp>/.work/{lists,out,log,submit.sub}`; prints the .sub path. All timestamp dirs are scanned and treated as independent files.
2. `condor_submit <.sub>`.
3. `scripts/status.sh <mp>` -> done/total chunks, idle/running/held; writes `.work/missing.txt`. Don't poll faster than ~60 s.
4. Held/failed/missing chunks: read `.work/log/chunk_N.err`, `condor_release`/`condor_rm` as needed, then `make_submit.py <mp> --only .work/missing.txt` and resubmit (max 2 retries). A chunk that still fails is a job failure, NOT file corruption: report it, never count its files as clean (aggregate.py exits 2 when results are missing).
Outputs are written atomically (tmp+mv), so a present chunk_N.json is complete. Jobs use getenv=False and source cvmfs themselves; paths must be visible on workers (/u, /d0, /pnfs are NFS).
