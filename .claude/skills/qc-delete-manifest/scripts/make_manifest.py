#!/usr/bin/env python3
"""make_manifest.py [--min-healthy 300000]: manifest of every corrupted=1 row of results/*/files.csv (metadata only; never reads file data).
Writes results/deletion/manifest_<ts>.csv + .sha256 and prints the guard table. Exit 3 if a masspoint would drop below --min-healthy."""
import argparse, csv, glob, hashlib, os, subprocess, sys, time
ap = argparse.ArgumentParser()
ap.add_argument("--qc", default="/d0/scratch/choij/SampleFactoryQC")
ap.add_argument("--min-healthy", type=int, default=300000)
a = ap.parse_args()


def sh(cmd, t=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


rows, guard = [], {}
for f in sorted(glob.glob(f"{a.qc}/results/*/files.csv")):
    mp = os.path.basename(os.path.dirname(f))
    s = next(csv.DictReader(open(f"{os.path.dirname(f)}/summary.csv")))
    guard[mp] = int(s["n_events_clean"])
    for r in csv.DictReader(open(f)):
        if r["corrupted"] != "1":
            continue
        rp = os.path.realpath(r["path"])
        d, b = os.path.split(rp)
        st = sh(["stat", "-c", "%s %Y", rp]).split()
        loc = sh(["cat", f"{d}/.(get)({b})(locality)"])
        rows.append(dict(path=r["path"], realpath=rp, masspoint=mp, reason=r["reasons"],
                         size_bytes=st[0] if len(st) == 2 else "", mtime=st[1] if len(st) == 2 else "",
                         locality=loc, healthy_events_after=guard[mp]))
os.makedirs(f"{a.qc}/results/deletion", exist_ok=True)
ts = time.strftime("%Y%m%d_%H%M%S")
m = f"{a.qc}/results/deletion/manifest_{ts}.csv"
with open(m, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
h = hashlib.sha256(open(m, "rb").read()).hexdigest()
open(m + ".sha256", "w").write(h + "\n")
print(m, "\nsha256", h, "\nrows", len(rows), "total_bytes", sum(int(r["size_bytes"] or 0) for r in rows))
bad = []
for mp, n in guard.items():
    k = [r for r in rows if r["masspoint"] == mp]
    flag = "" if n >= a.min_healthy else "  <-- BELOW GUARD"
    if flag: bad.append(mp)
    print(f"{mp.split('MA-')[1].split('_')[0]:>4} remove={len(k)} healthy_after={n}{flag}")
sys.exit(3 if bad else 0)
