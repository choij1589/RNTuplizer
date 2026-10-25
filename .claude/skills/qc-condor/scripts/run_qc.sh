#!/bin/bash
# run_qc.sh QC_ROOT WORKDIR CHUNK_ID
set -e
QC=$1; W=$2; C=$3
source $QC/.claude/skills/qc-env/scripts/env.sh
mapfile -t F < $W/lists/chunk_$C.txt
python3 $QC/.claude/skills/qc-check-rootfile/scripts/check_file.py $W/out/chunk_$C.json.tmp "${F[@]}"
mv $W/out/chunk_$C.json.tmp $W/out/chunk_$C.json
