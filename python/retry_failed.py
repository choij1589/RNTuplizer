#!/usr/bin/env python3
"""retry_failed.py MASSPOINT [--reason io_timeout] [--submit]: put files of the given reason (from qc/files.csv) into one extra
chunk chunk_rNNN of the CURRENT QC run; chunk records later override earlier ones in qc_merge.py."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, glob, os, subprocess
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--reason", default="io_timeout")
ap.add_argument("--submit", action="store_true")
a = ap.parse_args()
rd = layout.run_dir(a.mp, "qc")
paths = [r["path"] for r in csv.DictReader(open(f"{layout.qc_dir(a.mp)}/files.csv")) if a.reason in r["reasons"].split(";")]
if not paths:
    raise SystemExit(f"{a.mp}: no files with reason {a.reason}")
cid = "r%03d" % len(glob.glob(f"{rd}/lists/chunk_r*.txt"))
open(f"{rd}/lists/chunk_{cid}.txt", "w").write("\n".join(paths) + "\n")
open(f"{rd}/retry_ids.txt", "w").write(cid + "\n")
subprocess.run(["python3", f"{layout.REPO}/python/make_submit.py", a.mp, "--only", f"{rd}/retry_ids.txt"], check=True, stdout=subprocess.DEVNULL)
print(a.mp, cid, len(paths), "files")
if a.submit:
    subprocess.run(["condor_submit", f"{rd}/submit.sub"], check=True, stdout=subprocess.DEVNULL)
