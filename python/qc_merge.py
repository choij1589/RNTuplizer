#!/usr/bin/env python3
"""qc_merge.py MASSPOINT [--run RUN_ID]: merge chunk JSONs of a QC run into results/<mp>/qc/records.json
(path -> per-file facts; chunks processed in name order so retry chunks chunk_r* override earlier records)."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, glob, json, os
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--run")
a = ap.parse_args()
rd = layout.run_dir(a.mp, "qc", a.run)
rp = f"{layout.qc_dir(a.mp)}/records.json"
recs = json.load(open(rp)) if os.path.exists(rp) else {}
n = 0
for f in sorted(glob.glob(f"{rd}/out/chunk_*.json")):
    for r in json.load(open(f)):
        r["_run"] = os.path.basename(rd)
        recs[r["path"]] = r
        n += 1
tmp = rp + ".tmp"
json.dump(recs, open(tmp, "w"))
os.replace(tmp, rp)
print(f"merged {n} records from {os.path.basename(rd)} -> {rp} ({len(recs)} total)")
