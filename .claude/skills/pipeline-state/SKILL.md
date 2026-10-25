---
name: pipeline-state
description: Per-masspoint state (results/<mp>/pipeline.json) and the gate checks A / P / B / C of the fixed workflow.
---
`python3 python/pipeline_state.py show|record <mp> [qc|convert|validate]`. `python3 python/pipeline_gate.py A|P|B|C <mp> [--manifest M]` prints PASS/FAIL with reasons (exit 0 pass, 1 fail, 3 = gate A blocked only by corrupted files -> /qc-cleanup).
A: QC complete + fresh (file set and sizes equal to files.csv), 8 custom branches present, corrupted == 0. P: plan has no conflicts, sha256 valid. B: conversion complete (see rnt-convert). C: validation + QC cross-checks all pass.
