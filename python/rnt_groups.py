#!/usr/bin/env python3
"""Grouping of source files into conversion outputs of about TARGET_EVENTS events (pure python, no ROOT).

Consecutive sources of a masspoint (sorted by layout.src_key) are cut into k = max(1, round(N / target)) contiguous groups; a cut is
placed where the cumulative event count passes the next multiple of N/k, so group sizes differ by about one source file (~3.4k events).
The grouping is a pure function of the clean QC rows, so a plan is reproducible; a changed source set changes the affected groups'
digests, which marks their outputs stale."""
import hashlib
import sys
sys.dont_write_bytecode = True
import layout


def sort_rows(rows):
    return sorted(rows, key=lambda r: layout.src_key(r["path"]))


def make_groups(rows, target):
    """rows: dicts with 'path' and 'n_events' -> list of lists of rows (contiguous, in source order)."""
    rows = sort_rows(rows)
    if not rows:
        return []
    n = sum(int(r["n_events"]) for r in rows)
    k = max(1, round(n / target))
    out, acc, gi = [[]], 0, 1
    for r in rows:
        e = int(r["n_events"])
        if gi < k and acc + e / 2 > gi * n / k:
            out.append([])
            gi += 1
        out[-1].append(r)
        acc += e
    return [g for g in out if g]


def group_digest(sources):
    """sha256 over the ordered (path, size, mtime, events) of the sources of one group."""
    h = hashlib.sha256()
    for s in sources:
        h.update(f"{s['path']} {s['size']} {s['mtime']} {s['n_events']}\n".encode())
    return h.hexdigest()
