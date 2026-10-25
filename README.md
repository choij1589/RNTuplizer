# RNTuplizer

Quality control and TTree -> RNTuple conversion of private NanoAODv15 samples with custom electron branches.
For each masspoint a fixed workflow runs on the KNU Tier-3 HTCondor pool:

    QC (corruption, 8 custom branches, filter efficiency)  ->  [cleanup of corrupted files]  ->  conversion to RNTuple  ->  independent validation

Sources: `/u/user/choij/SE_UserHome/SampleFactory` (= `/pnfs/knu.ac.kr/data/cms/store/user/choij/SampleFactory`),
`<mp>/chain_RunIII2024Summer24/<YYYYMMDD_HHMMSS>/NanoAODv15_<N>.root`; every timestamp directory is an independent set of files.
Converted data: `/pnfs/knu.ac.kr/data/cms/store/user/choij/RNTuple/<mp>/rntpl_<NNN>.root` - consecutive source files of a masspoint are merged into outputs of about 20k events
(typically 5-6 sources each; zstd level 12); which sources went into which output is recorded in `results/<mp>/rntuple/groups.csv`.

---------------------------------------------------------------------------------------------------

## 1. Quick start

Work in a Claude Code session in this repo. After adding/editing agents or skills run `/reload-plugins`.

| Goal | Command |
|---|---|
| Whole workflow for one masspoint | `/pipeline <masspoint> [--branches config/rntuple_branches.test.conf]` |
| Only the QC stage (one / all masspoints) | `/sample-qc <masspoint>` / `/sample-qc all` |
| Remove the corrupted files of a masspoint (human-approved, 2 stages) | `/qc-cleanup <masspoint>` then, much later, `/qc-cleanup purge <masspoint>` |
| Look at results | `results/<mp>/qc/{files,summary}.csv`, `results/<mp>/rntuple/{conversion,validation,summary}.csv`, `results/overall.csv` |
| Undo a quarantine | `python3 python/restore.py --log results/<mp>/qc/deletion/log_<ts>.csv --apply` |

Without Claude (plain bash, from the repo root):

```bash
MP=TTToHcToWA_AToMuMu_MHc-130_MA-65_MultiLepFilter_TuneCP5_cff
bash scripts/rnt_build.sh                                             # once: build bin/rnt_convert, rnt_inventory, rnt_validate
bash scripts/qc_run_mp.sh $MP && python3 python/pipeline_gate.py A $MP         # 1 QC  (exit 3 at gate A = corrupted files, run the cleanup)
bash scripts/rnt_run_mp.sh $MP convert --branches config/rntuple_branches.conf  # 2 plan + convert  (gates P and B)
bash scripts/rnt_run_mp.sh $MP validate                                         # 3 validate        (gate C)
python3 python/rollup.py                                                        # results/overall.csv
```

Rules of thumb: ROOT only after `source scripts/env.sh`; use `bash` for multi-line shell logic (the login shell is zsh);
remove condor jobs by cluster id only; never read files whose dCache locality is `UNAVAILABLE` (check `cat <dir>/.(get)(<file>)(locality)`).

---------------------------------------------------------------------------------------------------

## 2. Design concept

1. **One pinned toolchain.** `config/rntuple_env.conf` selects the LCG view (`LCG_110`, `x86_64-el9-gcc15-opt` = ROOT 6.40.02, Python 3.13,
   gcc 15, cmake). `scripts/env.sh` asserts the ROOT version; the C++ tools refuse to run on another ROOT. RNTuple's format and API still move, and
   ROOT >= 6.40 is required for the importer used here (CMSSW_15_0_22 has 6.32.13 and was retired after a regression check: identical QC records).
2. **Everything about a masspoint lives in `results/<mp>/`** (reports, condor run directories with logs, deletion records); `/pnfs` sample directories hold data only.
   All paths come from `python/layout.py`; roots can be overridden with `RNT_*` environment variables, which is how every tool is tested in a sandbox first.
