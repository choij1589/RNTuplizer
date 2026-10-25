#!/usr/bin/env python3
"""rnt_branches.py: KEEP/DROP branch selection for the TTree -> RNTuple conversion.

Config file (config/rntuple_branches.conf), one rule per line, '#' comments:
    KEEP|DROP [tree:]pattern        shell-glob pattern, tree defaults to Events
Start with everything KEPT; rules are applied in file order, the LAST matching rule wins.
Safety: the 8 custom electron branches can never be dropped; a collection's counter (nPhoton) is dropped automatically when
all members are dropped and may never be dropped while a member is kept; patterns that match nothing and index branches that
point at a dropped collection (Electron_photonIdx) are reported as warnings.

CLI:
  rnt_branches.py resolve --inventory INV.csv [--conf FILE] [--out TABLE.csv]   -> resolved table (tree,branch,decision,...)
  rnt_branches.py draft   --inventory INV.csv --out config/rntuple_branches.draft.conf
INV.csv is the output of bin/rnt_inventory. Exit 2 on errors (warnings do not fail)."""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import argparse
import csv
import fnmatch
import hashlib
import os
import re
import sys
from collections import OrderedDict, defaultdict

import layout

CUSTOM = ["Electron_superclusterPhi", "Electron_superclusterEnergy", "Electron_DeltaEtaInSC", "Electron_DeltaPhiInSC",
          "Electron_DeltaPhiInSeed", "Electron_ecalPFClusIso", "Electron_hcalPFClusIso", "Electron_dr03HcalTowerSumEt"]
DEFAULT_CONF = f"{layout.CONFIG}/rntuple_branches.conf"


class SelectionError(Exception):
    pass


def load_rules(path):
    """-> list of (lineno, action, tree, pattern)."""
    rules = []
    if not path or not os.path.exists(path):
        return rules
    for i, line in enumerate(open(path), 1):
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) != 2 or parts[0] not in ("KEEP", "DROP"):
            raise SelectionError(f"{path}:{i}: expected 'KEEP|DROP [tree:]pattern', got {line.strip()!r}")
        tree, pat = ("Events", parts[1])
        if ":" in parts[1]:
            tree, pat = parts[1].split(":", 1)
        rules.append((i, parts[0], tree, pat))
    return rules


def read_inventory(path):
    """-> OrderedDict tree -> list of dict(branch,type,zip_bytes) from rnt_inventory CSV (branch rows only)."""
    trees = OrderedDict()
    for r in csv.DictReader(open(path)):
        if r["kind"] != "branch":
            continue
        trees.setdefault(r["tree"], []).append(dict(branch=r["branch"], type=r["type"], zip_bytes=int(r["zip_bytes"] or 0)))
    return trees


def counter_of(typ):
    m = re.search(r"\[(n\w+)\]$", typ)
    return m.group(1) if m else None


