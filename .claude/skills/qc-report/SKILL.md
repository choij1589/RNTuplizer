---
name: qc-report
description: Aggregate chunk results into results/<mp>/files.csv and summary.csv, and roll up all masspoints into results/overall.csv.
---
`python3 scripts/aggregate.py <mp>` (exit 2 = some files have no result; do not treat as final). `python3 scripts/rollup.py`.
files.csv: path,timestamp_dir,size_bytes,n_events,corrupted,reasons,warnings,missing_branches.
summary.csv: n_files, n_files_corrupted/clean, n_events_total/corrupted/clean, n_files_unreadable (corrupted files with n_events=0, so their events are unknown and excluded from totals), gen_num_passed/total, filter_efficiency = sum(numEventsPassed)/sum(numEventsTotal) over CLEAN files, filter_eff_err (binomial), n_files_missing_result, all_custom_branches_present.
Invariants: clean+corrupted=total; files.csv rows = n_files = number of .root files found.
