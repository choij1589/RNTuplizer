# SampleFactoryQC

Quality control and cleanup for private NanoAODv15 samples produced with custom electron branches
(CMSSW_15_0_22 campaign, KNU Tier-3). It checks every ROOT file for corruption, checks that the custom electron
branches exist, computes the generator filter efficiency, writes per-masspoint CSV reports, and (optionally and carefully)
removes the corrupted files.

Sample area: `/u/user/choij/SE_UserHome/SampleFactory` (a symlink to `/pnfs/knu.ac.kr/data/cms/store/user/choij/SampleFactory`),
layout `<masspoint>/chain_RunIII2024Summer24/<YYYYMMDD_HHMMSS>/NanoAODv15_<N>.root`.
Every timestamp directory is treated as independent files.

---------------------------------------------------------------------------------------------------

## 1. Quick start

Run everything from `/d0/scratch/choij/SampleFactoryQC` in a Claude Code session. After adding or editing agents/skills
run `/reload-plugins` (new agent types are not visible until then).

| Goal | Command |
|---|---|
| Run the whole QC (all masspoints) | `/sample-qc all` (or `/sample-qc <masspoint>`) |
| Look at results | `results/<masspoint>/files.csv`, `results/<masspoint>/summary.csv`, `results/overall.csv` |
| Remove corrupted files (safe, 2 stages) | `/qc-cleanup` (quarantine) then, much later, `/qc-cleanup purge` |
| Undo a quarantine | `python3 .claude/skills/qc-quarantine/scripts/restore.py --log results/deletion/log_<ts>.csv --apply` |

Without Claude (plain shell, bash):

```bash
cd /d0/scratch/choij/SampleFactoryQC
# one masspoint end to end
MP=TTToHcToWA_AToMuMu_MHc-130_MA-65_MultiLepFilter_TuneCP5_cff
S=$(python3 .claude/skills/qc-condor/scripts/make_submit.py $MP | awk '{print $1}'); condor_submit $S
bash .claude/skills/qc-condor/scripts/status.sh $MP              # chunks done/total, idle/running/held
python3 .claude/skills/qc-report/scripts/aggregate.py $MP        # files.csv + summary.csv (exit 2 = results missing)
python3 .claude/skills/qc-report/scripts/rollup.py               # results/overall.csv
# all masspoints, submitted at once, with retries and aggregation
nohup bash .claude/skills/sample-qc/scripts/run_all.sh > results/run_all.out 2>&1 &   # progress: results/run_all.log (ALLDONE)
# check a few files by hand
source .claude/skills/qc-env/scripts/env.sh
python3 .claude/skills/qc-check-rootfile/scripts/check_file.py /tmp/out.json file1.root file2.root
```

Rules of thumb: ROOT is only available after sourcing `qc-env` (system python has no ROOT/uproot). Use `bash` for scripts
(zsh does not word-split variables). Never match processes with `pkill -f <name>` in a command that itself contains that name.

---------------------------------------------------------------------------------------------------

## 2. Design concept

1. **Cheap, parallel, reproducible.** ~2,200 files / 33 GB are read in full (every branch of every event), so the work runs on
   HTCondor in chunks of 20 files (~16 min per job). ROOT comes from CMSSW_15_0_22 (`el9_amd64_gcc12`, created in `cmssw/`)
   and works identically on login and worker nodes (`/u`, `/d0`, `/pnfs` are NFS).
2. **Separate detection, aggregation and judgement.** Workers only write one JSON record per file (facts). All definitions that
   need cross-file or cross-tree reasoning (`incomplete`, exclusions, removed files, efficiency) are applied at aggregation, so
   rules can change without re-reading 33 GB.
3. **A job failure is not file corruption.** A chunk without output is "missing result" (aggregate exits 2 and the masspoint is not
   final); it is never counted as clean.
4. **Storage can lie or hang.** `/pnfs` is a `hard` NFS mount; a file on an offline dCache pool blocks the reader forever (process in
   `D` state). Each file is therefore checked in its own subprocess with a timeout (`io_timeout`), and dCache locality
   (`.(get)(file)(locality)`) is used as evidence.
5. **Independent verification.** Results are re-checked by a separate agent that writes its own PyROOT code and is given
   paths, never conclusions.
6. **Destructive actions are staged, guarded and human-approved.** Nothing is deleted in the step that decides it.
   Plan -> independent audit -> explicit user approval of a manifest hash -> canary -> reversible quarantine (rename) ->
   post-audit -> later, separately approved purge. Destructive scripts run only in the main session, never in subagents.
7. **Orchestration lives in the main session** (subagents cannot spawn subagents). Skills hold the logic and scripts; agents are
   thin, tool-restricted workers that follow a skill.

