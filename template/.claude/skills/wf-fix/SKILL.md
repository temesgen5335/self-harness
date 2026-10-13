---
name: wf-fix
description: Phase 3b (fix) — address the latest review's open findings test-first, write a response for the next reviewer, and draft commits. Run in the build session (or a fresh one; artifacts carry the context).
argument-hint: "[slug]"
disable-model-invocation: true
allowed-tools: Bash(cat:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(ls:*), Bash(python3 .claude/harness/scripts/*)
---
# Fix review findings

Branch: !`git branch --show-current`

1. Slug from `$ARGUMENTS` or the branch's state.json. Load `.work/<slug>/50-gate.md`, the latest `R<n>.md` and `R<n>.findings.json`, plus the spec sections the findings touch.
2. Order open findings: blocking/security first, then by exposure, highest first.
3. For each finding you fix:
   - Write the regression test from the finding; run it; confirm it FAILS on current code.
   - Fix at the root cause, not the symptom. Run the test again plus all configured checks.
4. If you believe a finding is wrong: do not change code. Mark it `disputed` with concrete evidence.
5. If a fix needs a design change: write a Spec Change Request in the build log and stop for a maintainer.
6. If only a human can accept the risk: mark `deferred — needs waiver` with the trade-off; never write waivers yourself.
7. Write `.work/<slug>/40-reviews/R<n>.response.md`: per finding id → `fixed` (test name) | `disputed` (evidence) | `deferred` (reason).
   Do not edit the reviewer's findings JSON; only the next review round can mark findings `verified`.
8. Append a build-log entry, `wf-state.py <slug> set phase=fixing`, draft commits via `/wf-commit`, then STOP.

Finish with: "Next: commit, then a fresh session: `/wf-review <slug>` (or re-run `wf-loop.sh <slug>`)."
