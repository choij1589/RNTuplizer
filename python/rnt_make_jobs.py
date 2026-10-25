#!/usr/bin/env python3
"""rnt_make_jobs.py MASSPOINT (--manifest M | --validate [--only-failed] | --only IDS) : condor run for the conversion or the validation
of one masspoint (results/<mp>/rntuple/runs/<run_id>/{lists,out,logs,params.json,submit.sub}).
convert : one job per group to convert/reconvert (list line: OUTPUT <tab> INPUT1 <tab> INPUT2 ...). Refuses a manifest whose sha256 or
          source files changed, or that contains conflicts.
validate: every converted output with status ok (or only those without a passing, current validation with --only-failed); 3 groups per job.
--only FILE re-queues just the listed chunk ids of the current run (stage chosen with --validate). Exit 3 = nothing to do.
Prints: <submit file> <n outputs> <n chunks> <run dir>"""
import sys; sys.dont_write_bytecode = True
import argparse, csv, glob, hashlib, json, os, time
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--manifest")
ap.add_argument("--only")
ap.add_argument("--validate", action="store_true")
ap.add_argument("--only-failed", action="store_true")
a = ap.parse_args()
STAGE = "validate" if a.validate else "rntuple"
rn = layout.rnt_dir(a.mp)


def read_manifest(path):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if open(path + ".sha256").read().strip() != h:
        sys.exit("REFUSED: manifest sha256 does not match its .sha256 file")
    rows = list(csv.DictReader(open(path)))
    groups = {}
    for r in rows:
        groups.setdefault(r["output"], []).append(r)
    return h, rows, groups


def latest_manifest():
    ms = sorted(glob.glob(f"{rn}/manifest_*.csv"))
    if not ms:
        sys.exit("no manifest; run rnt_make_manifest.py first")
    return ms[-1]


if a.only:
    run_id = layout.current_run(a.mp, STAGE)
    rd = layout.run_dir(a.mp, STAGE, run_id)
    ids = [x.strip() for x in open(a.only).read().split()]
    n_out = n_ch = None
else:
    if a.validate:
        mpath = latest_manifest()
        h, rows, groups = read_manifest(mpath)
        conv = {r["output"]: r for r in csv.DictReader(open(f"{rn}/conversion.csv"))}
        vp = f"{rn}/validation.csv"
        passed = set()
        if a.only_failed and os.path.exists(vp):
            passed = {r["output"] for r in csv.DictReader(open(vp)) if r["ok"] == "1" and conv.get(r["output"], {}).get("group_digest") == r["group_digest"]}
        todo = [o for o in groups if o not in passed and conv.get(o, {}).get("status") == "ok"]
        for o in todo:
            if not os.path.exists(o):
                sys.exit(f"REFUSED: converted output missing: {o}")
        per_chunk, kind, digest = 3, "validate", rows[0]["toolchain_digest"]
    else:
        if not a.manifest:
            sys.exit("--manifest required")
        mpath = a.manifest
        h, rows, groups = read_manifest(mpath)
        if any(r["action"] == "conflict" for r in rows):
            sys.exit("REFUSED: manifest contains conflicts")
        for r in rows:
            if r["input"]:
                st = os.stat(r["input"])
                if str(st.st_size) != r["size_bytes"] or str(int(st.st_mtime)) != r["mtime"]:
                    sys.exit(f"REFUSED: source changed since the manifest was made: {r['input']}")
        todo = [o for o, rs in groups.items() if rs[0]["action"] in ("convert", "reconvert-stale")]
        per_chunk, kind, digest = 1, "convert", rows[0]["toolchain_digest"]
    if not todo:
        print("nothing to do")
        sys.exit(3)
    run_id = layout.new_run_id("val" if a.validate else "run")
    layout.set_current_run(a.mp, STAGE, run_id)
    rd = layout.run_dir(a.mp, STAGE, run_id)
    for d in ("lists", "out", "logs"):
        os.makedirs(f"{rd}/{d}", exist_ok=True)
    chunks = [todo[i:i + per_chunk] for i in range(0, len(todo), per_chunk)]
    ids = []
    for ci, outs in enumerate(chunks):
        cid = "%03d" % ci
        ids.append(cid)
        with open(f"{rd}/lists/chunk_{cid}.txt", "w") as fh:
            for o in outs:
                fh.write("\t".join([o] + [r["input"] for r in groups[o]]) + "\n")
    n_out, n_ch = len(todo), len(chunks)
    json.dump(dict(stage=kind, masspoint=a.mp, run_id=run_id, created=time.strftime("%F %T"), manifest=mpath, manifest_sha256=h,
                   n_outputs=n_out, n_chunks=n_ch, n_files=sum(len(groups[o]) for o in todo), toolchain_digest=digest),
              open(f"{rd}/params.json", "w"), indent=1)
table = f"{rn}/branch_selection.csv"
sub = f"""universe = vanilla
executable = {layout.REPO}/scripts/{"rnt_validate.sh" if a.validate else "rnt_convert.sh"}
arguments = {layout.REPO} {rd} $(chunk) {table}
output = {rd}/logs/chunk_$(chunk).out
error = {rd}/logs/chunk_$(chunk).err
log = {rd}/logs/cluster.log
should_transfer_files = NO
getenv = False
# workers do not inherit the caller's RNT_* overrides
environment = "RNT_SUPERSEDED={layout.SUPERSEDED_ROOT}"
request_cpus = 1
request_memory = 4 GB
+JobFlavour = "longlunch"
max_retries = 0
# a stalled worker (disk/IO) must not block a chunk forever: remove after 1 h, the driver resubmits the chunk
periodic_remove = (JobStatus == 2) && ((time() - JobCurrentStartDate) > 3600)
queue chunk from (
{chr(10).join(ids)}
)
"""
open(f"{rd}/submit.sub", "w").write(sub)
print(f"{rd}/submit.sub", n_out, "outputs", n_ch or len(ids), "chunks", rd)
