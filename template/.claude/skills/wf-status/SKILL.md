---
name: wf-status
description: Show all harness work items with phase, review round, and gate verdict, and the next step for the current branch.
allowed-tools: Bash(.claude/harness/scripts/wf-status.sh), Bash(git branch:*)
---
!`.claude/harness/scripts/wf-status.sh`

Current branch: !`git branch --show-current`

Summarise in 3–5 lines: what is in flight, what is blocked, and the next command for the current branch.