3. **Detect, aggregate, judge.** Workers only write per-file facts. Cross-file rules (`incomplete`, exclusions, removed files, efficiency, cross-checks) are applied when
   aggregating, so a rule change never needs a re-read of 33 GB. A job failure is never counted as file corruption or as a clean file.
4. **Storage can hang.** `/pnfs` is a hard NFS mount; a file on an offline dCache pool blocks readers forever. Every file is checked in its own subprocess with a timeout (`io_timeout`),
   and dCache locality is evidence.
5. **Plan, run, gate.** Conversion first produces a read-only manifest over groups of sources (`convert | skip-valid | reconvert-stale | conflict`), then runs exactly that manifest; each stage ends in a gate
   (A, P, B, C) whose reasons are printed. Outputs are published by atomic rename; nothing is overwritten.
6. **Digest-based staleness.** Every conversion record carries `toolchain_digest = sha256(LCG view, ROOT version, rnt_convert binary, KEEP/DROP selection, compression)` and a `group_digest` over the exact sources (path, size, mtime, events). A changed digest marks the output stale; it is reconverted (the old file is renamed into `RNTuple_superseded/`), never silently reused.
   Grouping cut points are global over a masspoint, so changing one source regroups much of it: run cleanup before converting.
7. **Independent validation.** `rnt_validate` shares no code with the converter (separate type dispatch, TTreeReader vs RNTupleView) and compares values, not only counts; agents re-check with their own code and are given paths, not conclusions.
8. **Destructive actions are staged and human-gated.** Plan -> independent audit -> explicit approval of a manifest hash -> canary -> reversible quarantine -> post-audit; purge is a separate later run. Only the main session runs them. Conversion and validation delete nothing.
9. **Orchestration lives in the main session** (subagents cannot spawn subagents). Skills hold the playbook (`SKILL.md` only); code lives in `python/`, `scripts/`, `src/`.

### Definitions
Corrupted file reasons: `zombie`, `recovered`, `size0`, `no_tree`, `zero_events`, `read_error`, `missing_branch` (any of Electron_superclusterPhi, _superclusterEnergy, _DeltaEtaInSC, _DeltaPhiInSC, _DeltaPhiInSeed, _ecalPFClusIso, _hcalPFClusIso, _dr03HcalTowerSumEt),
`check_exception`, `io_timeout` (no result in 300 s: storage read hangs), `incomplete` (readable, but Events entries < sum of `GenFilter_numEventsPassed`: events silently lost). Warnings: `count_mismatch`, `no_genfilter_branches`.
Generator filter efficiency = sum(`LuminosityBlocks.GenFilter_numEventsPassed`) / sum(`GenFilter_numEventsTotal`) over clean files (`Runs.genEventCount` is post-filter).
Not importable, reported but not errors: trees with `edm::` branches (`MetaData`, `ParameterSets`) and non-tree objects (`tag`).

### Branch selection (KEEP/DROP)
`config/rntuple_branches.conf`: one rule per line, `KEEP|DROP [tree:]pattern` (shell glob, tree defaults to `Events`). Everything is kept by default; rules apply in order and the last match wins
(`DROP HLT_*` then `KEEP HLT_IsoMu24`). The 8 custom electron branches are protected; a collection's counter (`nPhoton`) is dropped automatically when all members are dropped and may never be dropped while a member is kept;
unmatched patterns and kept index branches pointing at a dropped collection (`Electron_photonIdx`) are warnings. `config/rntuple_branches.conf` holds the approved production table: `DROP HTXS_* Tau_* boostedTau_* Photon_* FsrPhoton_* IsoTrack_* LowPtElectron_* SoftActivityJet_* TauProd_* TauSpinner_* TrackGenJetAK4_*` plus `Electron_photonIdx`, `Electron_fsrPhotonIdx`, `Muon_fsrPhotonIdx` (254 of 2015 Events branches, nine counters such as `nTau`, `nPhoton` dropped automatically; ~17.7% of the Events TTree bytes; Tau 6.7%, Photon 3.6%, LowPtElectron 2.1%, boostedTau 1.5%, TrackGenJetAK4 1.1%, TauProd 0.9%, SoftActivityJet 0.8%, IsoTrack 0.5%). All `HLT_*` and `L1_*` trigger branches are kept (decision: keep all triggers). The resolver reports no warnings for this table. `config/rntuple_branches.test.conf` = `DROP Photon_*` (test only).
`python3 python/rnt_branches.py draft --inventory INV.csv --out config/rntuple_branches.draft.conf` writes a commented, inactive proposal grouped by prefix with sizes.

