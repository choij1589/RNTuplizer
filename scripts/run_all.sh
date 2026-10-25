#!/bin/bash
# run_all.sh [PARALLEL=23]: QC for every masspoint (each via scripts/qc_run_mp.sh, all submitted at once; HTCondor schedules),
# then results/overall.csv. Per-masspoint logs: results/<mp>/qc/runs/<run>/driver.log
R=$(cd "$(dirname "$0")/.." && pwd); P=${1:-23}
python3 $R/python/layout.py masspoints | xargs -P $P -I{} bash $R/scripts/qc_run_mp.sh {} >/dev/null
python3 $R/python/rollup.py
