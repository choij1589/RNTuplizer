---
name: sample-qc
description: Stage 1 of the pipeline - QC of one masspoint (or all). Invoke as /sample-qc [masspoint|all]; /pipeline runs it as its first stage.
---
Run from the main session. Per masspoint: `bash scripts/qc_run_mp.sh <mp>` (skill `qc-condor`), then `python3 python/pipeline_gate.py A <mp>`; record with `python3 python/pipeline_state.py record <mp> qc`. For `all`: `bash scripts/run_all.sh`.
Agents: `qc-scout` (discovery/probing), `qc-condor-runner` (submit/monitor/retry), `qc-aggregator` (reports + invariants), `qc-verifier` (independent re-check of flagged + sampled files, own code).
Gate A fails with exit 3 when only corrupted files stand in the way: run `/qc-cleanup <mp>` (human approval), then re-check.