### Definitions

A file is **corrupted** if any of these reasons applies:

| Reason | Meaning |
|---|---|
| `zombie` | cannot be opened / truncated (footer missing) |
| `recovered` | ROOT had to recover the file |
| `size0` | smaller than 1000 bytes or missing |
| `no_tree` | `Events`, `Runs` or `LuminosityBlocks` missing |
| `zero_events` | Events has 0 entries |
| `read_error` | `GetEntry` < 0 or exception on Events / Runs / LuminosityBlocks (bad baskets) |
| `missing_branch` | any of the 8 custom branches is absent (below) |
| `check_exception` | the checker crashed on the file |
| `io_timeout` | no result within `QC_FILE_TIMEOUT` (300 s): storage read hangs (seen: dCache locality `UNAVAILABLE`) |
| `incomplete` | valid ROOT but Events entries < sum of `GenFilter_numEventsPassed` (events silently lost); added at aggregation |

Warnings (not corruption): `count_mismatch` (Events entries != sum of `Runs.genEventCount`), `no_genfilter_branches`.

Custom electron branches: `Electron_superclusterPhi`, `Electron_superclusterEnergy`, `Electron_DeltaEtaInSC`, `Electron_DeltaPhiInSC`,
`Electron_DeltaPhiInSeed`, `Electron_ecalPFClusIso`, `Electron_hcalPFClusIso`, `Electron_dr03HcalTowerSumEt`.

**Generator filter efficiency** = sum(`LuminosityBlocks.GenFilter_numEventsPassed`) / sum(`GenFilter_numEventsTotal`) over clean files,
with binomial error. (`Runs.genEventCount` is post-filter and cannot give it.)

**Event accounting:** `n_events` of a corrupted file is its Events entry count, or 0 if unreadable (then it appears in
`n_files_unreadable`). So `n_events_total` is a lower bound while unreadable files exist.

---------------------------------------------------------------------------------------------------

## 3. Repository layout

```
README.md  CLAUDE.md
.claude/skills/<name>/SKILL.md (+ scripts/)     skills (logic + scripts)
.claude/agents/*.md                             agents (tool-restricted workers)
cmssw/CMSSW_15_0_22/                            ROOT environment (created by qc-env)
config/exclude.txt                              paths/globs excluded from QC (NOT deleted)
config/removed.txt                              paths quarantined/purged (dropped from reports, counted as removed)
results/<masspoint>/files.csv, summary.csv      per-masspoint reports
results/<masspoint>/.work/{lists,out,log}       condor chunk lists, per-chunk JSON, logs
results/overall.csv                             one row per masspoint
results/run_all.log                             driver log (ALLDONE when finished)
results/deletion/manifest_*.csv(+.sha256), log_*.csv, purge_*.csv   cleanup manifests and audit trail
```

### Report columns

`files.csv`: `path, timestamp_dir, size_bytes, n_events, corrupted, reasons, events_missing, warnings, missing_branches`

`summary.csv`: `masspoint, n_files, n_files_corrupted, n_files_clean, n_events_total, n_events_corrupted, n_events_clean,
n_files_unreadable, gen_num_passed, gen_num_total, filter_efficiency, filter_eff_err, n_files_incomplete,
n_events_missing_incomplete, n_files_missing_result, n_files_removed, all_custom_branches_present`
(invariants: clean + corrupted = total; `files.csv` rows = `n_files` = `.root` files on disk minus excluded/removed).

---------------------------------------------------------------------------------------------------

## 4. Skills

| Skill | Purpose | Key scripts |
|---|---|---|
| `qc-env` | Sets up CMSSW_15_0_22 (`el9_amd64_gcc12`) for PyROOT locally and on workers. | `scripts/env.sh` (source it; creates the release area on first use) |
| `qc-check-rootfile` | Corruption definition and the per-file checker. Each file is checked in its own subprocess with a 300 s timeout. Emits JSON: sizes, entries, readable entries, missing branches, reasons, warnings, GenFilter sums. | `scripts/check_file.py OUT.json FILE...` |
| `qc-condor` | Splits a masspoint into chunks of 20 files, submits, monitors, resubmits. Chunks write atomically (tmp + mv), so a present `chunk_N.json` is complete. | `make_submit.py <mp> [--only ids]`, `run_qc.sh` (worker wrapper), `status.sh <mp>` (also writes `.work/missing.txt`), `retry_failed.py [--reason io_timeout] [--submit]` |
| `qc-report` | Merges chunk JSONs into the CSVs; applies `incomplete`, `config/exclude.txt` and `config/removed.txt`; rollup across masspoints. | `aggregate.py <mp>` (exit 2 = missing results), `rollup.py` |
| `sample-qc` | Orchestrator playbook, `/sample-qc [mp\|all]`. | `run_all.sh [batch]` (all masspoints at once by default; idempotent, resubmits only missing chunks, retries twice, aggregates, rolls up) |
| `qc-delete-manifest` | Builds the deletion manifest (+ sha256 and a per-masspoint "healthy events after removal >= 300000" guard). Read-only, never reads file data. | `make_manifest.py [--min-healthy N]` |
| `qc-quarantine` | The only code that moves/removes samples. Dry-run by default. | `quarantine.py`, `restore.py`, `purge.py`, `common.py` |
| `qc-cleanup` | Orchestrator playbook for removal, `/qc-cleanup [purge]`. | (uses the two skills above) |

