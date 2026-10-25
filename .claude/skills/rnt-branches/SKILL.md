---
name: rnt-branches
description: KEEP/DROP branch selection for the conversion (config/rntuple_branches.conf), resolver, draft proposal and test selection.
---
Rules, one per line: `KEEP|DROP [tree:]pattern` (shell glob, tree defaults to Events). Everything is KEPT by default; rules apply in file order and the LAST match wins (`DROP HLT_*` then `KEEP HLT_IsoMu24`). The 8 custom electron branches are protected; a collection's counter (nPhoton) is dropped automatically when all members are dropped and may not be dropped while a member is kept; unmatched patterns and kept index branches pointing at a dropped collection (Electron_photonIdx) are warnings.
Tools: `python3 python/rnt_branches.py resolve --inventory INV.csv [--conf FILE] [--out TABLE.csv]` (INV from `bin/rnt_inventory`), `... draft --inventory INV.csv --out config/rntuple_branches.draft.conf` (commented proposal grouped by prefix with sizes; not active), `python3 python/test_rnt_branches.py` (unit tests).
Files: `config/rntuple_branches.conf` (production, keep-all until the user approves DROP rules), `config/rntuple_branches.test.conf` (`DROP Photon_*`). The resolved table `results/<mp>/rntuple/branch_selection.csv` and its digest feed the toolchain digest.
