#!/bin/bash
# status.sh MASSPOINT: chunks done/total of the current QC run, idle/running/held; writes <run>/missing.txt (chunk ids without output)
R=$(cd "$(dirname "$0")/.." && pwd); MP=$1
W=$(python3 $R/python/layout.py run-dir $MP qc) || exit 1
tot=$(ls $W/lists | wc -l); done=$(ls $W/out/chunk_*.json 2>/dev/null | wc -l)
for f in $W/lists/chunk_*.txt; do i=$(basename $f .txt); i=${i#chunk_}; [ -f $W/out/chunk_$i.json ] || echo $i; done > $W/missing.txt
echo "run=$(basename $W) chunks done=$done/$tot"
condor_q -constraint "regexp(\"$W\", Args)" -af JobStatus 2>/dev/null | sort | uniq -c | sed 's/ 1$/ idle/;s/ 2$/ running/;s/ 5$/ held/'
