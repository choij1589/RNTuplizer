#!/bin/bash
# rnt_run_mp.sh MASSPOINT {convert|validate} [--branches CONF] [--only-failed]
#   convert : manifest (read-only plan) -> gate P -> condor conversion (missing chunks resubmitted max 2x) -> conversion.csv -> gate B
#   validate: condor validation of every converted file (or only failed/unvalidated with --only-failed) -> validation.csv, summary.csv -> gate C
# Driver output is appended to <run dir>/driver.log. Exit code = result of the last gate (0 pass).
R=$(cd "$(dirname "$0")/.." && pwd); MP=$1; MODE=$2; shift 2
BR=$R/config/rntuple_branches.conf; OF=""
while [ $# -gt 0 ]; do case $1 in --branches) BR=$2; shift 2;; --only-failed) OF="--only-failed"; shift;; *) echo "unknown arg $1"; exit 64;; esac; done
G="python3 $R/python/pipeline_gate.py"
if [ "$MODE" = convert ]; then
  python3 $R/python/rnt_make_manifest.py $MP --branches $BR; rc=$?
  [ $rc -ne 0 ] && [ $rc -ne 4 ] && exit $rc     # 4 = conflicts: reported by gate P below
  MAN=$(ls -t $(python3 $R/python/layout.py stage-dir $MP rntuple)/manifest_*.csv | head -1)
  $G P $MP --manifest $MAN || exit 4
  out=$(python3 $R/python/rnt_make_jobs.py $MP --manifest $MAN); rc=$?
  [ $rc -eq 3 ] && { echo "nothing to convert (all skip-valid)"; $G B $MP; exit $?; }
  [ $rc -ne 0 ] && { echo "$out"; exit $rc; }
  STAGE=rntuple; AGG="python3 $R/python/rnt_aggregate.py $MP"; EXTRA=""; FINAL="$G B $MP"
else
  out=$(python3 $R/python/rnt_make_jobs.py $MP --validate $OF); rc=$?
  [ $rc -eq 3 ] && { echo "nothing to validate"; $G C $MP; exit $?; }
  [ $rc -ne 0 ] && { echo "$out"; exit $rc; }
  STAGE=validate; AGG="python3 $R/python/rnt_validate_report.py $MP"; EXTRA="--validate"; FINAL="$G C $MP"
fi
read SUB NF _f NC _c RUN <<< "$out"
exec > >(tee -a $RUN/driver.log) 2>&1
echo "$(date +%F\ %T) $MP $MODE run=$(basename $RUN) files=$NF chunks=$NC"
condor_submit $SUB >/dev/null
for try in 0 1 2; do
  bash $R/scripts/condor_wait.sh $RUN
  : > $RUN/missing.txt
  for f in $RUN/lists/chunk_*.txt; do i=$(basename $f .txt); i=${i#chunk_}; [ -f $RUN/out/chunk_$i.jsonl ] || echo $i >> $RUN/missing.txt; done
  [ -s $RUN/missing.txt ] || break
  [ $try -lt 2 ] || { echo "still missing after retries: $(tr '\n' ' ' < $RUN/missing.txt)"; break; }
  echo "resubmitting: $(tr '\n' ' ' < $RUN/missing.txt)"
  python3 $R/python/rnt_make_jobs.py $MP $EXTRA --only $RUN/missing.txt >/dev/null
  condor_submit $RUN/submit.sub >/dev/null
done
$AGG
python3 $R/python/pipeline_state.py record $MP $([ "$MODE" = convert ] && echo convert || echo validate) >/dev/null
$FINAL
