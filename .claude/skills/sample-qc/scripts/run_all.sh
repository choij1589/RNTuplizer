#!/bin/bash
# run_all.sh [BATCH=1000 (all at once; HTCondor schedules)]: run all masspoints under the sample dir lacking a complete summary.csv; batches in flight; retries missing chunks twice
QC=/d0/scratch/choij/SampleFactoryQC; S=/u/user/choij/SE_UserHome/SampleFactory; B=${1:-1000}
cd $QC
MPS=$(ls $S | while read m; do [ -f results/$m/summary.csv ] && [ "$FORCE" != 1 ] || echo $m; done)
submit() { local f=$(python3 .claude/skills/qc-condor/scripts/make_submit.py $1 ${2:+--only $2} | awk '{print $1}'); condor_submit $f >/dev/null; }
set -- $MPS
while [ $# -gt 0 ]; do
  batch=("${@:1:$B}"); shift $(( $# < B ? $# : B ))
  for m in "${batch[@]}"; do  # idempotent: skip if queued; submit only chunks lacking output
    [ -n "$(condor_q -constraint "regexp(\"results/$m/\", Args)" -af ClusterId)" ] && continue
    if [ -d results/$m/.work/lists ]; then bash .claude/skills/qc-condor/scripts/status.sh $m >/dev/null 2>&1
      [ -s results/$m/.work/missing.txt ] && submit $m results/$m/.work/missing.txt
    else submit $m; fi
  done
  for try in 0 1 2; do
    while true; do
      sleep 120; pend=0
      for m in "${batch[@]}"; do bash .claude/skills/qc-condor/scripts/status.sh $m >/dev/null 2>&1
        [ -z "$(condor_q -constraint "regexp(\"results/$m/\", Args)" -af ClusterId 2>/dev/null)" ] || pend=1; done
      [ $pend = 0 ] && break
    done
    again=0
    for m in "${batch[@]}"; do bash .claude/skills/qc-condor/scripts/status.sh $m >/dev/null 2>&1
      if [ -s results/$m/.work/missing.txt ]; then
        [ $try -lt 2 ] && { submit $m results/$m/.work/missing.txt; again=1; }; fi; done
    [ $again = 0 ] && break
  done
  for m in "${batch[@]}"; do python3 .claude/skills/qc-report/scripts/aggregate.py $m >/dev/null 2>>results/aggregate_errors.log || echo "INCOMPLETE $m" >> results/aggregate_errors.log; done
  echo "batch done: ${batch[*]}" >> results/run_all.log
done
python3 .claude/skills/qc-report/scripts/rollup.py >> results/run_all.log
echo ALLDONE >> results/run_all.log
