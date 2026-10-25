---
name: sample-qc
description: Orchestrate the full SampleFactory QC (all masspoints or one) - discovery, pilot, condor fan-out, aggregation, verification. Invoke as /sample-qc [masspoint|all] [--force].
---
Run from the main session (subagents cannot spawn subagents). Skip a masspoint whose summary.csv is newer than all its inputs unless --force.
0. Discovery gate: agent `qc-scout` + skill `qc-env`; list masspoints/files, confirm trees/branches (Events, Runs, LuminosityBlocks with GenFilter_*), 8 custom branches. Show anything unexpected to the user before continuing.
1. Pilot gate: pick the smallest masspoint; agent `qc-condor-runner` runs it end to end (`qc-condor`), `qc-aggregator` builds CSVs, `qc-verifier` re-checks locally. Don't change check logic afterwards without re-running the pilot.
2. Fan-out: `qc-condor-runner` for remaining masspoints, 4-6 in flight at once (agents in parallel in one message).
3. Close each masspoint: `qc-aggregator` (`qc-report`); done only if exit 0.
4. Final gate: `rollup.py`; report corrupted files, job failures, anomalies (efficiency spread, missing branches); `qc-verifier` spot-checks. Summarize to the user.
