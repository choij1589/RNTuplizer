#!/bin/bash
# qc_run_mp.sh MASSPOINT: full QC for one masspoint: submit, wait, resubmit missing chunks (max 2x), merge, aggregate.
# Logs of this driver go to <run dir>/driver.log. Exit 2 = some files still without result.
R=$(cd "$(dirname "$0")/.." && pwd); MP=$1
set -u
out=$(python3 $R/python/make_submit.py $MP) || exit 1
read SUB NF _f NC _c RUN <<< "$out"
exec > >(tee -a $RUN/driver.log) 2>&1
echo "$(date +%F\ %T) $MP run=$(basename $RUN) files=$NF chunks=$NC"
condor_submit $SUB >/dev/null
for try in 0 1 2; do
  while :; do
    st=$(condor_q -constraint "regexp(\"$RUN\", Args)" -af JobStatus 2>/dev/null)
    [ -z "$st" ] && break
    if ! echo "$st" | grep -qE '^(1|2)$'; then   # only held jobs left: report the reason, remove them, let the retry logic resubmit
      condor_q -constraint "regexp(\"$RUN\", Args)" -af ClusterId ProcId HoldReason | head -3
      condor_q -constraint "regexp(\"$RUN\", Args)" -af ClusterId | sort -u | xargs -r condor_rm >/dev/null
    fi
    sleep 60
  done
  bash $R/scripts/status.sh $MP | head -1
  [ -s $RUN/missing.txt ] || break
  [ $try -lt 2 ] || { echo "still missing after retries: $(tr '\n' ' ' < $RUN/missing.txt)"; break; }
  echo "resubmitting: $(tr '\n' ' ' < $RUN/missing.txt)"
  python3 $R/python/make_submit.py $MP --only $RUN/missing.txt >/dev/null
  condor_submit $RUN/submit.sub >/dev/null
done
python3 $R/python/qc_merge.py $MP
python3 $R/python/aggregate.py $MP >/dev/null; rc=$?
echo "$(date +%F\ %T) $MP aggregate exit=$rc"
[ $rc -eq 0 ] && python3 $R/python/pipeline_state.py record $MP qc >/dev/null
exit $rc
