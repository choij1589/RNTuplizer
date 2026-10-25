---
name: pipeline
description: Fixed workflow for ONE masspoint - preflight, QC, conversion TTree->RNTuple, validation. Invoke as /pipeline <masspoint> [--branches FILE]. Main session only.
---
0 Preflight: `source scripts/env.sh` works (ROOT 6.40.02), `bin/rnt_convert` built (`bash scripts/rnt_build.sh`), branch config resolves (`rnt_branches.py resolve`), no conflicting condor jobs, `results/<mp>/` writable. First use: agent `rnt-scout`.
1 QC: skill `sample-qc` for the masspoint, then **gate A** (`pipeline_gate.py A`). Exit 3 -> STOP, offer `/qc-cleanup <mp>`; continue only when corrupted == 0 and QC is fresh.
2 Convert: agent `rnt-planner` builds the manifest (`rnt_make_manifest.py`, **gate P**; report counts, show the plan to the user before the first production run); then `bash scripts/rnt_run_mp.sh <mp> convert --branches <conf>` via agent `rnt-condor-runner`; **gate B**.
3 Validate: `bash scripts/rnt_run_mp.sh <mp> validate`; independent sample check by agent `rnt-validator`; **gate C**.
4 Finalize: `pipeline_state.py record`, `rollup.py`/results overview, report (files, entries, sizes, compression ratio, bytes saved by DROP, efficiency, issues).
Rules: one masspoint at a time; test selection = `--branches config/rntuple_branches.test.conf`; production = `config/rntuple_branches.conf`. Destructive steps (quarantine/purge) only via `/qc-cleanup` with user approval. Conversion deletes nothing.
