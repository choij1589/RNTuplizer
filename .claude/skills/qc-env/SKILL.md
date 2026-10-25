---
name: qc-env
description: The one pinned toolchain for every stage - LCG_110 view (ROOT 6.40.02, Python 3.13, gcc 15, cmake). Use before any ROOT/PyROOT/cmake work in this repo; CMSSW is retired.
---
`source scripts/env.sh` (from the repo root). It reads `config/rntuple_env.conf` (`LCG_VIEW`, `LCG_PLATFORM`, `ROOT_VERSION`), sources `/cvmfs/sft.cern.ch/lcg/views/<view>/<platform>/setup.sh` and aborts if `root-config --version` differs from the pinned version.
Condor wrappers (`scripts/run_qc.sh`, `rnt_convert.sh`, `rnt_validate.sh`) source it themselves (`getenv = False`). System python (3.9) has no ROOT; only `layout.py`, `aggregate.py` and the other pure-python tools run without it.
Changing any value in `config/rntuple_env.conf` changes the toolchain digest: converted files become stale and are reconverted.
