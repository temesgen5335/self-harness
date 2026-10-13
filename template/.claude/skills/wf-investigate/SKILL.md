---
name: wf-investigate
description: Phase 1 (plan) — investigate the facts for a work item and write .work/<slug>/10-investigation.md. Run in a fresh session.
argument-hint: "[slug]"
disable-model-invocation: true
allowed-tools: Bash(git branch:*), Bash(git log:*), Bash(ls:*), Bash(python3 .claude/harness/scripts/*)
---
# Investigate

Branch: !`git branch --show-current`
Work items: !`ls .work 2>/dev/null || echo none`

Slug = `$ARGUMENTS`, or the work item whose state.json branch matches the current branch. If neither, stop and ask.

Read: `.work/<slug>/00-brief.md`. Do not read old reviews or other work items.

## Do
1. Split the brief into 3–6 concrete investigation questions (codebase, external tech, prior art/pitfalls, constraints).
2. Launch `wf-researcher` subagents in parallel, one per question. Keep their raw output out of your reply.
3. Verify the current stable version and current API of every library or service this work touches, with today's date.
4. Fill `.work/<slug>/10-investigation.md` from its template. Facts need sources. Separate facts, inferences, unknowns.
5. List the questions only a maintainer can answer (product intent, priorities, constraints).
6. Update state: `python3 .claude/harness/scripts/wf-state.py <slug> set phase=investigated`

## Do not
- Design the solution or write code. That is the spec phase.
- Guess. Unverifiable = `[unknown]`.

## Finish with
TL;DR (key facts, risks, open questions) and: "Next: answer the open questions, then start a fresh session and run `/wf-spec <slug>`."
