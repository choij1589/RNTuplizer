#!/usr/bin/env python3
"""make_submit.py MASSPOINT [--root DIR] [--chunk 20] [--sample-root ...]; writes results/MP/.work and submit.sub, prints the .sub path"""
import argparse, glob, os
ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--qc", default="/d0/scratch/choij/SampleFactoryQC")
ap.add_argument("--samples", default="/u/user/choij/SE_UserHome/SampleFactory")
ap.add_argument("--chunk", type=int, default=20)
ap.add_argument("--only", help="file with chunk ids to (re)submit, one per line")
a = ap.parse_args()
work = f"{a.qc}/results/{a.mp}/.work"
for d in ("lists", "out", "log"):
    os.makedirs(f"{work}/{d}", exist_ok=True)
files = sorted(glob.glob(f"{a.samples}/{a.mp}/**/*.root", recursive=True))
if not files:
    raise SystemExit(f"no root files for {a.mp}")
chunks = [files[i:i + a.chunk] for i in range(0, len(files), a.chunk)]
for i, c in enumerate(chunks):
    open(f"{work}/lists/chunk_{i:03d}.txt", "w").write("\n".join(c) + "\n")
ids = [int(x) for x in open(a.only).read().split()] if a.only else range(len(chunks))
runner = f"{a.qc}/.claude/skills/qc-condor/scripts/run_qc.sh"
sub = f"""universe = vanilla
executable = {runner}
arguments = {a.qc} {work} $(chunk)
output = {work}/log/chunk_$(chunk).out
error = {work}/log/chunk_$(chunk).err
log = {work}/log/cluster.log
should_transfer_files = NO
getenv = False
request_cpus = 1
request_memory = 2 GB
+JobFlavour = "longlunch"
max_retries = 0
queue chunk from (
{chr(10).join(f"{i:03d}" for i in ids)}
)
"""
open(f"{work}/submit.sub", "w").write(sub)
print(f"{work}/submit.sub", len(files), "files", len(chunks), "chunks")
