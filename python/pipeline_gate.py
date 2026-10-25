#!/usr/bin/env python3
"""pipeline_gate.py {A|P|B|C} MASSPOINT [--manifest M]: gate checks of the fixed workflow. Prints PASS/FAIL with reasons.
Exit 0 pass, 1 fail, 3 (gate A only) = QC clean otherwise but corrupted files remain -> run /qc-cleanup first.
 A  QC complete and fresh: no missing results, 8 custom branches present, file set + sizes unchanged since QC, corrupted == 0
 P  conversion plan has no conflicts and a valid sha256
 B  every clean file converted: status ok, output exists with recorded size, current toolchain digest, no .part/.failed leftovers
 C  validation passed for every file and the QC cross-checks (events, genEventCount, filter efficiency) agree"""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse, csv, hashlib, json, os, sys
import layout

ap = argparse.ArgumentParser()
ap.add_argument("gate", choices=list("APBC"))
ap.add_argument("mp")
ap.add_argument("--manifest")
a = ap.parse_args()
mp, why, code = a.mp, [], 1


def done():
    print(f"GATE {a.gate} {mp}: " + ("PASS" if not why else "FAIL"))
    for w in why:
        print("  -", w)
    sys.exit(0 if not why else code)


if a.gate == "A":
    qd = layout.qc_dir(mp)
    try:
        s = next(csv.DictReader(open(f"{qd}/summary.csv")))
        rows = list(csv.DictReader(open(f"{qd}/files.csv")))
    except FileNotFoundError:
        why.append("no QC reports yet")
        done()
    if int(s["n_files_missing_result"]):
        why.append(f"{s['n_files_missing_result']} files without QC result")
    if s["all_custom_branches_present"] != "1":
        why.append("custom electron branches missing in some files")
    cur = {p: os.path.getsize(p) for p in layout.source_files(mp)}
    qcset = {r["path"]: int(r["size_bytes"]) for r in rows}
    gone = sorted(set(qcset) - set(cur))
    new = sorted(set(cur) - set(qcset))
    changed = [p for p in qcset if p in cur and cur[p] != qcset[p] and qcset[p] >= 0]
    if gone or new or changed:
        why.append(f"QC is stale: {len(gone)} files gone, {len(new)} new, {len(changed)} size-changed since QC -> rerun QC")
    if int(s["n_files_corrupted"]):
        why.append(f"{s['n_files_corrupted']} corrupted files remain -> run /qc-cleanup (human approval), re-aggregate, then re-check")
        code = 3 if len(why) == 1 else 1
elif a.gate == "P":
    m = a.manifest
    rows = list(csv.DictReader(open(m)))
    if open(m + ".sha256").read().strip() != hashlib.sha256(open(m, "rb").read()).hexdigest():
        why.append("manifest sha256 mismatch")
    n, seen = {}, set()
    for r in rows:
        if r["output"] not in seen:
            seen.add(r["output"])
            n[r["action"]] = n.get(r["action"], 0) + 1
    print("  plan (outputs):", n)
    if n.get("conflict"):
        why.append(f"{n['conflict']} conflicts: " + "; ".join(sorted({r['note'] for r in rows if r['action'] == 'conflict'})))
elif a.gate == "B":
    # every planned output converted with the current sources and toolchain; no leftovers; plan fresh against QC
    import glob
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rnt_groups
    rn, qd = layout.rnt_dir(mp), layout.qc_dir(mp)
    conv = {r["output"]: r for r in csv.DictReader(open(f"{rn}/conversion.csv"))}
    mans = sorted(glob.glob(f"{rn}/manifest_*.csv"))
    if not mans:
        why.append("no conversion manifest")
        done()
    tool = next(csv.DictReader(open(mans[-1])))["toolchain_digest"]
    clean = [r for r in csv.DictReader(open(f"{qd}/files.csv")) if r["corrupted"] == "0"]
    groups = rnt_groups.make_groups(clean, int(layout.output_conf()["TARGET_EVENTS"]))
    for gi, g in enumerate(groups):
        out = layout.rntuple_part(mp, gi)
        srcs = []
        for r in g:
            st = os.stat(r["path"])
            srcs.append(dict(path=r["path"], size=st.st_size, mtime=int(st.st_mtime), n_events=int(r["n_events"])))
        gd = rnt_groups.group_digest(srcs)
        c = conv.get(out)
        if c is None or c["status"] != "ok":
            why.append(f"not converted: {os.path.basename(out)} {'' if c is None else c['error'][:80]}")
            continue
        if c["group_digest"] != gd:
            why.append(f"{os.path.basename(out)} was built from different sources (re-plan and reconvert)")
        if c["toolchain_digest"] != tool:
            why.append(f"stale toolchain digest: {os.path.basename(out)}")
        if not os.path.exists(out) or os.path.getsize(out) != int(c["output_bytes"]) or int(c["output_bytes"]) <= 0:
            why.append(f"output missing or wrong size: {os.path.basename(out)}")
    d = os.path.dirname(layout.rntuple_part(mp, 0))
    if os.path.isdir(d):
        left = [f for f in os.listdir(d) if ".part." in f or ".failed" in f]
        extra = [f for f in os.listdir(d) if (layout.output_index(f) is not None) and layout.output_index(f) >= len(groups)]
        if left:
            why.append(f"leftover {left[0]} in {d[-40:]}")
        if extra:
            why.append(f"{len(extra)} output(s) beyond the plan (e.g. {extra[0]})")
    print(f"  {len(groups)} planned outputs")
    why = why[:15]
elif a.gate == "C":
    try:
        s = next(csv.DictReader(open(f"{layout.rnt_dir(mp)}/summary.csv")))
    except FileNotFoundError:
        why.append("no rntuple/summary.csv (validation not run)")
        done()
    if s["all_pass"] != "1":
        for k in ("n_conversion_failed", "n_validation_failed", "n_not_validated"):
            if int(s[k]):
                why.append(f"{k}={s[k]}")
        for k in ("events_match", "genEventCount_match", "efficiency_match"):
            if s[k] != "1":
                why.append(f"{k}=0 (rntuple {s.get(k.replace('_match', '_rntuple'), '?')})")
        if s["toolchain_digests"] != "1":
            why.append("mixed toolchain digests")
    print(f"  events {s['events_rntuple']} vs QC {s['events_qc_clean']}; efficiency {s['filter_efficiency_rntuple']} vs {s['filter_efficiency_qc']}; size ratio {s['size_ratio']}")
done()
