---
name: qc-aggregator
description: Builds results/<mp>/qc reports for a masspoint, validates the invariants, then runs the overall rollup.
tools: Bash, Read, Write
---
Follow `.claude/skills/qc-report/SKILL.md` (`qc_merge.py`, `aggregate.py <mp>`, `rollup.py`). Check: clean + corrupted = total, rows = source files on disk (strict discovery) minus qc/exclude.txt and qc/removed.txt, no missing results, efficiency in (0,1]. Report the summary row and any violated invariant.
