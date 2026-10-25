#!/usr/bin/env python3
"""Check NanoAOD files for corruption. Usage: check_file.py OUT.json FILE [FILE...]  (needs PyROOT via cmsenv)"""
import json, os, subprocess, sys
TIMEOUT = int(os.environ.get("QC_FILE_TIMEOUT", "300"))  # seconds per file; hung /pnfs reads sit in D state forever

REQ = ["Electron_superclusterPhi", "Electron_superclusterEnergy", "Electron_DeltaEtaInSC",
       "Electron_DeltaPhiInSC", "Electron_DeltaPhiInSeed", "Electron_ecalPFClusIso",
       "Electron_hcalPFClusIso", "Electron_dr03HcalTowerSumEt"]
LUMI_BR = ["GenFilter_numEventsPassed", "GenFilter_numEventsTotal"]


def check(path):
    global ROOT
    import ROOT
    ROOT.gROOT.SetBatch(True)
    ROOT.gErrorIgnoreLevel = ROOT.kFatal
    r = dict(path=path, size_bytes=-1, n_events=0, n_events_readable=0, n_events_expected=-1,
             gen_passed=0, gen_total=0, corrupted=0, reasons=[], warnings=[], missing_branches=[])
    try:
        r["size_bytes"] = os.path.getsize(path)
    except OSError:
        pass
    if r["size_bytes"] < 1000:
        r["reasons"].append("size0")
        r["corrupted"] = 1
        return r
    try:
        f = ROOT.TFile.Open(path)
    except OSError:
        f = None
    if not f or f.IsZombie():
        r["reasons"].append("zombie"); r["corrupted"] = 1; return r
    if f.TestBit(ROOT.TFile.kRecovered):
        r["reasons"].append("recovered")
    E, Rn, L = f.Get("Events"), f.Get("Runs"), f.Get("LuminosityBlocks")
    if not all(isinstance(t, ROOT.TTree) for t in (E, Rn, L)):
        r["reasons"].append("no_tree")
    if isinstance(E, ROOT.TTree):
        r["n_events"] = int(E.GetEntries())
        if r["n_events"] == 0:
            r["reasons"].append("zero_events")
        have = {b.GetName() for b in E.GetListOfBranches()}
        r["missing_branches"] = [b for b in REQ if b not in have]
        if r["missing_branches"]:
            r["reasons"].append("missing_branch")
        ok = 0
        try:
            for i in range(r["n_events"]):
                if E.GetEntry(i) < 0:
                    r["reasons"].append("read_error"); break
                ok += 1
        except Exception:
            r["reasons"].append("read_error")
        r["n_events_readable"] = ok
    if isinstance(L, ROOT.TTree):
        try:
            if all(hasattr(L, b) for b in LUMI_BR):
                for i in range(L.GetEntries()):
                    if L.GetEntry(i) < 0:
                        r["reasons"].append("read_error"); break
                    r["gen_passed"] += int(L.GenFilter_numEventsPassed)
                    r["gen_total"] += int(L.GenFilter_numEventsTotal)
            else:
                r["warnings"].append("no_genfilter_branches")
        except Exception:
            r["reasons"].append("read_error")
    if isinstance(Rn, ROOT.TTree):
        try:
            n = 0
            for i in range(Rn.GetEntries()):
                if Rn.GetEntry(i) < 0:
                    r["reasons"].append("read_error"); break
                n += int(Rn.genEventCount)
            r["n_events_expected"] = n
            if r["n_events"] and n != r["n_events"]:
                r["warnings"].append("count_mismatch")
        except Exception:
            r["reasons"].append("read_error")
    f.Close()
    r["reasons"] = sorted(set(r["reasons"]))
    r["corrupted"] = int(bool(r["reasons"]))
    return r


def bad(path, reason, warn=""):
    return dict(path=path, size_bytes=-1, n_events=0, n_events_readable=0, n_events_expected=-1,
                gen_passed=0, gen_total=0, corrupted=1, reasons=[reason], warnings=[warn] if warn else [],
                missing_branches=[])


def one(out, path):
    try:
        r = check(path)
    except Exception as e:
        r = bad(path, "check_exception", repr(e)[:100])
    with open(out, "w") as fh:
        json.dump(r, fh)


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        one(sys.argv[2], sys.argv[3]); sys.exit(0)
    out, files = sys.argv[1], sys.argv[2:]
    res = []
    for i, p in enumerate(files):
        tmp = f"{out}.{i}.one"
        proc = subprocess.Popen([sys.executable, __file__, "--one", tmp, p])
        try:
            proc.wait(timeout=TIMEOUT)
            res.append(json.load(open(tmp)) if os.path.exists(tmp) else bad(p, "check_exception", f"rc={proc.returncode}"))
        except subprocess.TimeoutExpired:
            proc.kill()  # may stay in D state; do not wait for it
            res.append(bad(p, "io_timeout", f"no result after {TIMEOUT}s"))
        if os.path.exists(tmp):
            os.remove(tmp)
    with open(out, "w") as fh:
        json.dump(res, fh)
