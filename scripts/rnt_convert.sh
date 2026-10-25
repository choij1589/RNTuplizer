#!/bin/bash
# rnt_convert.sh REPO RUN_DIR CHUNK TABLE   (condor worker: convert the groups of one chunk, several TTree files -> one RNTuple file)
# lists/chunk_<C>.txt lines: OUTPUT<TAB>INPUT1<TAB>INPUT2...   Each group is converted into worker-local scratch, copied next to its
# final place as <out>.part.<pid> and renamed atomically. An existing (stale) output is first renamed into RNTuple_superseded/ - never
# deleted. One JSON record per output goes to out/chunk_<C>.jsonl.tmp, renamed to chunk_<C>.jsonl when the chunk is complete.
# RESUMABLE: a rerun of the chunk skips outputs that already have an ok+copied record in the .tmp file.
R=$1; W=$2; C=$3; TABLE=$4
source $R/scripts/env.sh || exit 1
COMP=$(grep -E '^COMPRESSION=' $R/config/rntuple_output.conf | cut -d= -f2)
RUNID=$(basename $W)
TMP=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/rnt.XXXXXX") || exit 1
trap 'rm -rf "$TMP"' EXIT
touch $W/out/chunk_$C.jsonl.tmp
python3 - $W/out/chunk_$C.jsonl.tmp > $TMP/done.txt <<'PY'
import json, sys
for line in open(sys.argv[1]):
    try:
        j = json.loads(line)
    except ValueError:
        continue
    if j.get("ok") and j.get("copied"):
        print(j["output"])
PY
while IFS=$'\t' read -r -a F; do
  OUT=${F[0]}; [ -z "$OUT" ] && continue
  grep -qxF -- "$OUT" $TMP/done.txt && continue
  printf '%s\n' "${F[@]:1}" > $TMP/inputs.txt
  rm -f $TMP/out.root $TMP/out.root.part $TMP/rec.json
  $R/bin/rnt_convert --branches $TABLE --compression $COMP --json $TMP/rec.json --inputs $TMP/inputs.txt $TMP/out.root 2> $TMP/err.txt
  rc=$?
  copied=false; note=""; sup=""
  if [ $rc -eq 0 ] && [ -s $TMP/out.root ]; then
    mkdir -p "$(dirname "$OUT")"
    if cp $TMP/out.root "$OUT.part.$$" && [ "$(stat -c %s $TMP/out.root)" = "$(stat -c %s "$OUT.part.$$")" ]; then
      if [ -e "$OUT" ]; then
        sup=$(python3 $R/python/layout.py superseded-dst "$OUT" "$RUNID")
        mkdir -p "$(dirname "$sup")" && mv -n -- "$OUT" "$sup" && [ ! -e "$OUT" ] || { note="could not supersede the old output"; sup=""; }
      fi
      if [ -z "$note" ] && mv -T -n "$OUT.part.$$" "$OUT" && [ -e "$OUT" ] && [ ! -e "$OUT.part.$$" ]; then copied=true; else [ -z "$note" ] && note="rename to final location failed"; rm -f "$OUT.part.$$"; fi
    else note="copy to final location failed"; rm -f "$OUT.part.$$"; fi
  fi
  python3 - "$TMP/rec.json" "$TMP/err.txt" $rc $copied "$note" "$OUT" "$TMP/inputs.txt" "$sup" >> $W/out/chunk_$C.jsonl.tmp <<'PY'
import json, os, sys
rec_p, err_p, rc, copied, note, out, inp_p, sup = sys.argv[1:9]
inputs = [l.rstrip("\n") for l in open(inp_p)]
try:
    rec = json.load(open(rec_p))
except Exception:
    rec = dict(ok=False, error="no record from rnt_convert", trees=[], not_trees=[], root_version="", out_bytes=-1, seconds=0)
rec.update(output=out, inputs=inputs, rc=int(rc), copied=(copied == "true"), note=note, superseded=sup,
           stderr_tail=open(err_p).read()[-300:] if os.path.exists(err_p) else "")
print(json.dumps(rec))
PY
done < $W/lists/chunk_$C.txt
mv $W/out/chunk_$C.jsonl.tmp $W/out/chunk_$C.jsonl
