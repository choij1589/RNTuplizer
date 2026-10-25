#!/usr/bin/env python3
"""rollup.py [--qc DIR]: concatenate results/*/summary.csv -> results/overall.csv"""
import csv, glob, sys
qc = sys.argv[1] if len(sys.argv) > 1 else "/d0/scratch/choij/SampleFactoryQC"
rows = [next(csv.DictReader(open(f))) for f in sorted(glob.glob(f"{qc}/results/*/summary.csv"))]
with open(f"{qc}/results/overall.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), "masspoints ->", f"{qc}/results/overall.csv")
