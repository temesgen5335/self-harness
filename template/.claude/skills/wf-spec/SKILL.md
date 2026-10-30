---
name: wf-spec
description: Phase 1b (plan) — turn the investigation into an approvable spec with acceptance criteria and a task breakdown. Run in a fresh session.
argument-hint: "[slug]"
disable-model-invocation: true
allowed-tools: Bash(git branch:*), Bash(python3 .claude/harness/scripts/*)
---
# Spec

Branch: !`git branch --show-current`

Read ONLY: `.work/<slug>/00-brief.md`, `.work/<slug>/10-investigation.md`, and code it cites when needed.
If the investigation has unanswered questions that change the design, ask a maintainer first (one message, numbered).

## Do
Track: `python3 .claude/harness/scripts/wf-track.py <slug>`. On the `lite` track write a short spec instead
(steps 2, 3 and 6 may be one line each, "n/a — lite"); acceptance criteria and tasks are still required.
If the work outgrows lite (the planner's `reasons`), switch: `wf-state.py <slug> set track=standard` and write the full spec.

1. Write `.work/<slug>/20-spec.md` from its template. Every section filled or marked "n/a — because …".
2. Design: give 2–3 real alternatives with trade-offs; choose one and say why. Prefer boring, observable, configurable.
3. Design for the review lenses up front: security model, scale budgets, observability, customisation points,
   failure-modes table, rollback. The reviewer will check exactly these (`.claude/harness/RUBRIC.md`).
4. Acceptance criteria: testable, numbered AC-n, each mapped to tests.
5. Tasks: T1..Tn, each about one commit, dependency-ordered, mapped to ACs, critical-path flagged.
6. Section 14: decisions a maintainer must make, each with your recommendation.
7. Set `Status: Draft` and `python3 .claude/harness/scripts/wf-state.py <slug> set phase=specified`.

## Approval
Only when a maintainer (lead or collaborator in harness.json `team`) explicitly approves in chat: set `Status: Approved`, add a line to the spec change log
with the date, and set `phase=approved`. Never self-approve.

## Finish with
TL;DR (approach, key trade-offs, decisions needed) and: "Next: approve, then `/wf-build <slug>` in a build session."
