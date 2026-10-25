"""Helpers shared by the quarantine tools (manifest, quarantine, restore, purge). Paths come from layout.py."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import csv, os, re, subprocess
import layout

REAL_SAMPLE_ROOT = os.path.realpath(layout.SAMPLE_ROOT)   # /pnfs/.../SampleFactory
PAT = r"[^/]+/%s/\d{8}_\d{6}/NanoAODv15_\d+\.root" % layout.CHAIN


def path_ok(rp, root):
    return re.fullmatch(re.escape(root.rstrip("/")) + "/" + PAT, rp) is not None


def run(cmd, t=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def locality(rp):
    """dCache locality of a file (ONLINE / NEARLINE / UNAVAILABLE ...) via the magic dot-file; metadata only."""
    d, b = os.path.split(rp)
    return run(["cat", f"{d}/.(get)({b})(locality)"], 30)[1]


def append_log(path, row, fields):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)
