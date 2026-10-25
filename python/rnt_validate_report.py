#!/usr/bin/env python3
"""rnt_validate_report.py MASSPOINT: merge the current validation run into results/<mp>/rntuple/validation.csv (one row per output)
and write results/<mp>/rntuple/summary.csv with the cross-checks against QC:
  sum(Events entries of the RNTuples) == QC n_events_clean, sum(Runs.genEventCount) == sum of the QC per-file genEventCount,
  filter efficiency recomputed from the RNTuple LuminosityBlocks == QC filter_efficiency.
Exit 2 if a converted output has no validation record, 1 if anything failed or a cross-check disagrees, 0 if all pass."""
import sys; sys.dont_write_bytecode = True
import argparse, csv, glob, json, os
import layout

ap = argparse.ArgumentParser()
ap.add_argument("mp")
a = ap.parse_args()
rn, qd = layout.rnt_dir(a.mp), layout.qc_dir(a.mp)
vp, cp = f"{rn}/validation.csv", f"{rn}/conversion.csv"
F = ["output", "ok", "n_sources", "group_digest", "seconds", "events_entries", "events_rntuple", "fields_compared", "missing", "extra",
     "type_mismatch", "value_mismatch", "genEventCount", "gen_passed", "gen_total", "run_id", "error"]
val = {r["output"]: r for r in csv.DictReader(open(vp))} if os.path.exists(vp) else {}
conv = {r["output"]: r for r in csv.DictReader(open(cp))}
rd = layout.run_dir(a.mp, "validate")
rid = os.path.basename(rd)
for f in sorted(glob.glob(f"{rd}/out/chunk_*.jsonl")):
    for line in open(f):
        j = json.loads(line)
        tr = {t["name"]: t for t in j["trees"]}
        ev, ru, lu = tr.get("Events", {}), tr.get("Runs", {}), tr.get("LuminosityBlocks", {})
        err = "; ".join(j.get("file_errors", []) + [f"{t['name']}: {t['error']}" for t in j["trees"] if t.get("error")]
                        + [f"{t['name']} missing={len(t['missing'])} extra={len(t['extra'])} type={len(t['type_mismatch'])} unsupported={len(t['unsupported'])} values={len(t['value_mismatch'])}"
                           for t in j["trees"] if not t["ok"] and not t.get("error")])
        row = dict(
            output=j["output"], ok=int(bool(j["ok"])), n_sources=len(j["inputs"]), group_digest=conv.get(j["output"], {}).get("group_digest", ""),
            seconds=round(j["seconds"], 2), events_entries=ev.get("entries", -1), events_rntuple=ev.get("rntuple_entries", -1),
            fields_compared=sum(t.get("fields_compared", 0) for t in j["trees"]),
            missing=sum(len(t["missing"]) for t in j["trees"]), extra=sum(len(t["extra"]) for t in j["trees"]),
            type_mismatch=sum(len(t["type_mismatch"]) for t in j["trees"]), value_mismatch=sum(len(t["value_mismatch"]) for t in j["trees"]),
            genEventCount=int(ru.get("rntuple_sums", {}).get("genEventCount", 0)),
            gen_passed=int(lu.get("rntuple_sums", {}).get("GenFilter_numEventsPassed", 0)),
            gen_total=int(lu.get("rntuple_sums", {}).get("GenFilter_numEventsTotal", 0)), run_id=rid, error=err[:300])
        val[j["output"]] = {k: str(v) for k, v in row.items()}   # same types as rows read back from the CSV
with open(vp, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=F)
    w.writeheader()
    w.writerows(val[k] for k in sorted(val))

qs = next(csv.DictReader(open(f"{qd}/summary.csv")))
qrec = json.load(open(f"{qd}/records.json"))
clean = [r["path"] for r in csv.DictReader(open(f"{qd}/files.csv")) if r["corrupted"] == "0"]
man = sorted(glob.glob(f"{rn}/manifest_*.csv"))[-1]
plan = {}
for r in csv.DictReader(open(man)):
    if r["output"] and r["group"] != "-1":
        plan.setdefault(r["output"], []).append(r)
outs = sorted(plan)
ok_conv = [o for o in outs if conv.get(o, {}).get("status") == "ok" and conv[o]["group_digest"] == plan[o][0]["group_digest"]]
passed = [o for o in ok_conv if val.get(o, {}).get("ok") == "1" and val[o]["group_digest"] == conv[o]["group_digest"]]
failed_val = [o for o in ok_conv if o in val and o not in passed]
not_val = [o for o in ok_conv if o not in val]
ev = sum(int(val[o]["events_rntuple"]) for o in passed)
gec = sum(int(val[o]["genEventCount"]) for o in passed)
gp, gt = sum(int(val[o]["gen_passed"]) for o in passed), sum(int(val[o]["gen_total"]) for o in passed)
q_gec = sum(qrec[p]["n_events_expected"] for p in clean)
eff = gp / gt if gt else None
all_pass = (len(passed) == len(outs) and not failed_val and not not_val)
ev_match = all_pass and ev == int(qs["n_events_clean"])
gec_match = all_pass and gec == q_gec
eff_match = all_pass and eff is not None and f"{eff:.6f}" == qs["filter_efficiency"]
in_b = sum(int(conv[o]["input_bytes"]) for o in ok_conv)
out_b = sum(int(conv[o]["output_bytes"]) for o in ok_conv)
digests = {conv[o]["toolchain_digest"] for o in ok_conv}
evs = [int(conv[o]["events_entries"]) for o in ok_conv]
s = dict(masspoint=a.mp, n_sources_clean_qc=len(clean), n_outputs_planned=len(outs), n_converted_ok=len(ok_conv),
         n_conversion_failed=sum(1 for o in outs if conv.get(o, {}).get("status") == "failed"),
         n_validated_ok=len(passed), n_validation_failed=len(failed_val), n_not_validated=len(not_val),
         events_rntuple=ev, events_qc_clean=int(qs["n_events_clean"]), events_match=int(ev_match),
         genEventCount_rntuple=gec, genEventCount_qc=q_gec, genEventCount_match=int(gec_match),
         filter_efficiency_rntuple="" if eff is None else f"{eff:.6f}", filter_efficiency_qc=qs["filter_efficiency"], efficiency_match=int(eff_match),
         events_per_output_min=min(evs) if evs else "", events_per_output_median=sorted(evs)[len(evs) // 2] if evs else "", events_per_output_max=max(evs) if evs else "",
         input_bytes=in_b, output_bytes=out_b, size_ratio=round(out_b / in_b, 4) if in_b else "",
         branches_kept=conv[ok_conv[0]]["branches_kept"] if ok_conv else "", branches_dropped=conv[ok_conv[0]]["branches_dropped"] if ok_conv else "",
         toolchain_digests=len(digests), toolchain_digest=sorted(digests)[0][:16] if digests else "",
         all_pass=int(all_pass and ev_match and gec_match and eff_match and len(digests) == 1))
with open(f"{rn}/summary.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(s.keys()))
    w.writeheader()
    w.writerow(s)
print(s)
for o in failed_val[:10]:
    print("FAILED:", os.path.basename(o), val[o]["error"])
sys.exit(2 if not_val else (0 if s["all_pass"] else 1))
