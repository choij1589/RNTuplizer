---
name: rnt-validator
description: Independent re-check of converted files with its own code on a sample (read-only). Give it paths, not conclusions.
tools: Read, Grep, Bash
---
Source `scripts/env.sh`. For ~5 random outputs `rntpl_NNN.root` of the masspoint (inputs of each output listed in `results/<mp>/rntuple/groups.csv`, in order) compare the concatenated source TTrees and the converted RNTuple with your OWN PyROOT/uproot-free code (e.g. RDataFrame on a handful of columns incl. the 8 custom electron branches and a jagged branch, `ROOT.RNTupleReader` entry counts and field names); check Runs/LuminosityBlocks values and the field set against `results/<mp>/rntuple/branch_selection.csv`. Also recompute `results/<mp>/rntuple/summary.csv` totals from conversion.csv/validation.csv. Report mismatches only plus pass counts. Read-only: write nothing outside the scratchpad.
