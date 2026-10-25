#!/usr/bin/env python3
"""restore.py --log L [--apply]: move quarantined files back to their original place (refuses to overwrite)."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, os, sys
import layout
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--log", required=True)
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()
back, mp = [], None
for r in csv.DictReader(open(a.log)):
    if r["status"] != "quarantined":
        continue
    mp = r["masspoint"]
    if os.path.exists(r["src"]) or not os.path.isfile(r["dst"]):
        print("skip", r["src"][-50:], "(src exists or dst missing)")
        continue
    print("restore", r["src"][-60:])
    if a.apply:
        os.makedirs(os.path.dirname(r["src"]), exist_ok=True)
        rc, o = run(["mv", "--no-clobber", "--", r["dst"], r["src"]])
        if rc or not os.path.isfile(r["src"]):
            sys.exit("STOP: restore failed " + o)
        back.append(r["src"])
if back:  # drop restored paths from the masspoint's removed.txt (compare via realpath)
    p = layout.removed_file(mp)
    keep = [l for l in open(p) if os.path.realpath(l.strip()) not in back]
    open(p, "w").writelines(keep)
