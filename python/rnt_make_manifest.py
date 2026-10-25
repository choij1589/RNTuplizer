#!/usr/bin/env python3
"""rnt_make_manifest.py MASSPOINT [--branches CONF]: conversion plan for one masspoint. READ-ONLY on /pnfs.

Takes the clean files of results/<mp>/qc/files.csv, merges consecutive sources into groups of about TARGET_EVENTS events
(config/rntuple_output.conf), resolves the KEEP/DROP selection against a real branch inventory and classifies every group:
  convert | skip-valid | reconvert-stale | conflict
Writes results/<mp>/rntuple/{branch_selection.csv, manifest_<ts>.csv(+.sha256)} (one manifest row per SOURCE file; action/output/
group_digest repeat for all sources of a group). Exit 4 on any conflict, 5 if QC is not clean/complete, 2 on selection errors."""
import sys; sys.dont_write_bytecode = True
import argparse, csv, hashlib, os, shutil, subprocess, time
import layout, rnt_branches, rnt_groups

ap = argparse.ArgumentParser()
ap.add_argument("mp")
ap.add_argument("--branches", default=rnt_branches.DEFAULT_CONF)
a = ap.parse_args()

qd, rd = layout.qc_dir(a.mp), layout.rnt_dir(a.mp)
s = next(csv.DictReader(open(f"{qd}/summary.csv")))
if int(s["n_files_corrupted"]) or int(s["n_files_missing_result"]) or s["all_custom_branches_present"] != "1":
    sys.exit(f"{a.mp}: QC not clean (corrupted={s['n_files_corrupted']} missing={s['n_files_missing_result']}); run the cleanup first")
clean = [r for r in csv.DictReader(open(f"{qd}/files.csv")) if r["corrupted"] == "0"]
os.makedirs(rd, exist_ok=True)

# selection: inventory of the first clean file
inv = f"{rd}/.inventory_ref.csv"
subprocess.run(["bash", "-c", f"source {layout.REPO}/scripts/env.sh && {layout.REPO}/bin/rnt_inventory '{clean[0]['path']}' > {inv}"], check=True)
trees = rnt_branches.read_inventory(inv)
rules = rnt_branches.load_rules(a.branches)
rows, warns, errs = rnt_branches.resolve(rules, trees)
for w in warns: print("WARNING:", w)
for e in errs: print("ERROR:", e)
if errs: sys.exit(2)
open(f"{rd}/branch_selection.csv", "w").write(rnt_branches.table_text(rows))
os.remove(inv)
sel_digest = rnt_branches.selection_digest(rows)

# toolchain digest = LCG view + ROOT version + converter binary + selection + compression
conf, oconf = layout.env_conf(), layout.output_conf()
conv_sha = hashlib.sha256(open(f"{layout.REPO}/bin/rnt_convert", "rb").read()).hexdigest()
tool_digest = hashlib.sha256(f"{conf['LCG_VIEW']}/{conf['LCG_PLATFORM']}|{conf['ROOT_VERSION']}|{conv_sha}|{sel_digest}|{oconf['COMPRESSION']}".encode()).hexdigest()

prev = {}
cp = f"{rd}/conversion.csv"
if os.path.exists(cp):
    prev = {r["output"]: r for r in csv.DictReader(open(cp))}

groups = rnt_groups.make_groups(clean, int(oconf["TARGET_EVENTS"]))
total_in, plan, srcs_of = 0, [], []
out_dir = os.path.dirname(layout.rntuple_part(a.mp, 0))
existing = set(os.listdir(out_dir)) if os.path.isdir(out_dir) else set()
for gi, g in enumerate(groups):
    out = layout.rntuple_part(a.mp, gi)
    base = os.path.basename(out)
    srcs = []
    for r in g:
        st = os.stat(r["path"])
        srcs.append(dict(path=r["path"], size=st.st_size, mtime=int(st.st_mtime), n_events=int(r["n_events"])))
        total_in += st.st_size
    gd = rnt_groups.group_digest(srcs)
    action, note = "convert", ""
    leftovers = sorted(f for f in existing if f.startswith(base + ".part") or f.startswith(base + ".failed"))
    if leftovers:
        action, note = "conflict", f"leftover {leftovers[0]}"
    elif base in existing:
        p = prev.get(out)
        if p is None:
            action, note = "conflict", "output exists without a conversion record"
        elif p["status"] != "ok" or p["group_digest"] != gd or os.path.getsize(out) != int(p["output_bytes"]):
            action, note = "reconvert-stale", "sources changed / output changed / previous failure"
        elif p["toolchain_digest"] != tool_digest:
            action, note = "reconvert-stale", "toolchain digest changed"
        else:
            action = "skip-valid"
    plan.append(dict(group=gi, output=out, action=action, note=note, group_digest=gd, events=sum(x["n_events"] for x in srcs)))
    srcs_of.append(srcs)
orphans = sorted(f for f in existing if (layout.output_index(f) is not None) and layout.output_index(f) >= len(groups))
for f in orphans:
    plan.append(dict(group=-1, output=f"{out_dir}/{f}", action="conflict", note="orphan output not in the plan (fewer groups than before); supersede it first", group_digest="", events=0))
    srcs_of.append([])

free = shutil.disk_usage(os.path.dirname(layout.RNTUPLE_ROOT.rstrip("/")) or "/").free
if free < int(1.0 * total_in):
    for p in plan:
        if p["action"] in ("convert", "reconvert-stale"):
            p["action"], p["note"] = "conflict", "not enough free space"

m = f"{rd}/manifest_{time.strftime('%Y%m%d_%H%M%S')}.csv"
with open(m, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["input", "size_bytes", "mtime", "events", "group", "output", "action", "group_digest", "toolchain_digest", "note"])
    for p, srcs in zip(plan, srcs_of):
        if not srcs:
            w.writerow(["", "", "", 0, p["group"], p["output"], p["action"], "", tool_digest, p["note"]])
        for x in srcs:
            w.writerow([x["path"], x["size"], x["mtime"], x["n_events"], p["group"], p["output"], p["action"], p["group_digest"], tool_digest, p["note"]])
h = hashlib.sha256(open(m, "rb").read()).hexdigest()
open(m + ".sha256", "w").write(h + "\n")
cnt = {}
for p in plan: cnt[p["action"]] = cnt.get(p["action"], 0) + 1
dropped = [r for r in rows if r["tree"] == "Events" and r["decision"] == "DROP"]
ev = [p["events"] for p in plan if p["group"] >= 0]
print(m, "\nsha256", h)
print(f"{a.mp}: {len(clean)} clean sources -> {len(ev)} outputs {cnt}; events/output min {min(ev)} median {sorted(ev)[len(ev)//2]} max {max(ev)}; input {total_in/1e6:.0f} MB, free {free/1e12:.1f} TB")
print(f"selection: conf={a.branches} rules={len(rules)} Events dropped={len(dropped)}; compression={oconf['COMPRESSION']} target={oconf['TARGET_EVENTS']}; toolchain digest {tool_digest[:16]}")
bad = [p for p in plan if p["action"] == "conflict"]
for p in bad[:10]: print("CONFLICT:", os.path.basename(p["output"]), "->", p["note"])
sys.exit(4 if bad else 0)
