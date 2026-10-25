#!/bin/bash
# pipeline_run_all.sh [PARALLEL=4] [--branches CONF]: pipeline_run_mp.sh for every masspoint, PARALLEL masspoints at a time
# (each masspoint submits its own condor jobs; HTCondor schedules). Writes results/pipeline_run_all.status (mp, exit code) and
# refreshes the rollups at the end. Masspoints that are already fully valid finish within a minute (skip-valid).
R=$(cd "$(dirname "$0")/.." && pwd); P=${1:-4}; shift
ST=$R/results/pipeline_run_all.status; : > $ST
python3 $R/python/layout.py masspoints | xargs -P $P -I{} bash -c "bash $R/scripts/pipeline_run_mp.sh {} $*; echo {} \$? >> $ST"
python3 $R/python/rollup.py
echo "ALL-DONE $(date '+%F %T')" >> $ST
