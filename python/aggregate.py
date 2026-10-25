#!/usr/bin/env python3
"""aggregate.py MASSPOINT: results/<mp>/qc/records.json -> qc/files.csv + qc/summary.csv.
Expected files = lists of the current QC run minus exclude.txt / removed.txt. Exits 2 if any expected file has no record."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, fnmatch, glob, json, math, os, re, sys
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
a = ap.parse_args()
qd = layout.qc_dir(a.mp)
excl = layout.read_list(layout.exclude_file(a.mp))
rem = layout.read_list(layout.removed_file(a.mp))
n_removed = len(rem)
excl += rem
rd = layout.run_dir(a.mp, "qc")
expected = list(dict.fromkeys(
    l.strip() for f in sorted(glob.glob(f"{rd}/lists/chunk_*.txt")) for l in open(f)
    if l.strip() and not any(fnmatch.fnmatch(l.strip(), e) for e in excl)))
recs = json.load(open(f"{qd}/records.json"))
cur = os.path.basename(rd)
missing = [p for p in expected if p not in recs or recs[p].get("_run") != cur]   # records of an older run do not count
rows = []
for p in expected:
    r = recs.get(p)
    if r is None or r.get("_run") != cur:
        continue
    reasons = list(r["reasons"])
    lost = r["gen_passed"] - r["n_events"] if (not reasons and r["gen_passed"] > r["n_events"]) else 0
    corrupted = r["corrupted"]
    if lost:  # valid ROOT but fewer events than the GEN filter passed: production-level truncation
        reasons.append("incomplete")
        corrupted = 1
    m = re.search(r"/(\d{8}_\d{6})/", p)
    rows.append(dict(path=p, timestamp_dir=m.group(1) if m else "", size_bytes=r["size_bytes"],
                     n_events=r["n_events"], corrupted=corrupted, reasons=";".join(reasons), events_missing=lost,
                     warnings=";".join(r["warnings"]), missing_branches=";".join(r["missing_branches"])))
with open(f"{qd}/files.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["path"])
    w.writeheader()
    w.writerows(rows)
bad = [r for r in rows if r["corrupted"]]
good = [recs[r["path"]] for r in rows if not r["corrupted"]]
tot = sum(r["n_events"] for r in rows)
bad_ev = sum(r["n_events"] for r in bad)
passed = sum(g["gen_passed"] for g in good)
total = sum(g["gen_total"] for g in good)
eff = passed / total if total else None
err = math.sqrt(eff * (1 - eff) / total) if total else None
s = dict(masspoint=a.mp, n_files=len(rows), n_files_corrupted=len(bad), n_files_clean=len(rows) - len(bad),
         n_events_total=tot, n_events_corrupted=bad_ev, n_events_clean=tot - bad_ev,
         n_files_unreadable=sum(1 for r in bad if r["n_events"] == 0),
         gen_num_passed=passed, gen_num_total=total,
         filter_efficiency="" if eff is None else f"{eff:.6f}", filter_eff_err="" if err is None else f"{err:.6f}",
         n_files_incomplete=sum(1 for r in bad if "incomplete" in r["reasons"]),
         n_events_missing_incomplete=sum(r["events_missing"] for r in bad),
         n_files_missing_result=len(missing), n_files_removed=n_removed,
         all_custom_branches_present=int(all(not r["missing_branches"] for r in rows)) if rows else 0)
with open(f"{qd}/summary.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(s.keys()))
    w.writeheader()
    w.writerow(s)
print(s)
if missing:
    print(f"MISSING {len(missing)} files without result", file=sys.stderr)
    sys.exit(2)
