# RNTuplizer

QC and TTree -> RNTuple conversion of private NanoAODv15 samples (custom electron branches) in
`/u/user/choij/SE_UserHome/SampleFactory` (-> `/pnfs/knu.ac.kr/data/cms/store/user/choij/SampleFactory`).
Fixed workflow per masspoint: **QC -> (cleanup) -> convert -> validate** = `/pipeline <mp>`. Details: README.md.

## Environment (one pinned toolchain for everything)
- `source scripts/env.sh` = LCG_110 view (ROOT 6.40.02, Python 3.13, gcc 15, cmake), defined in `config/rntuple_env.conf`; asserts the ROOT version. CMSSW is retired. System python (3.9) has no ROOT: only layout/aggregate/gate/report scripts run without the env.
- HTCondor for all bulk reads (QC, conversion, validation). Wrappers source the env themselves (`getenv = False`). Remove jobs only by cluster id (`condor_rm <ids>`), never `condor_rm <user>`.
- Interactive shells are zsh (no word splitting of variables): run multi-line logic as bash scripts.

## Layout (single source of truth: `python/layout.py`, roots overridable with `RNT_*` env vars for sandbox tests)
- Everything about a masspoint lives in `results/<mp>/` (qc/, rntuple/, pipeline.json); `results/overall.csv` (QC) and `results/overall_rntuple.csv` (conversion/validation) are the only cross-masspoint files. Logs of condor runs: `results/<mp>/<stage>/runs/<run_id>/`.
- /pnfs is data only: `SampleFactory/<mp>/chain_RunIII2024Summer24/<ts>/NanoAODv15_<N>.root` (sources), `SampleFactory_quarantine/<date>/<mp>/...`, `RNTuple/<mp>/rntpl_<NNN>.root` (converted: consecutive source files merged into outputs of ~20k events, provenance in `results/<mp>/rntuple/groups.csv`), `RNTuple_superseded/<date>/<mp>/...` (replaced outputs, renamed aside - never deleted).
- Source discovery is strict (`chain_RunIII2024Summer24/<ts>/NanoAODv15_<digits>.root`); never glob recursively.

## Code layout rule
- Skill directories (`.claude/skills/<name>/`) contain only `SKILL.md`. Bash in `scripts/`, Python in `python/` (flat, unique names, shared helpers `layout.py`/`common.py`), C++ in `src/` (CMake -> `bin/`). Reference scripts by repo-relative path; build paths from `layout.py`, not from a script's own location.
- All code is in this repo; `/d0/scratch/choij/RNTuplizer_upstream` is reference reading only (nothing from it is built or run).
- New script: put it in the right folder and mention it in the owning SKILL.md and the README.

## Output settings
`config/rntuple_output.conf`: `COMPRESSION=512` (zstd level 12), `TARGET_EVENTS=20000`. Both are part of the toolchain/plan digests; changing them marks converted outputs stale. Group membership is a pure function of the clean QC rows (`python/rnt_groups.py`): cut points are global over the masspoint (tight size spread), so adding/removing/changing even one source regroups much of the masspoint (measured: 7 of 15 outputs of MA-65 when one source disappears) and those outputs are reconverted (old ones renamed into RNTuple_superseded/). Therefore: finish QC and cleanup BEFORE converting a masspoint; unchanged groups are skipped by their digest.

## Branch selection
`config/rntuple_branches.conf`: `KEEP|DROP [tree:]pattern`, default keep-all, last match wins; 8 custom electron branches protected. Production table (approved): DROP `HTXS_* Tau_* boostedTau_* Photon_* FsrPhoton_* IsoTrack_* LowPtElectron_* SoftActivityJet_* TauProd_* TauSpinner_* TrackGenJetAK4_*` plus `Electron_photonIdx Electron_fsrPhotonIdx Muon_fsrPhotonIdx` (254 of 2015 Events branches incl. 9 auto-dropped counters; ~17.7% of the Events TTree bytes). All HLT_* and L1_* trigger branches are KEPT (user decision). Test selection: `config/rntuple_branches.test.conf` (`DROP Photon_*`). Changing the config changes the toolchain digest, which marks old outputs stale (the MA-65 pilot outputs were made with the test selection).

## Destructive operations (cleanup rules)
- Corrupted files are removed only via `/qc-cleanup`: manifest -> independent audit -> explicit user approval (AskUserQuestion) -> canary -> quarantine (rename) -> post-audit. Purge (permanent) is a separate later run with its own approval.
- Destructive scripts (`quarantine.py`, `purge.py`, `purge_rnt.py`, `restore.py`) run only in the main session, never in subagents; no `rm`, no recursive/glob operations on /pnfs sample dirs; use realpaths; /pnfs is a hard NFS mount, so wrap file operations on UNAVAILABLE files in timeouts and never read them directly (check dCache locality instead).
- Conversion and validation delete nothing. Failed outputs are reported and re-run, never auto-removed; a stale output that gets replaced is renamed into `RNTuple_superseded/` (purge later, with approval: `python/purge_rnt.py plan <mp>` -> hashed plan -> dry-run -> user approval -> `apply --apply`; log `results/<mp>/rntuple/purge_<ts>.log.csv`).
- `results/<mp>/qc/exclude.txt` = excluded from QC (not deleted); `qc/removed.txt` = quarantined/purged paths.

## Verification habit
Test new tools in a sandbox first (`work/sandbox*`, NFS-visible for condor workers; the scratchpad in /tmp is not visible to workers), compare re-aggregated CSVs byte-for-byte against the previous ones, and use independent agents (`qc-verifier`, `qc-delete-auditor`, `rnt-validator`, `layout-auditor`) that are given paths, not conclusions.
