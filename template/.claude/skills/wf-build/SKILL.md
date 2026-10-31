---
name: wf-build
description: Phase 2 (build) — implement exactly one spec task test-first, run all checks, log it, and draft commits. Repeat per task.
argument-hint: "[slug] [task-id]"
disable-model-invocation: true
allowed-tools: Bash(git branch:*), Bash(git status:*), Bash(tail:*), Bash(python3 .claude/harness/scripts/*)
---
# Build one task

Branch: !`git branch --show-current`
Tree: !`git status --short | head -20`

## Preconditions (stop if any fails)
- `.work/<slug>/20-spec.md` has `Status: Approved`.
- Working tree is clean, or the dirty files belong to the task in progress (check the build log tail).

## Context to load (and nothing more)
- The spec sections for this task: its row in §13, its ACs in §12, and the design sections it touches.
- The last ~60 lines of `.work/<slug>/30-build-log.md` (latest HANDOFF if present).
- Commands from `.claude/harness/harness.json`.

## Do
1. Pick the task: `$ARGUMENTS` task id, else the first `pending` task whose dependencies are done.
2. Write or extend tests for the task's ACs first; run them and confirm they fail for the right reason.
3. Implement the smallest change that passes. Follow the spec; verify any library API against current docs.
4. Bake in the review lenses as you go: input validation, timeouts, bounded resources, structured logs, config not constants.
5. Run every configured check (lint, typecheck, test, build). Paste each command and its one-line result.
6. Self-check against `.claude/harness/RUBRIC.md` for the touched code; fix what you find.
7. Append a build-log entry, set the task row to `done`, `wf-state.py <slug> set phase=building`.
   If this session is on a sync board (`wf-sync.py whoami`) and another session depends on this task or a shared
   interface changed, post `DONE` / `CHANGED` with the commit as `--ref` (`/wf-sync`).
8. Draft commits by following `/wf-commit` (draft only). Then STOP. Do not start the next task unless told "continue".

## If the spec is wrong or incomplete
Write a "Spec Change Request" entry in the build log (what, why, options) and stop for a maintainer.

## When all tasks are done
Set `phase=built` and say: "Next: after you commit, open a fresh session and run `/wf-review <slug>`."
