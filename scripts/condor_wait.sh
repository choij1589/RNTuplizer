#!/bin/bash
# condor_wait.sh RUN_DIR: block until no condor job of this run directory is left; jobs that are only held are reported and removed.
W=$1
while :; do
  st=$(condor_q -constraint "regexp(\"$W\", Args)" -af JobStatus 2>/dev/null)
  [ -z "$st" ] && break
  if ! echo "$st" | grep -qE '^(1|2)$'; then
    condor_q -constraint "regexp(\"$W\", Args)" -af ClusterId ProcId HoldReason | head -3
    condor_q -constraint "regexp(\"$W\", Args)" -af ClusterId | sort -u | xargs -r condor_rm >/dev/null
  fi
  sleep 60
done
