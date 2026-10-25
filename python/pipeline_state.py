#!/usr/bin/env python3
"""pipeline_state.py {show|record} MASSPOINT [stage]: results/<mp>/pipeline.json = what has run for this masspoint and with which inputs.
record qc|convert|validate stores the current run id, timestamp and key numbers (from the stage's summary/params)."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import csv, json, os, sys, time
import layout


def path(mp):
    return f"{layout.mp_dir(mp)}/pipeline.json"


def read(mp):
    return json.load(open(path(mp))) if os.path.exists(path(mp)) else {"masspoint": mp}


def write(mp, d):
    d["updated"] = time.strftime("%F %T")
    os.makedirs(layout.mp_dir(mp), exist_ok=True)
    json.dump(d, open(path(mp) + ".tmp", "w"), indent=1)
    os.replace(path(mp) + ".tmp", path(mp))


def record(mp, stage):
    d = read(mp)
    now = time.strftime("%F %T")
    if stage == "qc":
        s = next(csv.DictReader(open(f"{layout.qc_dir(mp)}/summary.csv")))
        d["qc"] = dict(run_id=layout.current_run(mp, "qc"), recorded=now, n_files=int(s["n_files"]), n_files_corrupted=int(s["n_files_corrupted"]),
                       n_events_clean=int(s["n_events_clean"]), filter_efficiency=s["filter_efficiency"],
                       source_digest=layout.source_digest(mp))
    elif stage == "convert":
        rd = layout.run_dir(mp, "rntuple")
        p = json.load(open(f"{rd}/params.json"))
        d["convert"] = dict(run_id=p["run_id"], recorded=now, toolchain_digest=p["toolchain_digest"], manifest=p["manifest"], n_outputs=p["n_outputs"], n_sources=p["n_files"])
    elif stage == "validate":
        s = next(csv.DictReader(open(f"{layout.rnt_dir(mp)}/summary.csv")))
        d["validate"] = dict(run_id=layout.current_run(mp, "validate"), recorded=now, all_pass=int(s["all_pass"]), n_validated_ok=int(s["n_validated_ok"]),
                             events_rntuple=int(s["events_rntuple"]), size_ratio=s["size_ratio"])
    else:
        sys.exit("stage must be qc|convert|validate")
    write(mp, d)
    return d


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("show", "record"):
        sys.exit(__doc__)
    out = read(sys.argv[2]) if sys.argv[1] == "show" else record(sys.argv[2], sys.argv[3])
    print(json.dumps(out, indent=1))