---------------------------------------------------------------------------------------------------

## 3. Output structure

```
results/
  overall.csv                       rollup of results/<mp>/qc/summary.csv (only cross-masspoint file)
  <mp>/
    pipeline.json                   what ran, with which run ids and digests
    qc/
      records.json                  per-file QC facts (authoritative input of aggregate.py; each record stamped with its run)
      files.csv  summary.csv        QC reports
      exclude.txt  removed.txt      excluded from QC (not deleted) / quarantined or purged paths
      current_run                   id of the run aggregate.py expects results from
      runs/<run_id>/                lists/ out/ logs/ params.json submit.sub driver.log   (legacy_20261025 = migrated old run)
      deletion/                     manifest_<ts>.csv(+.sha256), log_<ts>.csv, purge_<ts>.csv, *.origin
    rntuple/
      branch_selection.csv          resolved KEEP/DROP decisions (tree,branch,decision,type,zip_bytes,rule)
      manifest_<ts>.csv(+.sha256)   plan: one row per source file with its group, output, action, group digest, toolchain digest
      groups.csv                    provenance: output <- sources (events, size, mtime)
      conversion.csv                per OUTPUT: status, n_sources, group digest, events, bytes, trees converted/skipped, kept/dropped, digest, ROOT version, seconds, superseded, error
      validation.csv                per output: ok, entries, fields compared, missing/extra/type/value mismatches, RNTuple genEventCount and GenFilter sums
      summary.csv                   per masspoint: counts, events, QC cross-checks (events, genEventCount, efficiency), sizes, all_pass
      runs/<run_id>/                conversion (run_*) and validation (val_*) runs: lists/ out/ logs/ params.json submit.sub driver.log
/pnfs/knu.ac.kr/data/cms/store/user/choij/
  SampleFactory/<mp>/chain_RunIII2024Summer24/<ts>/NanoAODv15_<N>.root        sources (data only)
  SampleFactory_quarantine/<YYYYMMDD>/<mp>/chain_RunIII2024Summer24/<ts>/...   quarantined files
  RNTuple/<mp>/rntpl_<NNN>.root                                                converted RNTuple files, ~20k events each
  RNTuple_superseded/<date>/<mp>/rntpl_<NNN>.root.<run_id>                     replaced outputs, renamed aside (never deleted by the pipeline; purge only with approval via `python/purge_rnt.py`)
```
Other repo folders: `python/`, `scripts/`, `src/` + `CMakeLists.txt`, `config/`, `bin/` + `build/` (gitignored), `work/` (gitignored sandboxes).

---------------------------------------------------------------------------------------------------

## 4. Workflow graph (skills `[ ]` and agents `( )`)

