#!/usr/bin/env python3
"""quarantine.py --manifest M --confirm-hash SHA [--apply] [--canary] [--root R] [--qdir Q]
Dry-run by default. Moves (rename, metadata-only) manifest files into the quarantine dir after hard per-file checks. Never deletes."""
import argparse, csv, hashlib, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *
ap = argparse.ArgumentParser()
ap.add_argument("--manifest", required=True)
ap.add_argument("--confirm-hash", required=True)
ap.add_argument("--apply", action="store_true")
ap.add_argument("--canary", action="store_true", help="only the first eligible file")
ap.add_argument("--root", default=ROOT)
ap.add_argument("--qdir", help="default: <root>_quarantine/<YYYYMMDD>")
ap.add_argument("--qc", default=QC)
ap.add_argument("--no-condor-check", action="store_true")
a = ap.parse_args()
a.root = os.path.realpath(a.root)
if hashlib.sha256(open(a.manifest, "rb").read()).hexdigest() != a.confirm_hash:
    sys.exit("REFUSED: manifest hash != --confirm-hash")
if not a.no_condor_check and run(["condor_q", os.environ.get("USER", "choij"), "-af", "ClusterId"], 60)[1]:
    sys.exit("REFUSED: condor jobs are queued")
qdir = a.qdir or f"{a.root}_quarantine/{time.strftime('%Y%m%d')}"
ts = time.strftime("%Y%m%d_%H%M%S")
logp = f"{a.qc}/results/deletion/log_{ts}.csv"
os.makedirs(os.path.dirname(logp), exist_ok=True)
F = ["manifest", "src", "dst", "masspoint", "reason", "size_bytes", "status"]
chk = f"{a.qc}/.claude/skills/qc-check-rootfile/scripts/check_file.py"
envs = f"{a.qc}/.claude/skills/qc-env/scripts/env.sh"
done = 0
for r in csv.DictReader(open(a.manifest)):
    rp = r["realpath"]; dst = f"{qdir}/{os.path.relpath(rp, a.root)}" if rp.startswith(a.root) else ""
    def out(status):
        print(f"{status:<40} {rp[-60:]}")
        if a.apply: append_log(logp, dict(manifest=a.manifest, src=rp, dst=dst, masspoint=r["masspoint"], reason=r["reason"], size_bytes=r["size_bytes"], status=status), F)
        return status
    if a.canary and done >= 1: break
    if not path_ok(rp, a.root): out("skipped:path_pattern"); continue
    if os.path.islink(rp) or os.path.realpath(rp) != rp: out("skipped:symlink"); continue
    if not os.path.isfile(rp): out("skipped:not_a_file"); continue
    st = os.stat(rp)
    if str(st.st_size) != r["size_bytes"] or str(int(st.st_mtime)) != r["mtime"]: out("skipped:changed_since_qc"); continue
    if os.path.exists(dst): out("skipped:dst_exists"); continue
    if "io_timeout" in r["reason"]:
        loc = locality(rp)
        if loc != "UNAVAILABLE": out(f"skipped:locality={loc[:20]}"); continue  # recovered or unknown: re-QC instead
    else:
        rc, o = run(["bash", "-c", f"source {envs} >/dev/null 2>&1; python3 {chk} /tmp/_q.json {rp} && python3 -c \"import json;r=json.load(open('/tmp/_q.json'))[0];print(int(r['corrupted'] or r['gen_passed']>r['n_events']))\""], 900)
        if o.splitlines()[-1:] != ["1"]: out("skipped:recheck_not_bad"); continue
    if not a.apply: out("would_quarantine"); done += 1; continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    rc, o = run(["mv", "--no-clobber", "--", rp, dst], 60)
    if rc or os.path.exists(rp) or not os.path.isfile(dst) or os.path.getsize(dst) != int(r["size_bytes"]):
        out(f"failed:{o[:30]}"); sys.exit("STOP: verification failed after move; investigate before continuing")
    out("quarantined"); done += 1
    with open(f"{a.qc}/config/removed.txt", "a") as fh: fh.write(r["path"] + "\n")
print("log:" if a.apply else "(dry-run, nothing changed)", logp if a.apply else "", "files:", done)
