#!/usr/bin/env python3
"""purge_rnt.py - permanent removal of leftover test products, from an explicit, hashed plan (main session only, after user approval).

  purge_rnt.py plan <mp>                         write results/<mp>/rntuple/purge_<ts>.plan.csv (+ .sha256), delete nothing
  purge_rnt.py apply <plan.csv> --confirm-hash H [--apply]    dry-run unless --apply; log -> <plan>.log.csv
  purge_rnt.py sweep ROOT [--apply]              rmdir (never rm) empty directories below the superseded or quarantine root

Plan kinds (everything else is never touched; regular files only, no symlinks, one unlink per listed path, no globbing at delete time):
  superseded  RNTuple_superseded/<date>/<mp>/rntpl_NNN.root.<run id>          (outputs replaced by a newer conversion)
  pilot       RNTuple/<mp>/chain_RunIII2024Summer24/<ts>/NanoAODv15_<N>.root  (obsolete 1:1 layout of the first pilot)
  stray       SampleFactory_quarantine/<date>/<mp>/chain_RunIII2024Summer24/<ts>/NanoAODv15_.root  (quarantined stray test file)
After the files, plan directories (kind=dir: superseded date/mp dirs and the pilot chain dirs) are removed with os.rmdir only if empty.
Quarantined sources (logged by quarantine.py) are purged by purge.py, not here."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, hashlib, os, re, time
import layout
from common import append_log

F = ["kind", "path", "size_bytes"]
RE = {
    "superseded": re.compile(r"rntpl_\d{3,}\.root\.(run|val)_\d{8}_\d{6}"),
    "pilot": re.compile(r"NanoAODv15_\d+\.root"),
    "stray": re.compile(r"NanoAODv15_\.root"),
}


def regular(p):
    return os.path.isfile(p) and not os.path.islink(p)


def plan(mp):
    rows, dirs = [], []
    for d in sorted(os.listdir(layout.SUPERSEDED_ROOT)) if os.path.isdir(layout.SUPERSEDED_ROOT) else []:
        mdir = f"{layout.SUPERSEDED_ROOT}/{d}/{mp}"
        if os.path.isdir(mdir):
            for n in sorted(os.listdir(mdir)):
                p = f"{mdir}/{n}"
                if RE["superseded"].fullmatch(n) and regular(p):
                    rows.append(("superseded", p, os.path.getsize(p)))
                else:
                    raise SystemExit(f"unexpected entry in {mdir}: {n}")
            dirs += [mdir, f"{layout.SUPERSEDED_ROOT}/{d}"]
    chain = f"{layout.RNTUPLE_ROOT}/{mp}/{layout.CHAIN}"
    if os.path.isdir(chain):
        for ts in sorted(os.listdir(chain)):
            if not re.fullmatch(r"\d{8}_\d{6}", ts):
                raise SystemExit(f"unexpected entry in {chain}: {ts}")
            for n in sorted(os.listdir(f"{chain}/{ts}")):
                p = f"{chain}/{ts}/{n}"
                if RE["pilot"].fullmatch(n) and regular(p):
                    rows.append(("pilot", p, os.path.getsize(p)))
                else:
                    raise SystemExit(f"unexpected entry in {chain}/{ts}: {n}")
            dirs.append(f"{chain}/{ts}")
        dirs.append(chain)
    if os.path.isdir(layout.QUARANTINE_ROOT):
        for d in sorted(os.listdir(layout.QUARANTINE_ROOT)):
            for ts in (sorted(os.listdir(f"{layout.QUARANTINE_ROOT}/{d}/{mp}/{layout.CHAIN}"))
                       if os.path.isdir(f"{layout.QUARANTINE_ROOT}/{d}/{mp}/{layout.CHAIN}") else []):
                p = f"{layout.QUARANTINE_ROOT}/{d}/{mp}/{layout.CHAIN}/{ts}/NanoAODv15_.root"
                if regular(p):
                    rows.append(("stray", p, os.path.getsize(p)))
    rows += [("dir", d, 0) for d in dict.fromkeys(dirs)]
    return rows


def check_file(kind, p, size):
    rp = os.path.realpath(p)
    root = {"superseded": layout.SUPERSEDED_ROOT, "pilot": layout.RNTUPLE_ROOT, "stray": layout.QUARANTINE_ROOT}[kind]
    return (rp == p and p.startswith(os.path.realpath(root) + "/") and RE[kind].fullmatch(os.path.basename(p)) is not None
            and regular(p) and os.path.getsize(p) == size)


def sweep(root, apply):
    n = 0
    for dp, dn, fn in os.walk(root, topdown=False):
        if dp != root and not os.listdir(dp):
            print("rmdir" if apply else "would rmdir", dp[-90:])
            if apply:
                os.rmdir(dp)
            n += 1
    print(("removed " if apply else "would remove "), n, "empty directories")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "apply", "sweep"])
    ap.add_argument("arg")
    ap.add_argument("--confirm-hash")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.cmd == "plan":
        rows = plan(a.arg)
        out = f"{layout.rnt_dir(a.arg)}/purge_{time.strftime('%Y%m%d_%H%M%S')}.plan.csv"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(F)
            w.writerows(rows)
        h = hashlib.sha256(open(out, "rb").read()).hexdigest()
        open(out + ".sha256", "w").write(h + "\n")
        by = {}
        for k, _, s in rows:
            c = by.setdefault(k, [0, 0])
            c[0] += 1
            c[1] += s
        print(out, h)
        for k, (n, s) in by.items():
            print(f"  {k:10s} {n:4d}  {s / 2**30:.3f} GiB")
    elif a.cmd == "apply":
        if hashlib.sha256(open(a.arg, "rb").read()).hexdigest() != a.confirm_hash:
            raise SystemExit("REFUSED: plan hash mismatch")
        rows = list(csv.DictReader(open(a.arg)))
        lg = a.arg.replace(".plan.csv", ".log.csv")
        bad = [r for r in rows if r["kind"] != "dir" and not check_file(r["kind"], r["path"], int(r["size_bytes"]))]
        if bad:
            raise SystemExit("REFUSED: %d planned files failed the checks, e.g. %s" % (len(bad), bad[0]["path"]))
        n = 0
        for r in rows:
            if r["kind"] == "dir":
                continue
            if a.apply:
                os.unlink(r["path"])
                append_log(lg, dict(kind=r["kind"], path=r["path"], size_bytes=r["size_bytes"], status="purged"), F + ["status"])
            n += 1
        for r in sorted((r for r in rows if r["kind"] == "dir"), key=lambda r: -len(r["path"])):
            if os.path.isdir(r["path"]) and not os.listdir(r["path"]):
                if a.apply:
                    os.rmdir(r["path"])
                    append_log(lg, dict(kind="dir", path=r["path"], size_bytes=0, status="rmdir"), F + ["status"])
        print("purged" if a.apply else "dry-run: would purge", n, "files")
    else:
        root = os.path.realpath(a.arg)
        assert root in (os.path.realpath(layout.SUPERSEDED_ROOT), os.path.realpath(layout.QUARANTINE_ROOT)), root
        sweep(root, a.apply)
