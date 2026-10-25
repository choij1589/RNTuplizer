#!/usr/bin/env python3
"""Single source of truth for every path in this repository.

Roots can be overridden with environment variables so tests can run in a sandbox:
RNT_REPO, RNT_RESULTS, RNT_CONFIG, RNT_PNFS, RNT_SAMPLES, RNT_QUARANTINE, RNT_RNTUPLE.
Works with the system python (no ROOT needed).

Shell use:  python3 python/layout.py <name> <mp> [stage]   (see COMMANDS below)
"""
import sys
sys.dont_write_bytecode = True   # (tools also set it before importing us - the flag is read when a module is loaded)
import glob
import hashlib
import os
import re
import time

REPO = os.environ.get("RNT_REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.environ.get("RNT_RESULTS") or f"{REPO}/results"
CONFIG = os.environ.get("RNT_CONFIG") or f"{REPO}/config"
PNFS = os.environ.get("RNT_PNFS") or "/pnfs/knu.ac.kr/data/cms/store/user/choij"
SAMPLE_ROOT = os.environ.get("RNT_SAMPLES") or "/u/user/choij/SE_UserHome/SampleFactory"  # path form used in all reports
QUARANTINE_ROOT = os.environ.get("RNT_QUARANTINE") or f"{PNFS}/SampleFactory_quarantine"
RNTUPLE_ROOT = os.environ.get("RNT_RNTUPLE") or f"{PNFS}/RNTuple"
SUPERSEDED_ROOT = os.environ.get("RNT_SUPERSEDED") or f"{PNFS}/RNTuple_superseded"   # replaced outputs are renamed here, never deleted
CHAIN = "chain_RunIII2024Summer24"
STAGES = ("qc", "rntuple", "validate")   # "validate" runs live beside the conversion runs in results/<mp>/rntuple/runs/

# <root>/<mp>/chain_RunIII2024Summer24/<ts>/NanoAODv15_<N>.root  (strict: digits only, so e.g. NanoAODv15_.root never matches)
SRC_RE = re.compile(r"^(?P<root>.*)/(?P<mp>[^/]+)/%s/(?P<ts>\d{8}_\d{6})/NanoAODv15_(?P<n>\d+)\.root$" % CHAIN)


# ---- results (repo-local, everything about one masspoint lives in results/<mp>/) -------------------------------
def mp_dir(mp):
    return f"{RESULTS}/{mp}"


def stage_dir(mp, stage):
    assert stage in STAGES, stage
    return f"{RESULTS}/{mp}/{'rntuple' if stage == 'validate' else stage}"


def qc_dir(mp):
    return stage_dir(mp, "qc")


def rnt_dir(mp):
    return stage_dir(mp, "rntuple")


def deletion_dir(mp):
    return f"{qc_dir(mp)}/deletion"


def runs_dir(mp, stage):
    return f"{stage_dir(mp, stage)}/runs"


def run_dir(mp, stage, run_id=None):
    return f"{runs_dir(mp, stage)}/{run_id or current_run(mp, stage)}"


def new_run_id(prefix="run"):
    return prefix + "_" + time.strftime("%Y%m%d_%H%M%S")


def _pointer(mp, stage):
    return f"{stage_dir(mp, stage)}/current_run" + ("_validate" if stage == "validate" else "")


def current_run(mp, stage):
    p = _pointer(mp, stage)
    if not os.path.exists(p):
        raise SystemExit(f"no current {stage} run for {mp} ({p} missing)")
    return open(p).read().strip()


def set_current_run(mp, stage, run_id):
    os.makedirs(stage_dir(mp, stage), exist_ok=True)
    with open(_pointer(mp, stage), "w") as fh:
        fh.write(run_id + "\n")


def exclude_file(mp):
    return f"{qc_dir(mp)}/exclude.txt"


def removed_file(mp):
    return f"{qc_dir(mp)}/removed.txt"


def read_list(path):
    """Non-empty, non-comment lines of a text file ([] if missing)."""
    if not os.path.exists(path):
        return []
    return [l.strip() for l in open(path) if l.strip() and not l.lstrip().startswith("#")]


# ---- samples (data on /pnfs) ---------------------------------------------------------------------------------
def sample_dir(mp):
    return f"{SAMPLE_ROOT}/{mp}"


def masspoints():
    return sorted(d for d in os.listdir(SAMPLE_ROOT) if os.path.isdir(f"{SAMPLE_ROOT}/{d}"))


def source_files(mp):
    """All source files of a masspoint (strict pattern, sorted). Never matches RNTuple/, quarantine or stray names."""
    out = []
    for p in sorted(glob.glob(f"{sample_dir(mp)}/{CHAIN}/*/NanoAODv15_*.root")):
        if SRC_RE.match(p):
            out.append(p)
    return out


def source_digest(mp, files=None):
    """sha256 over sorted 'path size mtime' of the given (default: all) source files; detects any change of the input set."""
    h = hashlib.sha256()
    for p in sorted(files if files is not None else source_files(mp)):
        st = os.stat(p)
        h.update(f"{p} {st.st_size} {int(st.st_mtime)}\n".encode())
    return h.hexdigest()


def src_key(path):
    """Sort key of a source file: (timestamp dir, job number N) - numeric N, so NanoAODv15_9 sorts before NanoAODv15_10."""
    m = SRC_RE.match(path)
    if not m:
        raise ValueError(f"not a source file path: {path}")
    return (m["ts"], int(m["n"]))


OUT_PREFIX = "rntpl_"   # converted outputs are named rntpl_NNN.root


def rntuple_part(mp, idx):
    """Converted output no. idx of a masspoint: <RNTuple root>/<mp>/rntpl_NNN.root (several source files merged)."""
    return f"{RNTUPLE_ROOT}/{mp}/{OUT_PREFIX}{idx:03d}.root"


def output_index(filename):
    """Index NNN of a converted output file name (rntpl_NNN.root) or None for any other name (e.g. staging files .part.<pid>)."""
    m = re.fullmatch(re.escape(OUT_PREFIX) + r"(\d{3,})\.root", os.path.basename(filename))
    return int(m.group(1)) if m else None


def superseded_dst(out, run_id, date=None):
    """Where a replaced output is moved: <SUPERSEDED_ROOT>/<date>/<mp>/<file>.<run id> (rename only; purge is a separate approved step)."""
    return f"{SUPERSEDED_ROOT}/{date or time.strftime('%Y%m%d')}/{os.path.basename(os.path.dirname(out))}/{os.path.basename(out)}.{run_id}"


def output_conf():
    """config/rntuple_output.conf as a dict (COMPRESSION, TARGET_EVENTS)."""
    d = {}
    for l in read_list(f"{CONFIG}/rntuple_output.conf"):
        if "=" in l:
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def quarantine_dst(real_src, date=None, root=None):
    """Destination of a quarantined file: <quarantine root>/<date>/<mp>/chain/.../file (same relative path as the source)."""
    m = SRC_RE.match(real_src)
    if not m:
        raise ValueError(f"not a source file path: {real_src}")
    return f"{QUARANTINE_ROOT}/{date or time.strftime('%Y%m%d')}/{m['mp']}/{CHAIN}/{m['ts']}/NanoAODv15_{m['n']}.root"


# ---- pinned toolchain config -----------------------------------------------------------------------------------
def env_conf():
    """config/rntuple_env.conf as a dict (KEY=VALUE lines)."""
    d = {}
    for l in read_list(f"{CONFIG}/rntuple_env.conf"):
        if "=" in l:
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip()
    return d


COMMANDS = {
    "superseded-dst": lambda mp, st: superseded_dst(mp, st),   # args: <output path> <run id>
    "mp-dir": lambda mp, st: mp_dir(mp),
    "stage-dir": lambda mp, st: stage_dir(mp, st),
    "run-dir": lambda mp, st: run_dir(mp, st),
    "current-run": lambda mp, st: current_run(mp, st),
    "deletion-dir": lambda mp, st: deletion_dir(mp),
    "sample-dir": lambda mp, st: sample_dir(mp),
    "masspoints": lambda mp, st: "\n".join(masspoints()),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit("usage: layout.py {%s} [mp] [stage]" % "|".join(COMMANDS))
    print(COMMANDS[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else "qc"))
