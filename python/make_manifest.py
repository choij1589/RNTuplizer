#!/usr/bin/env python3
"""make_manifest.py MASSPOINT [--min-healthy 300000]: manifest of every corrupted=1 row of results/<mp>/qc/files.csv
(metadata only; never reads file data). Writes results/<mp>/qc/deletion/manifest_<ts>.csv + .sha256 and prints the guard
line. Exit 3 if the masspoint would drop below --min-healthy, exit 4 if nothing is corrupted."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, hashlib, os, subprocess, sys, time
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--min-healthy", type=int, default=300000)
a = ap.parse_args()


def sh(cmd, t=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


qd = layout.qc_dir(a.mp)
healthy = int(next(csv.DictReader(open(f"{qd}/summary.csv")))["n_events_clean"])
rows = []
for r in csv.DictReader(open(f"{qd}/files.csv")):
    if r["corrupted"] != "1":
        continue
    rp = os.path.realpath(r["path"])
    d, b = os.path.split(rp)
    st = sh(["stat", "-c", "%s %Y", rp]).split()
    rows.append(dict(path=r["path"], realpath=rp, masspoint=a.mp, reason=r["reasons"],
                     size_bytes=st[0] if len(st) == 2 else "", mtime=st[1] if len(st) == 2 else "",
                     locality=sh(["cat", f"{d}/.(get)({b})(locality)"]), healthy_events_after=healthy))
if not rows:
    print(f"{a.mp}: no corrupted files")
    sys.exit(4)
os.makedirs(layout.deletion_dir(a.mp), exist_ok=True)
m = f"{layout.deletion_dir(a.mp)}/manifest_{time.strftime('%Y%m%d_%H%M%S')}.csv"
with open(m, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
h = hashlib.sha256(open(m, "rb").read()).hexdigest()
open(m + ".sha256", "w").write(h + "\n")
print(m, "\nsha256", h, "\nrows", len(rows), "total_bytes", sum(int(r["size_bytes"] or 0) for r in rows))
flag = "" if healthy >= a.min_healthy else "  <-- BELOW GUARD"
print(f"{a.mp}: remove={len(rows)} healthy_after={healthy}{flag}")
sys.exit(3 if flag else 0)
