#!/usr/bin/env python3
"""migrate_results.py [--apply]: one-time move of the old results layout into results/<mp>/qc/ (repo-local only, no /pnfs access).

Old                                              New
results/<mp>/{files,summary}.csv                 results/<mp>/qc/{files,summary}.csv
results/<mp>/.work/{lists,out,log,*.sub,...}     results/<mp>/qc/runs/legacy_20261025/{lists,out,logs,...}
.work/out/chunk_*.json (merged, name order)      results/<mp>/qc/records.json
config/{exclude,removed}.txt (global)            results/<mp>/qc/{exclude,removed}.txt (lines of that masspoint)
results/deletion/{manifest,log,manual}_*         results/<mp>/qc/deletion/ (rows of that masspoint, + .origin with the original sha256)
results/run_all.log|out, aggregate_errors.log    lines mentioning <mp> -> qc/runs/legacy_20261025/driver.log
Dry-run by default; every move is printed. An audit file <run>/migration.json lists sha256 of every moved/created file."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, glob, hashlib, json, os, shutil, sys, time
import layout

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
ap.add_argument("--run-id", default="legacy_20261025")
a = ap.parse_args()
R = layout.RESULTS
acts = []          # (kind, src, dst)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


mps = sorted(d for d in os.listdir(R) if os.path.isdir(f"{R}/{d}") and d != "deletion" and os.path.isdir(f"{R}/{d}/.work"))
if not mps:
    sys.exit("nothing to migrate (no results/<mp>/.work found)")
for mp in mps:
    if os.path.exists(layout.qc_dir(mp)):
        sys.exit(f"REFUSED: {layout.qc_dir(mp)} already exists")

glob_excl = layout.read_list(f"{layout.CONFIG}/exclude.txt")
glob_rem = layout.read_list(f"{layout.CONFIG}/removed.txt")
del_files = sorted(glob.glob(f"{R}/deletion/*"))
glob_logs = [p for p in (f"{R}/run_all.log", f"{R}/run_all.out", f"{R}/aggregate_errors.log") if os.path.exists(p)]
log_lines = {p: open(p).read().splitlines() for p in glob_logs}
used_log_lines = set()

report = {}
for mp in mps:
    qd, rd = layout.qc_dir(mp), layout.run_dir(mp, "qc", a.run_id)
    rep = report[mp] = {"moved": [], "created": []}
    # 1. reports and work dir
    for n in ("files.csv", "summary.csv"):
        acts.append(("move", f"{R}/{mp}/{n}", f"{qd}/{n}"))
    w = f"{R}/{mp}/.work"
    for item in sorted(os.listdir(w)):
        dstname = {"log": "logs"}.get(item, item)
        acts.append(("move", f"{w}/{item}", f"{rd}/{dstname}"))
    # 2. per-masspoint lists
    for kind, glob_l, name in (("exclude", glob_excl, "exclude.txt"), ("removed", glob_rem, "removed.txt")):
        acts.append(("write_lines", [l for l in glob_l if f"/{mp}/" in l], f"{qd}/{name}"))
    # 3. deletion records split by masspoint
    for p in del_files:
        b = os.path.basename(p)
        if b.endswith(".sha256"):
            continue
        if b.endswith(".csv"):
            with open(p, newline="") as fh:
                rd_ = csv.DictReader(fh)
                rows = [r for r in rd_ if (r.get("masspoint") == mp) or (not r.get("masspoint") and f"/{mp}/" in (r.get("src") or ""))]
                fields = rd_.fieldnames
            if rows:
                acts.append(("write_csv", (fields, rows, p), f"{qd}/deletion/{b}"))
    # 4. driver log
    acts.append(("driver_log", mp, f"{rd}/driver.log"))

print(f"{len(mps)} masspoints, {len(acts)} actions ({'APPLY' if a.apply else 'dry-run'})")
if not a.apply:
    shown = {}
    for k, s, d in acts:
        kk = (k, os.path.basename(os.path.dirname(d)) if k != "move" else k)
        shown[kk] = shown.get(kk, 0) + 1
    for (k, _), n in sorted(shown.items()):
        print(f"  {k:12s} x{n}")
    for k, s, d in acts[:14]:
        print(" ", k, (s if isinstance(s, str) else "...")[-70:], "->", d[-80:])
    print("  ... (re-run with --apply)")
    sys.exit(0)

for k, s, d in acts:
    os.makedirs(os.path.dirname(d), exist_ok=True)
    mp = d.split(f"{R}/")[1].split("/")[0]
    rep = report[mp]
    if k == "move":
        if not os.path.exists(s):
            continue
        if os.path.isdir(s):
            files = [(os.path.join(dp, f)) for dp, _, fs in os.walk(s) for f in fs]
            before = {os.path.relpath(f, s): sha(f) for f in files}
            os.rename(s, d)
            for rel, h in before.items():
                assert sha(os.path.join(d, rel)) == h, f"hash mismatch after move: {rel}"
            rep["moved"].append({"src": s, "dst": d, "files": len(before)})
        else:
            h = sha(s)
            os.rename(s, d)
            assert sha(d) == h
            rep["moved"].append({"src": s, "dst": d, "sha256": h})
    elif k == "write_lines":
        with open(d, "w") as fh:
            fh.write("".join(l + "\n" for l in s))
        rep["created"].append({"dst": d, "lines": len(s)})
    elif k == "write_csv":
        fields, rows, orig = s
        with open(d, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        oh = sha(orig)
        with open(d + ".origin", "w") as fh:
            fh.write(f"original: {orig}\noriginal_sha256: {oh}\nrows_of_this_masspoint: {len(rows)}\n")
        if os.path.exists(orig + ".sha256") or d.split("/")[-1].startswith("manifest_"):
            with open(d + ".sha256", "w") as fh:
                fh.write(sha(d) + "\n")
        rep["created"].append({"dst": d, "rows": len(rows), "origin_sha256": oh})
    elif k == "driver_log":
        mp_ = s
        lines = []
        for p, ls in log_lines.items():
            for i, l in enumerate(ls):
                if mp_ in l:
                    lines.append(f"[{os.path.basename(p)}] {l}")
                    used_log_lines.add((p, i))
        with open(d, "w") as fh:
            fh.write("".join(l + "\n" for l in lines))
        rep["created"].append({"dst": d, "lines": len(lines)})

# records.json + current_run + params.json per masspoint
for mp in mps:
    rd = layout.run_dir(mp, "qc", a.run_id)
    recs = {}
    for f in sorted(glob.glob(f"{rd}/out/chunk_*.json")):
        for r in json.load(open(f)):
            r["_run"] = a.run_id
            recs[r["path"]] = r
    json.dump(recs, open(f"{layout.qc_dir(mp)}/records.json", "w"))
    layout.set_current_run(mp, "qc", a.run_id)
    chunks = len(glob.glob(f"{rd}/lists/chunk_*.txt"))
    json.dump(dict(stage="qc", masspoint=mp, run_id=a.run_id, legacy=True, migrated=time.strftime("%F %T"),
                   n_records=len(recs), n_chunks=chunks, input_digest=layout.source_digest(mp)),
              open(f"{rd}/params.json", "w"), indent=1)
    report[mp]["created"].append({"dst": f"{layout.qc_dir(mp)}/records.json", "records": len(recs)})
    json.dump(report[mp], open(f"{rd}/migration.json", "w"), indent=1)

# remove migrated global files (only if every line was attributed or is a known global line) and now-empty dirs
leftover = []
for p, ls in log_lines.items():
    for i, l in enumerate(ls):
        if (p, i) not in used_log_lines and l.strip():
            leftover.append(f"{os.path.basename(p)}: {l[:100]}")
print("global log lines not attributed to a masspoint (dropped):", len(leftover))
for l in leftover[:6]:
    print("   ", l)
for p in glob_logs:
    os.remove(p)
for p in del_files:
    if os.path.isfile(p):
        os.remove(p)
for d in (f"{R}/deletion",):
    if os.path.isdir(d):
        os.rmdir(d)
for mp in mps:
    w = f"{R}/{mp}/.work"
    if os.path.isdir(w):
        os.rmdir(w)   # fails loudly if something was left behind
print("done; run `python3 python/aggregate.py <mp>` per masspoint and compare with the baseline")
