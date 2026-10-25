#!/usr/bin/env python3
"""make_submit.py MASSPOINT [--chunk 20] [--only FILE]: QC condor run for one masspoint (strict source-file discovery).
New run dir results/<mp>/qc/runs/<run_id>/{lists,out,logs,params.json,submit.sub}; with --only reuses the current run and
queues just the chunk ids listed in FILE. Prints: <submit file> <n files> <n chunks> <run dir>"""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, json, os, time
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--chunk", type=int, default=20)
ap.add_argument("--only", help="file with chunk ids to (re)submit (current run), one per line")
a = ap.parse_args()

files = layout.source_files(a.mp)
if not files:
    raise SystemExit(f"no source files for {a.mp} under {layout.sample_dir(a.mp)}")
if a.only:
    run_id = layout.current_run(a.mp, "qc")
else:
    run_id = layout.new_run_id()
    layout.set_current_run(a.mp, "qc", run_id)
rd = layout.run_dir(a.mp, "qc", run_id)
for d in ("lists", "out", "logs"):
    os.makedirs(f"{rd}/{d}", exist_ok=True)
if a.only:
    ids = [x.strip() for x in open(a.only).read().split()]
    nchunks = len([f for f in os.listdir(f"{rd}/lists") if f.startswith("chunk_")])
else:
    chunks = [files[i:i + a.chunk] for i in range(0, len(files), a.chunk)]
    for i, c in enumerate(chunks):
        open(f"{rd}/lists/chunk_{i:03d}.txt", "w").write("\n".join(c) + "\n")
    ids = [f"{i:03d}" for i in range(len(chunks))]
    nchunks = len(chunks)
    json.dump(dict(stage="qc", masspoint=a.mp, run_id=run_id, created=time.strftime("%F %T"), n_files=len(files),
                   n_chunks=nchunks, chunk_size=a.chunk, input_digest=layout.source_digest(a.mp, files)),
              open(f"{rd}/params.json", "w"), indent=1)
sub = f"""universe = vanilla
executable = {layout.REPO}/scripts/run_qc.sh
arguments = {layout.REPO} {rd} $(chunk)
output = {rd}/logs/chunk_$(chunk).out
error = {rd}/logs/chunk_$(chunk).err
log = {rd}/logs/cluster.log
should_transfer_files = NO
getenv = False
request_cpus = 1
request_memory = 2 GB
+JobFlavour = "longlunch"
max_retries = 0
queue chunk from (
{chr(10).join(ids)}
)
"""
open(f"{rd}/submit.sub", "w").write(sub)
print(f"{rd}/submit.sub", len(files), "files", nchunks, "chunks", rd)