```
/pipeline <mp>   [pipeline]  ── state: [pipeline-state] → results/<mp>/pipeline.json
 │
 ├─ 0 PREFLIGHT   [qc-env] pinned LCG_110 · [rnt-build] bin/ tools · [rnt-branches] KEEP/DROP resolver     (rnt-scout) on first use
 │
 ├─ 1 QC          [sample-qc] ─┬─ [qc-condor]  ← (qc-condor-runner)   submit / monitor / retry chunks
 │                             ├─ [qc-check-rootfile]  python/check_file.py
 │                             └─ [qc-report]  ← (qc-aggregator)      records.json · files.csv · summary.csv
 │                (qc-scout) discovery · (qc-verifier) independent re-check
 │    ▼
 │   G-A: no missing results · 8 custom branches present · QC fresh (file set + sizes unchanged) · corrupted files = 0 ?
 │        └─ corrupted > 0 ─► STOP ─► [qc-cleanup] ─ [qc-delete-manifest] ← (qc-delete-planner)
 │                                        ▼ audit ← (qc-delete-auditor)
 │                                        ▼ HUMAN APPROVAL (main session)
 │                                        └─ [qc-quarantine]: dry-run → canary → quarantine → post-audit ← (qc-delete-auditor)
 │                                           then re-aggregate, re-check G-A;  purge = separate later run
 │    ▼ pass
 ├─ 2 CONVERT     [rnt-manifest] ← (rnt-planner)  → manifest_<ts>.csv
 │                   ▼ G-P: no conflicts · space OK · plan counts reported
 │                [rnt-convert] + [rnt-branches] ← (rnt-condor-runner)   scripts/rnt_run_mp.sh <mp> convert → bin/rnt_convert
 │    ▼
 │   G-B: every clean file ok · output size as recorded · current toolchain digest · no .part/.failed leftovers
 │    ▼ pass
 ├─ 3 VALIDATE    [rnt-validate] ← (rnt-condor-runner)   scripts/rnt_run_mp.sh <mp> validate → bin/rnt_validate;  (rnt-validator) independent sample
 │    ▼
 │   G-C: all files pass · Events entries = QC n_events_clean · Runs.genEventCount = QC · efficiency (from RNTuple) = QC efficiency
 └─ 4 FINALIZE    [pipeline-state] → pipeline.json · results/overall.csv · report

One-time (done): [results-migration] python/migrate_results.py ← audit (layout-auditor)
```

| Stage | Skills | Agents | Main code | Writes | Gate |
|---|---|---|---|---|---|
| 0 Preflight | qc-env, rnt-build, rnt-branches, pipeline-state | rnt-scout | `scripts/env.sh`, `scripts/rnt_build.sh`, `python/rnt_branches.py`, `python/layout.py` | `bin/`, `rntuple/branch_selection.csv` | env + build + config |
| 1 QC | sample-qc, qc-condor, qc-check-rootfile, qc-report | qc-scout, qc-condor-runner, qc-aggregator, qc-verifier | `qc_run_mp.sh`, `make_submit.py`, `run_qc.sh`, `check_file.py`, `qc_merge.py`, `aggregate.py` | `results/<mp>/qc/*` | A |
| 1b Cleanup | qc-cleanup, qc-delete-manifest, qc-quarantine | qc-delete-planner, qc-delete-auditor | `make_manifest.py`, `quarantine.py`, `restore.py`, `purge.py`, `purge_rnt.py` | `qc/deletion/*`, quarantine dir | human approval |
| 2a Plan | rnt-manifest, rnt-branches | rnt-planner | `rnt_make_manifest.py`, `rnt_branches.py` | `rntuple/manifest_<ts>.csv` | P |
| 2b Convert | rnt-convert | rnt-condor-runner | `rnt_run_mp.sh`, `rnt_make_jobs.py`, `rnt_convert.sh`, `bin/rnt_convert`, `rnt_aggregate.py` | `/pnfs/.../RNTuple/<mp>/`, `rntuple/conversion.csv` | B |
| 3 Validate | rnt-validate | rnt-condor-runner, rnt-validator | `rnt_run_mp.sh`, `rnt_validate.sh`, `bin/rnt_validate`, `rnt_validate_report.py` | `rntuple/{validation,summary}.csv` | C |
| 4 Finalize | pipeline-state | – | `pipeline_state.py`, `pipeline_gate.py`, `rollup.py` | `pipeline.json`, `overall.csv` | – |
| One-time | results-migration | layout-auditor | `migrate_results.py` | `results/<mp>/` reorganized | audit |

---------------------------------------------------------------------------------------------------

