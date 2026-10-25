import csv, os, re, subprocess
ROOT = "/pnfs/knu.ac.kr/data/cms/store/user/choij/SampleFactory"
QC = "/d0/scratch/choij/SampleFactoryQC"
PAT = r"[^/]+/chain_RunIII2024Summer24/\d{8}_\d{6}/NanoAODv15_\d+\.root"


def path_ok(rp, root):
    return re.fullmatch(re.escape(root.rstrip("/")) + "/" + PAT, rp) is not None


def run(cmd, t=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def locality(rp):
    d, b = os.path.split(rp)
    return run(["cat", f"{d}/.(get)({b})(locality)"], 30)[1]


def append_log(path, row, fields):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new: w.writeheader()
        w.writerow(row)