Retry mechanism: `retry_failed.py` puts files with a given reason into an extra chunk `chunk_rNNN`; during aggregation the later
chunk record overrides the earlier one for the same path.

### qc-quarantine in detail

- `quarantine.py --manifest M --confirm-hash <sha256 of M> [--canary] [--apply] [--root R] [--qc Q] [--no-condor-check]`
  Per-file hard checks (a failure means skip and report, never "fix"): the real path matches
  `<root>/<mp>/chain_RunIII2024Summer24/<14-digit ts>/NanoAODv15_<N>.root`; regular file, not a symlink; size and mtime equal to the
  manifest; destination does not exist; no condor jobs of the user are queued; and fresh evidence:
  `io_timeout` rows must still be locality `UNAVAILABLE` (otherwise skip: "recovered, re-QC it"), other rows are re-checked
  with `check_file.py` and must still be bad. Action: `mv --no-clobber` (a metadata-only rename on the same filesystem) into
  `<root>_quarantine/<YYYYMMDD>/<same relative path>`, every filesystem call under a 60 s timeout. After each move it verifies
  source gone / destination present / same size, and stops the whole run on any failure. Appends to the audit log
  `results/deletion/log_<ts>.csv` and to `config/removed.txt`. It never uses `rm`, globs or recursion.
- `restore.py --log L [--apply]` moves quarantined files back (refuses to overwrite) and removes them from `config/removed.txt`.
- `purge.py --log L --confirm-hash <sha256 of L> [--apply]` permanently unlinks only files that the log lists as quarantined and that
  are inside the quarantine directory with the logged size. Writes `purge_<ts>.csv`.

---------------------------------------------------------------------------------------------------

## 5. Agents

All agents are read-only or limited; none performs a destructive step. The main session decides, the user approves.

| Agent | Tools | Job |
|---|---|---|
| `qc-scout` | Bash, Read, Grep, Glob | Discovery: list masspoints/files, probe trees and branches of one file (Events, Runs, LuminosityBlocks incl. `GenFilter_*`), confirm the 8 custom branches, check path visibility. Never modifies samples or submits jobs. |
| `qc-condor-runner` | Bash, Read, Write | Runs one masspoint on HTCondor following `qc-condor`: create, submit, monitor (>= 60 s between checks), resubmit missing/held chunks up to 2 times. Reports job failures with causes; never edits check logic or deletes samples. |
| `qc-aggregator` | Bash, Read, Write | Runs `aggregate.py` / `rollup.py` and validates invariants (clean + corrupted = total, rows = `find` count, no missing results, efficiency in (0,1]). |
| `qc-verifier` | Read, Grep, Glob, Bash | Independent re-check: re-opens all flagged files plus random clean files with its own PyROOT code (entries, 8 branches, full `GetEntry` loop, GenFilter sums), re-sums CSV totals, recomputes the efficiency. For `io_timeout` files it only tests with `timeout cat`. Reports mismatches only. |
| `qc-delete-planner` | Read, Bash, Grep | Builds the deletion manifest and guard table; may run only read-only commands. |
| `qc-delete-auditor` | Read, Grep, Bash | Adversarial audit. PRE mode (given a manifest path): the manifest must equal the recomputed `corrupted=1` set exactly, sha256 and path-pattern valid, no healthy or excluded file, per-masspoint healthy events >= 300000, and independent evidence per row (dCache locality for `io_timeout`, Events vs GenFilter for `incomplete`; never opens unavailable files). POST mode (given a log): sources gone, destinations present with the right sizes, quarantine tree contains exactly the logged files, `removed.txt` and CSVs consistent. |

Guidance: give verifiers/auditors file paths, not the conclusion you expect.

---------------------------------------------------------------------------------------------------

## 6. Workflows

### 6.1 QC (`/sample-qc`)

0. **Discovery gate.** `qc-scout` + `qc-env`: list masspoints/files, confirm trees and branches (including `GenFilter_*` in
   `LuminosityBlocks`). Stop and show anything unexpected.