def resolve(rules, trees):
    """-> (rows, warnings, errors). rows: dict(tree,branch,decision,type,zip_bytes,rule,note)."""
    rows, warns, errs = [], [], []
    used = set()
    for tree, brs in trees.items():
        dec = OrderedDict((b["branch"], ("KEEP", "default")) for b in brs)
        for ln, act, rtree, pat in rules:
            if rtree != tree:
                continue
            hit = [b for b in dec if fnmatch.fnmatch(b, pat)]
            if hit:
                used.add(ln)
            for b in hit:
                dec[b] = (act, f"line {ln}")
        # protected custom branches (Events only)
        if tree == "Events":
            for b in CUSTOM:
                if b in dec and dec[b][0] == "DROP":
                    errs.append(f"protected branch {b} would be dropped ({dec[b][1]})")
                    dec[b] = ("KEEP", "protected")
        # counters: group members by counter branch
        members = defaultdict(list)
        for b in brs:
            c = counter_of(b["type"])
            if c and c in dec:
                members[c].append(b["branch"])
        for c, ms in members.items():
            kept = [m for m in ms if dec[m][0] == "KEEP"]
            if not kept and dec[c][0] == "KEEP" and any(dec[m][0] == "DROP" for m in ms):
                dec[c] = ("DROP", "auto: all members dropped")
            elif kept and dec[c][0] == "DROP":
                errs.append(f"{tree}: counter {c} dropped (rule {dec[c][1]}) while {len(kept)} member(s) are kept")
                dec[c] = ("KEEP", "counter of kept members")
        # dangling cross-collection index branches
        for c, ms in members.items():
            if dec[c][0] == "DROP" and not c.startswith("nLHE"):
                coll = c[1:]
                for b in dec:
                    if dec[b][0] == "KEEP" and b.split("_")[-1].lower() == coll.lower() + "idx":   # exact: Electron_photonIdx, not fsrPhotonIdx
                        warns.append(f"{tree}: kept index branch {b} points at dropped collection {coll}")
        info = {b["branch"]: b for b in brs}
        for b, (d, why) in dec.items():
            rows.append(dict(tree=tree, branch=b, decision=d, type=info[b]["type"], zip_bytes=info[b]["zip_bytes"], rule=why))
    for ln, act, rtree, pat in rules:
        if ln not in used:
            warns.append(f"line {ln}: '{act} {rtree}:{pat}' matches no branch")
    return rows, warns, errs


def table_text(rows):
    out = ["tree,branch,decision,type,zip_bytes,rule"]
    out += [f"{r['tree']},{r['branch']},{r['decision']},{r['type']},{r['zip_bytes']},{r['rule']}" for r in rows]
    return "\n".join(out) + "\n"


def selection_digest(rows):
    """sha256 over the KEEP/DROP decisions only (types/bytes/rules do not matter for the output)."""
    h = hashlib.sha256()
    for r in rows:
        h.update(f"{r['tree']},{r['branch']},{r['decision']}\n".encode())
    return h.hexdigest()


def expected_kept(rows, tree="Events"):
    return [r["branch"] for r in rows if r["tree"] == tree and r["decision"] == "KEEP"]


def draft(trees, path):
    groups = defaultdict(lambda: [0, 0])
    for b in trees.get("Events", []):
        g = b["branch"].split("_")[0] + "_*" if "_" in b["branch"] else b["branch"]
        groups[g][0] += 1
        groups[g][1] += b["zip_bytes"]
    tot = sum(v[1] for v in groups.values()) or 1
    with open(path, "w") as fh:
        fh.write("# DRAFT proposal generated from a real branch inventory - NOT active.\n"
                 "# Copy the DROP lines you approve into config/rntuple_branches.conf (all lines below are commented out).\n"
                 "# group           branches   compressed bytes   share of Events\n")
        for g, (n, z) in sorted(groups.items(), key=lambda kv: -kv[1][1]):
            fh.write(f"# DROP {g:<26} {n:5d} {z:12d} {100 * z / tot:6.2f}%\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["resolve", "draft"])
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--conf", default=DEFAULT_CONF)
    ap.add_argument("--out")
    a = ap.parse_args()
    trees = read_inventory(a.inventory)
    if a.cmd == "draft":
        draft(trees, a.out)
        print("draft ->", a.out)
        return
    rules = load_rules(a.conf)
    rows, warns, errs = resolve(rules, trees)
    ev = [r for r in rows if r["tree"] == "Events"]
    dropped = [r for r in ev if r["decision"] == "DROP"]
    print(f"conf={a.conf} rules={len(rules)} Events: {len(ev)} branches, {len(dropped)} dropped, "
          f"{sum(r['zip_bytes'] for r in dropped)} compressed bytes saved; selection digest {selection_digest(rows)[:16]}")
    for w in warns:
        print("WARNING:", w)
    for e in errs:
        print("ERROR:", e)
    if a.out:
        open(a.out, "w").write(table_text(rows))
    sys.exit(2 if errs else 0)


if __name__ == "__main__":
    main()
