#!/usr/bin/env python3
"""Unit tests for rnt_branches.py (no ROOT needed): python3 python/test_rnt_branches.py"""
import sys; sys.dont_write_bytecode = True   # never leave __pycache__ in python/
import os, sys, tempfile, unittest
from collections import OrderedDict
import rnt_branches as rb


def inv():
    ev = [("nElectron", "Int_t"), ("Electron_pt", "Float_t[nElectron]"), ("Electron_photonIdx", "Int_t[nElectron]"),
          ("nPhoton", "Int_t"), ("Photon_pt", "Float_t[nPhoton]"), ("Photon_eta", "Float_t[nPhoton]"),
          ("HLT_IsoMu24", "Bool_t"), ("HLT_Mu50", "Bool_t"), ("run", "UInt_t")]
    ev += [(b, "Float_t[nElectron]") for b in rb.CUSTOM]
    return OrderedDict(Events=[dict(branch=b, type=t, zip_bytes=100) for b, t in ev],
                       Runs=[dict(branch="genEventCount", type="Long64_t", zip_bytes=8)])


def conf(text):
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as fh:
        fh.write(text)
    return rb.load_rules(fh.name)


def dec(rows, b, tree="Events"):
    return next(r["decision"] for r in rows if r["tree"] == tree and r["branch"] == b)


class T(unittest.TestCase):
    def test_default_keeps_all(self):
        rows, w, e = rb.resolve([], inv())
        self.assertTrue(all(r["decision"] == "KEEP" for r in rows)); self.assertEqual((w, e), ([], []))

    def test_last_match_wins(self):
        rows, w, e = rb.resolve(conf("DROP HLT_*\nKEEP HLT_IsoMu24\n"), inv())
        self.assertEqual(dec(rows, "HLT_Mu50"), "DROP"); self.assertEqual(dec(rows, "HLT_IsoMu24"), "KEEP")

    def test_collection_drop_removes_counter_and_warns_on_dangling_index(self):
        rows, w, e = rb.resolve(conf("DROP Photon_*\n"), inv())
        self.assertEqual(dec(rows, "Photon_pt"), "DROP"); self.assertEqual(dec(rows, "nPhoton"), "DROP")
        self.assertEqual(dec(rows, "Electron_photonIdx"), "KEEP"); self.assertEqual(e, [])
        self.assertTrue(any("Electron_photonIdx" in x for x in w))
        self.assertEqual(sum(r["decision"] == "DROP" for r in rows), 3)

    def test_typo_pattern_warns_and_drops_nothing(self):
        rows, w, e = rb.resolve(conf("DROP Photons_*\n"), inv())
        self.assertTrue(any("matches no branch" in x for x in w)); self.assertTrue(all(r["decision"] == "KEEP" for r in rows))

    def test_protected_branch_rejected(self):
        rows, w, e = rb.resolve(conf("DROP Electron_superclusterPhi\n"), inv())
        self.assertTrue(e); self.assertEqual(dec(rows, "Electron_superclusterPhi"), "KEEP")
        rows, w, e = rb.resolve(conf("DROP Electron_*\n"), inv()); self.assertTrue(e)

    def test_counter_cannot_be_dropped_with_kept_members(self):
        rows, w, e = rb.resolve(conf("DROP nPhoton\n"), inv())
        self.assertTrue(any("counter nPhoton" in x for x in e)); self.assertEqual(dec(rows, "nPhoton"), "KEEP")

    def test_tree_prefix_and_syntax(self):
        rows, w, e = rb.resolve(conf("DROP Runs:genEventCount\n"), inv())
        self.assertEqual(dec(rows, "genEventCount", "Runs"), "DROP")
        with self.assertRaises(rb.SelectionError): conf("REMOVE x\n")

    def test_digest_changes_with_selection(self):
        a = rb.selection_digest(rb.resolve([], inv())[0]); b = rb.selection_digest(rb.resolve(conf("DROP HLT_*\n"), inv())[0])
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=1)
