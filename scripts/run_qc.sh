#!/bin/bash
# run_qc.sh REPO RUN_DIR CHUNK_ID   (condor worker for one QC chunk)
set -e
R=$1; W=$2; C=$3
source $R/scripts/env.sh
mapfile -t F < $W/lists/chunk_$C.txt
python3 $R/python/check_file.py $W/out/chunk_$C.json.tmp "${F[@]}"
mv $W/out/chunk_$C.json.tmp $W/out/chunk_$C.json
