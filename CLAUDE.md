# SampleFactoryQC
Checks private NanoAODv15 in /u/user/choij/SE_UserHome/SampleFactory (-> /pnfs/knu.ac.kr/data/cms/store/user/choij): corruption + 8 custom electron branches + generator filter efficiency (LuminosityBlocks GenFilter_numEventsPassed/Total).
- Run with `/sample-qc [mp|all]`. Skills/agents in .claude/. Output: results/<mp>/{files,summary}.csv, results/overall.csv.
- ROOT only via CMSSW_15_0_22 (el9_amd64_gcc12) in cmssw/; use qc-env. HTCondor for all bulk reads.
- Layout <mp>/chain_RunIII2024Summer24/<timestamp>/NanoAODv15_N.root; all timestamp dirs are independent files.

## Cleanup rules (destructive)
- Corrupted files are removed only via /qc-cleanup: manifest -> independent audit -> explicit user approval -> canary -> quarantine (rename to <root>_quarantine/<date>) -> post-audit. Purge (permanent) is a separate later run with its own approval.
- Destructive scripts (qc-quarantine) run only in the main session, never in subagents; never use rm/glob/recursive on /pnfs sample dirs. Use realpaths; /pnfs is a hard NFS mount, so wrap fs ops on UNAVAILABLE files in timeouts.
- config/exclude.txt = excluded from QC (not deleted); config/removed.txt = quarantined/purged paths.
