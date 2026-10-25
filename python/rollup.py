#!/usr/bin/env python3
"""rollup.py: concatenate the per-masspoint summaries into results/overall.csv (QC) and results/overall_rntuple.csv (conversion + validation)."""
import sys; sys.dont_write_bytecode = True
import csv, glob
import layout

for stage, name in (("qc", "overall.csv"), ("rntuple", "overall_rntuple.csv")):
    rows = [next(csv.DictReader(open(f))) for f in sorted(glob.glob(f"{layout.RESULTS}/*/{stage}/summary.csv"))]
    if not rows:
        continue
    with open(f"{layout.RESULTS}/{name}", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "masspoints ->", f"{layout.RESULTS}/{name}")
