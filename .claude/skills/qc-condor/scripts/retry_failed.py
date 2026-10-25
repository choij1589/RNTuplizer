#!/usr/bin/env python3
"""retry_failed.py [--reason io_timeout] [--submit]: for each masspoint, put files with that reason in files.csv into one extra
chunk (lists/chunk_rNNN.txt). aggregate.py lets later chunk files (r*) override earlier records for the same path."""
import argparse, csv, glob, os, subprocess
ap = argparse.ArgumentParser()
ap.add_argument("--reason", default="io_timeout")
ap.add_argument("--qc", default="/d0/scratch/choij/SampleFactoryQC")
ap.add_argument("--submit", action="store_true")
a = ap.parse_args()
runner = f"{a.qc}/.claude/skills/qc-condor/scripts/run_qc.sh"
for f in sorted(glob.glob(f"{a.qc}/results/*/files.csv")):
    res = os.path.dirname(f); work = f"{res}/.work"
    paths = [r["path"] for r in csv.DictReader(open(f)) if a.reason in r["reasons"].split(";")]
    if not paths:
        continue
    n = len(glob.glob(f"{work}/lists/chunk_r*.txt"))
    cid = f"r{n:03d}"
    open(f"{work}/lists/chunk_{cid}.txt", "w").write("\n".join(paths) + "\n")
    sub = f"""universe = vanilla
executable = {runner}
arguments = {a.qc} {work} {cid}
output = {work}/log/chunk_{cid}.out
error = {work}/log/chunk_{cid}.err
log = {work}/log/cluster.log
should_transfer_files = NO
getenv = False
request_cpus = 1
request_memory = 2 GB
+JobFlavour = "longlunch"
max_retries = 0
queue
"""
    open(f"{work}/retry_{cid}.sub", "w").write(sub)
    print(os.path.basename(res)[-45:-26], cid, len(paths), "files")
    if a.submit:
        subprocess.run(["condor_submit", f"{work}/retry_{cid}.sub"], check=True, stdout=subprocess.DEVNULL)
