#!/bin/bash
# pipeline_run_mp.sh MASSPOINT [--branches CONF]: the fixed workflow for ONE masspoint, non-interactive part:
#   gate A (QC complete, fresh, clean)  ->  convert (plan, gate P, condor, gate B)  ->  validate (condor, gate C)  ->  state
# Stops at the first failing gate (exit code of that stage). Idempotent: a rerun skips outputs that are still valid.
# QC and cleanup are NOT run here (cleanup needs human approval): gate A fails/blocks if they are not done.
# Log: results/<mp>/pipeline.log
R=$(cd "$(dirname "$0")/.." && pwd); MP=$1; shift
BR=(); [ "$1" = "--branches" ] && BR=(--branches "$2")
LOG=$R/results/$MP/pipeline.log
exec >> $LOG 2>&1
echo "=== $(date '+%F %T') pipeline $MP ${BR[*]}"
python3 $R/python/pipeline_gate.py A $MP || { echo "STOP at gate A"; exit 10; }
python3 $R/python/pipeline_state.py record $MP qc >/dev/null
bash $R/scripts/rnt_run_mp.sh $MP convert "${BR[@]}" || { echo "STOP at conversion/gate B/P"; exit 20; }
bash $R/scripts/rnt_run_mp.sh $MP validate || { echo "STOP at validation/gate C"; exit 30; }
echo "=== $(date '+%F %T') $MP DONE"
