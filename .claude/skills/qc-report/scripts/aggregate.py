#!/usr/bin/env python3
"""aggregate.py MASSPOINT [--qc DIR]: merge chunk JSONs -> results/MP/{files,summary}.csv. Exits 2 if chunks/files are missing."""
import argparse, csv, fnmatch, glob, json, math, os, re, sys
ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--qc", default="/d0/scratch/choij/SampleFactoryQC")
a = ap.parse_args()
res = f"{a.qc}/results/{a.mp}"; work = f"{res}/.work"
excl = [l.strip() for l in open(f"{a.qc}/config/exclude.txt")] if os.path.exists(f"{a.qc}/config/exclude.txt") else []
excl = [e for e in excl if e and not e.startswith("#")]
rem = [l.strip() for l in open(f"{a.qc}/config/removed.txt")] if os.path.exists(f"{a.qc}/config/removed.txt") else []
n_removed = sum(1 for l in rem if f"/{a.mp}/" in l)
excl += rem
expected = list(dict.fromkeys([l.strip() for f in sorted(glob.glob(f"{work}/lists/chunk_*.txt")) for l in open(f) if l.strip() and not any(fnmatch.fnmatch(l.strip(), e) for e in excl)]))  # dedupe: retry chunks (chunk_r*) repeat paths, later results override
recs = {}
for f in sorted(glob.glob(f"{work}/out/chunk_*.json")):
    for r in json.load(open(f)):
        recs[r["path"]] = r
missing = [p for p in expected if p not in recs]
rows = []
for p in expected:
    r = recs.get(p)
    if r is None:
        continue
    reasons = list(r["reasons"])
    lost = r["gen_passed"] - r["n_events"] if (not reasons and r["gen_passed"] > r["n_events"]) else 0
    if lost:  # valid ROOT but fewer events than the GEN filter passed: production-level truncation
        reasons.append("incomplete"); r["corrupted"] = 1
    r["events_missing"] = lost
    m = re.search(r"/(\d{8}_\d{6})/", p)
    rows.append(dict(path=p, timestamp_dir=m.group(1) if m else "", size_bytes=r["size_bytes"],
                     n_events=r["n_events"], corrupted=r["corrupted"], reasons=";".join(reasons), events_missing=lost,
                     warnings=";".join(r["warnings"]), missing_branches=";".join(r["missing_branches"])))
with open(f"{res}/files.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["path"]); w.writeheader(); w.writerows(rows)
bad = [r for r in rows if r["corrupted"]]
good = [recs[r["path"]] for r in rows if not r["corrupted"]]
tot = sum(r["n_events"] for r in rows); bad_ev = sum(r["n_events"] for r in bad)
passed = sum(g["gen_passed"] for g in good); total = sum(g["gen_total"] for g in good)
eff = passed / total if total else None
err = math.sqrt(eff * (1 - eff) / total) if total else None
s = dict(masspoint=a.mp, n_files=len(rows), n_files_corrupted=len(bad), n_files_clean=len(rows) - len(bad),
         n_events_total=tot, n_events_corrupted=bad_ev, n_events_clean=tot - bad_ev,
         n_files_unreadable=sum(1 for r in bad if r["n_events"] == 0),
         gen_num_passed=passed, gen_num_total=total,
         filter_efficiency="" if eff is None else f"{eff:.6f}", filter_eff_err="" if err is None else f"{err:.6f}",
         n_files_incomplete=sum(1 for r in bad if "incomplete" in r["reasons"]), n_events_missing_incomplete=sum(r["events_missing"] for r in bad),
         n_files_missing_result=len(missing), n_files_removed=n_removed,
         all_custom_branches_present=int(all(not r["missing_branches"] for r in rows)) if rows else 0)
with open(f"{res}/summary.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(s.keys())); w.writeheader(); w.writerow(s)
print(s)
if missing:
    print(f"MISSING {len(missing)} files without result", file=sys.stderr); sys.exit(2)
