#!/usr/bin/env python3
"""purge.py --log L --confirm-hash SHA256(log) [--apply]: PERMANENTLY unlink files that the log says are quarantined, only inside the quarantine dir."""
import argparse, csv, hashlib, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *
ap = argparse.ArgumentParser(); ap.add_argument("--log", required=True); ap.add_argument("--confirm-hash", required=True)
ap.add_argument("--apply", action="store_true"); ap.add_argument("--qc", default=QC); ap.add_argument("--root", default=ROOT)
a = ap.parse_args()
if hashlib.sha256(open(a.log, "rb").read()).hexdigest() != a.confirm_hash: sys.exit("REFUSED: log hash mismatch")
qroot = os.path.realpath(a.root) + "_quarantine/"
plog = a.log.replace("log_", "purge_")
F = ["dst", "size_bytes", "status"]; n = 0
for r in csv.DictReader(open(a.log)):
    if r["status"] != "quarantined": continue
    d = r["dst"]
    ok = d.startswith(qroot) and os.path.realpath(d) == d and os.path.isfile(d) and os.path.getsize(d) == int(r["size_bytes"])
    print("purge" if ok else "SKIP ", d[-70:])
    if ok and a.apply:
        os.unlink(d); n += 1
        append_log(plog, dict(dst=d, size_bytes=r["size_bytes"], status="purged"), F)
print("purged", n, "(dry-run)" if not a.apply else "")
