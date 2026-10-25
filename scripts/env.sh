# source me: the pinned LCG view (ROOT, Python, gcc, cmake) defined in config/rntuple_env.conf.
# Used by all stages locally and on condor workers (getenv = False; the job wrappers source this file).
_rnt_repo=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)
eval "$(grep -E '^[A-Z_]+=' "$_rnt_repo/config/rntuple_env.conf")"
export RNT_REPO=$_rnt_repo
source /cvmfs/sft.cern.ch/lcg/views/$LCG_VIEW/$LCG_PLATFORM/setup.sh >/dev/null 2>&1
if [ "$(root-config --version 2>/dev/null)" != "$ROOT_VERSION" ]; then
  echo "env.sh: expected ROOT $ROOT_VERSION from $LCG_VIEW/$LCG_PLATFORM, got '$(root-config --version 2>/dev/null)'" >&2
  return 1 2>/dev/null || exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
unset _rnt_repo