1. **Pilot gate.** Smallest masspoint end to end on condor, aggregate, then `qc-verifier`. Confirms worker visibility of `/pnfs`,
   runtime and memory. Do not change check logic afterwards without re-running the pilot.
2. **Fan-out.** All remaining masspoints submitted at once (HTCondor schedules); `run_all.sh` waits, resubmits missing chunks
   (max 2 retries) and aggregates.
3. **Per-masspoint close.** `aggregate.py` must exit 0 (every file has a result).
4. **Final gate.** `rollup.py`, report corrupted files / job failures / anomalies (efficiency spread, missing branches),
   `qc-verifier` spot check, summary to the user. Re-runs skip masspoints that already have a `summary.csv` unless forced.

Typical timeline: ~16 min per chunk job; a hanging file adds up to 5 min. If a job runs far longer than 20 min it is blocked on
storage: `condor_ssh_to_job <id>` and look for `D`-state `check_file.py`, then
`ls -l /proc/<pid>/fd` for the file and `cat <dir>/.(get)(<file>)(locality)`.

### 6.2 Retrying unreadable files

`python3 .claude/skills/qc-condor/scripts/retry_failed.py --submit`, wait for the jobs, then re-run `aggregate.py` for the affected
masspoints and `rollup.py`. If files stay `UNAVAILABLE`, ask the dCache admins to bring the pools back.

### 6.3 Cleanup (`/qc-cleanup`)

0. **Preconditions.** No QC condor jobs; `files.csv`/`summary.csv` are final.
1. **Plan.** `qc-delete-planner` (or `make_manifest.py`) writes `results/deletion/manifest_<ts>.csv` and its `.sha256`; exit code 3 means a
   masspoint would drop below the healthy-events guard (300k) and the run stops.
2. **Audit gate.** `qc-delete-auditor` (PRE) must report zero discrepancies.
3. **Human gate.** The main session shows the per-masspoint table, lists the `UNAVAILABLE` files separately (they are not proven
   corrupt), the total size and the manifest hash, and asks for explicit approval (AskUserQuestion). An agent's report is never approval.
4. **Execute.** `quarantine.py` dry-run, then `--canary --apply`, verify, then `--apply` with the same hash.
5. **Post-audit.** `qc-delete-auditor` (POST); re-run `aggregate.py` for all masspoints and `rollup.py`.
6. **Purge (separate, later).** `/qc-cleanup purge`: recheck dCache locality of the `io_timeout` files (any now `ONLINE` should be
   restored and re-QC'd instead), ask again with the hash of the quarantine log, then `purge.py --apply`.

Quarantine location: `/pnfs/knu.ac.kr/data/cms/store/user/choij/SampleFactory_quarantine/<YYYYMMDD>/`.

### 6.4 Exclusions

Add a path or fnmatch glob to `config/exclude.txt` to drop a file from QC (it stays on disk; example: a leftover test file),
then re-run `aggregate.py` for its masspoint and `rollup.py`.

---------------------------------------------------------------------------------------------------

## 7. Status of the first production QC (2026-10-25)

- 23 masspoints (MHc-130, MA = 15..125 in steps of 5), 2,165 files; 1 stray leftover test file excluded
  (`MA-90/.../20261019_043451/NanoAODv15_.root`); 2,164 files checked.
- 23 files were corrupted (13 `io_timeout` with dCache locality `UNAVAILABLE`, 10 `incomplete`); all 8 custom electron branches
  were present in every file that could be opened.
- The 23 files were moved to quarantine (not yet purged). After re-aggregation: 2,141 files, 0 corrupted, 7,176,252 healthy
  events, at least 301,809 per masspoint. Filter efficiency (clean files) ranges from 0.544 (MA-125) to 0.703 (MA-55).
- The stray MA-90 file was also moved to quarantine on request (logged in `results/deletion/manual_removals.csv`; its now-empty
  timestamp directory `20261019_043451` was left in place). The sample area now holds exactly the 2,141 checked files; the
  quarantine holds 24 files.
- Pending: decide on the purge (see 6.3 step 6).

## 8. Known pitfalls

- New or edited agents/skills are visible only after `/reload-plugins` / `/reload-skills`.
- `condor_q -constraint` needs ClassAd syntax: `regexp("<path>", Args)`, not `~=`.
- `condor_rm <user>` removes all of the user's jobs; remove by cluster id (`condor_q -constraint 'regexp("SampleFactoryQC/results", Args)' -af ClusterId`).
- Do not read `UNAVAILABLE` files directly with ROOT/`cat`; use the locality query or a `timeout`-wrapped, backgrounded test.
- Paths in `files.csv` use the `/u/user/choij/SE_UserHome/...` symlink form; cleanup scripts always work on the `/pnfs/...` realpath.
