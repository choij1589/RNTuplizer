#!/usr/bin/env python3
"""rnt_aggregate.py MASSPOINT: merge the per-output records of the current conversion run into results/<mp>/rntuple/conversion.csv
(one row per OUTPUT file, accumulating over runs; the newer record of an output wins) and write rntuple/groups.csv (provenance: which
sources went into which output). Exit 2 if outputs of the run have no record yet."""
import sys; sys.dont_write_bytecode = True
import argparse, csv, glob, json, os
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
a = ap.parse_args()
rn = layout.rnt_dir(a.mp)
rd = layout.run_dir(a.mp, "rntuple")
params = json.load(open(f"{rd}/params.json"))
man = list(csv.DictReader(open(params["manifest"])))
by_out = {}
for r in man:
    by_out.setdefault(r["output"], []).append(r)
cp = f"{rn}/conversion.csv"
F = ["output", "status", "n_sources", "group_digest", "events_expected", "events_entries", "input_bytes", "output_bytes", "trees_converted", "trees_skipped",
     "branches_kept", "branches_dropped", "toolchain_digest", "root_version", "run_id", "seconds", "superseded", "error"]
rows = {r["output"]: r for r in csv.DictReader(open(cp))} if os.path.exists(cp) else {}
expected, got = set(), set()
for f in glob.glob(f"{rd}/lists/chunk_*.txt"):
    expected |= {l.split("\t")[0] for l in open(f) if l.strip()}
for f in sorted(glob.glob(f"{rd}/out/chunk_*.jsonl")):
    for line in open(f):
        j = json.loads(line)
        o = j["output"]
        src = by_out.get(o, [])
        ev = next((t for t in j["trees"] if t["name"] == "Events"), {})
        ok = j["ok"] and j["copied"]
        rows[o] = dict(
            output=o, status="ok" if ok else "failed", n_sources=len(j["inputs"]), group_digest=src[0]["group_digest"] if src else "",
            events_expected=sum(int(x["events"]) for x in src), events_entries=ev.get("entries", -1),
            input_bytes=sum(int(x["size_bytes"]) for x in src), output_bytes=j["out_bytes"] if ok else -1,
            trees_converted=";".join(t["name"] for t in j["trees"] if t["status"] == "converted"),
            trees_skipped=";".join(f"{t['name']}({t['reason']})" for t in j["trees"] if t["status"] == "skipped") + (";" if j["not_trees"] else "") + ";".join(f"{x['name']}({x['class']})" for x in j["not_trees"]),
            branches_kept=ev.get("kept", -1), branches_dropped=ev.get("dropped", -1), toolchain_digest=params["toolchain_digest"],
            root_version=j["root_version"], run_id=params["run_id"], seconds=round(j["seconds"], 2), superseded=j.get("superseded", ""),
            error=(j["error"] or j["note"] or j["stderr_tail"]).replace("\n", " ")[:200] if not ok else "")
        got.add(o)
with open(cp, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=F)
    w.writeheader()
    w.writerows(rows[k] for k in sorted(rows))
# provenance table for all outputs of the current plan that are converted ok
with open(f"{rn}/groups.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["output", "input", "events", "size_bytes", "mtime"])
    for o in sorted(by_out):
        if rows.get(o, {}).get("status") == "ok" and o:
            for x in by_out[o]:
                w.writerow([o, x["input"], x["events"], x["size_bytes"], x["mtime"]])
missing = sorted(expected - got)
n_ok = sum(1 for o in got if rows.get(o, {}).get("status") == "ok")
print(f"{a.mp}: run {params['run_id']}: expected {len(expected)} outputs, recorded {len(got)}, ok {n_ok}, failed {len(got) - n_ok}, missing {len(missing)} -> {cp}")
sys.exit(2 if missing else 0)
