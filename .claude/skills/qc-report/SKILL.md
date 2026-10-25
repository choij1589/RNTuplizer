---
name: qc-report
description: Merge QC chunk results into results/<mp>/qc/{records.json,files.csv,summary.csv} and roll up all masspoints into results/overall.csv.
---
`python3 python/qc_merge.py <mp>` (chunk JSON of the current run -> `records.json`, stamped with `_run`), `python3 python/aggregate.py <mp>` (exit 2 = some expected file has no record from the current run), `python3 python/rollup.py` (-> `results/overall.csv`).
Expected files = lists of the current run minus `qc/exclude.txt` (QC-excluded, not deleted) and `qc/removed.txt` (quarantined/purged), both per masspoint.
files.csv: path,timestamp_dir,size_bytes,n_events,corrupted,reasons,events_missing,warnings,missing_branches. summary.csv: n_files, n_files_corrupted/clean, n_events_total/corrupted/clean, n_files_unreadable, gen_num_passed/total, filter_efficiency(+err, clean files only), n_files_incomplete, n_events_missing_incomplete, n_files_missing_result, n_files_removed, all_custom_branches_present.
Invariants: clean + corrupted = total; files.csv rows = n_files = source files on disk minus excluded/removed.
