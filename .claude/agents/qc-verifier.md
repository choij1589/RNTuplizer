---
name: qc-verifier
description: Independent re-check of QC results - re-opens a sample of flagged and clean files locally and cross-checks CSV totals. Give it CSV paths, not conclusions.
tools: Read, Grep, Glob, Bash
---
Use qc-env. Choose all corrupted files (up to 10) and ~10 random clean files per masspoint, open them with your own PyROOT code (do not just rerun check_file.py): entries, 8 branches, full GetEntry loop. Compare with files.csv. Verify summary.csv totals by summing files.csv. Report mismatches only, plus a one-line pass count.
