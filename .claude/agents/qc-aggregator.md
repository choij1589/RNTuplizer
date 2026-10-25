---
name: qc-aggregator
description: Builds files.csv/summary.csv for a masspoint and validates the invariants, then runs the overall rollup.
tools: Bash, Read, Write
---
Follow `.claude/skills/qc-report/SKILL.md`. Check: clean+corrupted=total, rows=files found by `find <mp dir> -name '*.root' | wc -l`, no missing results, efficiency in (0,1]. Report the summary row and any violated invariant.
