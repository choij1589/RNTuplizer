#!/bin/bash
# rnt_validate.sh REPO RUN_DIR CHUNK TABLE   (condor worker: independently validate the converted outputs of one chunk)
# lists/chunk_<C>.txt lines: OUTPUT<TAB>INPUT1<TAB>INPUT2...; one JSON record per output goes to out/chunk_<C>.jsonl (atomic mv at the end).
R=$1; W=$2; C=$3; TABLE=$4
source $R/scripts/env.sh || exit 1
TMP=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/rntv.XXXXXX") || exit 1
trap 'rm -rf "$TMP"' EXIT
: > $W/out/chunk_$C.jsonl.tmp
while IFS=$'\t' read -r -a F; do
  OUT=${F[0]}; [ -z "$OUT" ] && continue
  printf '%s\n' "${F[@]:1}" > $TMP/inputs.txt
  rm -f $TMP/rec.json
  $R/bin/rnt_validate --table $TABLE --json $TMP/rec.json --inputs $TMP/inputs.txt "$OUT" 2> $TMP/err.txt
  rc=$?
  python3 - "$TMP/rec.json" "$TMP/err.txt" $rc "$OUT" "$TMP/inputs.txt" >> $W/out/chunk_$C.jsonl.tmp <<'PY'
import json, os, sys
rec_p, err_p, rc, out, inp_p = sys.argv[1:6]
inputs = [l.rstrip("\n") for l in open(inp_p)]
try:
    rec = json.load(open(rec_p))
except Exception:
    rec = dict(ok=False, file_errors=["no record from rnt_validate"], trees=[], seconds=0, root_version="")
rec.update(output=out, inputs=inputs, rc=int(rc), stderr_tail=open(err_p).read()[-300:] if os.path.exists(err_p) else "")
print(json.dumps(rec))
PY
done < $W/lists/chunk_$C.txt
mv $W/out/chunk_$C.jsonl.tmp $W/out/chunk_$C.jsonl
