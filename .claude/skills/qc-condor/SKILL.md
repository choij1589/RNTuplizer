---
name: qc-condor
description: Run the file check for one masspoint on HTCondor (chunks of 20 files) - submit, monitor, resubmit, merge, aggregate. Per-masspoint run directories under results/<mp>/qc/runs/.
---
One command per masspoint: `bash scripts/qc_run_mp.sh <mp>` (submit -> wait -> resubmit missing chunks max 2x -> `qc_merge.py` -> `aggregate.py`; log in `<run>/driver.log`; exit 2 = files still without result). `bash scripts/run_all.sh` does all masspoints at once (HTCondor schedules).
Pieces: `python/make_submit.py <mp> [--only ids]` (strict discovery `chain_RunIII2024Summer24/<ts>/NanoAODv15_<N>.root`; creates `results/<mp>/qc/runs/<run_id>/{lists,out,logs,params.json,submit.sub}` and sets `qc/current_run`), `scripts/run_qc.sh` (worker), `scripts/status.sh <mp>` (done/total, idle/running/held, writes `<run>/missing.txt`), `scripts/condor_wait.sh <run>` (held-only jobs are reported and removed so the retry logic can resubmit), `python/retry_failed.py <mp> [--reason io_timeout] [--submit]` (extra chunk `chunk_rNNN`).
A job-level failure is not file corruption: records from an older run never satisfy a new run (`_run` stamp), so missing chunks keep `aggregate.py` at exit 2. Remove jobs only by cluster id, never `condor_rm <user>`.
