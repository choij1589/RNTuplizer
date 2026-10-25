---
name: qc-env
description: Set up CMSSW_15_0_22 (el9_amd64_gcc12) so PyROOT is available locally and on HTCondor workers. Use before any ROOT work in SampleFactoryQC.
---
Source `scripts/env.sh` (`source /d0/scratch/choij/SampleFactoryQC/.claude/skills/qc-env/scripts/env.sh`). It creates `cmssw/CMSSW_15_0_22` on first use and runs `cmsenv`. System python has no ROOT/uproot, so every ROOT command must run after this. Never install packages.
