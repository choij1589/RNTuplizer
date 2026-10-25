#!/bin/bash
# status.sh MASSPOINT [QC]: prints done/total chunks, idle/run/held jobs; writes .work/missing.txt (chunk ids with no output)
MP=$1; QC=${2:-/d0/scratch/choij/SampleFactoryQC}; W=$QC/results/$MP/.work
tot=$(ls $W/lists | wc -l); done=$(ls $W/out/chunk_*.json 2>/dev/null | wc -l)
for i in $(ls $W/lists | sed 's/chunk_\(.*\).txt/\1/'); do [ -f $W/out/chunk_$i.json ] || echo $i; done > $W/missing.txt
echo "chunks done=$done/$tot"
condor_q -constraint "regexp(\"$W\", Args)" -af JobStatus 2>/dev/null | sort | uniq -c | sed 's/ 1$/ idle/;s/ 2$/ running/;s/ 5$/ held/'