## 5. Skills (16, `.claude/skills/<name>/SKILL.md`)
`qc-env` pinned toolchain · `qc-check-rootfile` corruption definition + checker · `qc-condor` per-masspoint condor QC runs · `qc-report` merge/aggregate/rollup · `sample-qc` QC stage playbook ·
`qc-delete-manifest` deletion manifest · `qc-quarantine` quarantine / restore / purge · `qc-cleanup` cleanup playbook · `rnt-build` C++ tools · `rnt-branches` KEEP/DROP ·
`rnt-manifest` conversion plan · `rnt-convert` conversion stage · `rnt-validate` validation stage · `pipeline-state` state + gates · `results-migration` one-time reorganization · `pipeline` the fixed workflow.

## 6. Agents (11, `.claude/agents/*.md`) - none performs a destructive step
| Agent | Tools | Job |
|---|---|---|
| `qc-scout` | Bash, Read, Grep, Glob | read-only discovery: masspoints/files, trees/branches of one file, locality of paths |
| `qc-condor-runner` | Bash, Read, Write | QC run of one masspoint (submit, monitor, retry max 2x) |
| `qc-aggregator` | Bash, Read, Write | merge + aggregate + invariants + rollup |
| `qc-verifier` | Read, Grep, Glob, Bash | independent re-check of flagged and sampled clean files with its own code |
| `qc-delete-planner` | Read, Bash, Grep | builds the deletion manifest (read-only) |
| `qc-delete-auditor` | Read, Grep, Bash | adversarial pre-/post-audit of a deletion |
| `rnt-scout` | Bash, Read, Grep, Glob | read-only discovery for conversion: env on workers, importer API, inventory, draft DROP list |
| `rnt-planner` | Read, Bash, Grep | builds/explains the conversion manifest; cannot write to /pnfs or submit |
| `rnt-condor-runner` | Bash, Read, Write | conversion or validation run of one masspoint (retry max 2x, gate result) |
| `rnt-validator` | Read, Grep, Bash | independent sample re-check of converted files, own code |
| `layout-auditor` | Read, Grep, Glob, Bash | audit of the results layout / reorganization |

## 7. C++ tools (`src/`, built into `bin/` by `scripts/rnt_build.sh`)
`rnt_convert [--branches TABLE] [--json OUT] [--compression N] (IN | --inputs LIST) OUT` (RNTupleImporter, several inputs are concatenated in order; branch selection by cloning only kept branches; `.part` + atomic rename; never overwrites; self-check of entry counts) ·
`rnt_inventory IN` (trees, branches, types, compressed bytes as CSV) · `rnt_validate [--table TABLE] [--json OUT] (IN | --inputs LIST) OUT` (TChain of the sources vs the merged RNTuple: entries, field set, types, value identity per field with order-sensitive checksums; exact equality).
RDataFrame was rejected for validation: its JIT needs about a minute per 300 columns.

## 8. Known pitfalls
- New or edited agents/skills are visible only after `/reload-plugins` / `/reload-skills`.
- Condor workers cannot see the login node's `/tmp`; sandboxes that run condor jobs must live on NFS (`work/`).
- `condor_q -constraint` needs ClassAd syntax: `regexp("<run dir>", Args)`; the run dir is followed by a space in `Args`, not a slash.
- `scripts/condor_wait.sh` removes jobs that are only held (reason printed) so the retry logic can resubmit.
- Output size: sources are ~3.4k events each; outputs are normalized to ~20k events (`config/rntuple_output.conf`: `TARGET_EVENTS`, `COMPRESSION`). Measured on one 20.9k-event group: zstd 505 63.3 MB, 509 60.6 MB, 512 60.2 MB (plateau), LZMA 209 60.1 MB but 2.2x slower full reads and 5x slower subset reads, so zstd 512 is used (read speed does not depend on the zstd level).
- Do not read `UNAVAILABLE` files with ROOT or `cat`; use the locality dot-file or a `timeout`-wrapped, backgrounded test.
- Paths in reports use the `/u/user/choij/SE_UserHome/...` symlink form; destructive tools always work on the `/pnfs/...` realpath.
