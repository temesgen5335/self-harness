---
name: wf-review
description: Phase 3 (review) — independent multi-lens review of COMMITTED work for a work item, scored with the risk model, followed by the gate. Must run in a fresh session, one session per round.
argument-hint: "[slug]"
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(python3 .claude/harness/scripts/*), Bash(ls:*)
---
# Review round

Branch: !`git branch --show-current`
Uncommitted: !`git status --porcelain | head -10`
Previous rounds: !`ls .work/*/40-reviews/ 2>/dev/null | tail -5`

You are an independent reviewer. You did not write this code and you owe it nothing.
You never edit source or tests. You write only under `.work/<slug>/`.

## Setup
1. Slug from `$ARGUMENTS` or the branch's state.json. If uncommitted changes exist, note that they are NOT reviewed.
2. `base` = state.json `base` (fall back to `git merge-base origin/<default_branch> HEAD`); `head` = `git rev-parse HEAD`.
3. Round n = number of existing `R*.findings.json` + 1. Load the previous round's findings (if any) and
   `R<n-1>.response.md` from the builder (fixed / disputed / deferred per finding).
4. Read the spec (§3, §4–§12) and `git log --oneline base..head`, `git diff --stat base...head`. Do not read the build log.

## Run checks yourself
Run every non-empty command in `.claude/harness/harness.json` (`lint`, `typecheck`, `test`, `build`, `stress`).
A failing check is a finding (`executed-repro`). Never trust a claim that checks passed.

## Fan out (parallel)
- One `wf-lens-reviewer` per lens in `harness.json` `review.lenses`. Give each: lens, slug, base, head,
  and the previous findings for that lens.
- If `review.adversary` is true: one `wf-adversary` with slug, base, head, and the spec's critical tasks.

## Consolidate
1. Merge and de-duplicate findings; renumber as F-001…; keep stable ids for carried-forward findings.
2. Re-score each with `.claude/harness/RISK.md` bands. Higher band when torn. Reject findings without evidence.
3. Disputed findings: rule on them with evidence → `rejected` or stays `open`.
4. AC coverage: list any acceptance criterion without a test that would fail → finding (class functional, blocking).
5. Write `.work/<slug>/40-reviews/R<n>.findings.json`:
   `{"round": n, "base": "<sha>", "head": "<full sha>", "date": "<iso>", "checks": {"test": "pass|fail|n/a", ...},
   "lenses_run": ["correctness", ...], "adversary_run": true|false, "findings": [...]}`
   List only lenses whose subagent actually returned. The gate blocks on missing lenses or checks not reported `pass`.
6. Write `.work/<slug>/40-reviews/R<n>.md`: TL;DR, check results, findings ordered by exposure
   (each: what, where, evidence, fix, regression test), and what is genuinely good (one short list).
7. Run `python3 .claude/harness/scripts/gate.py <slug>` and include its verdict.
8. `wf-state.py <slug> set phase=reviewed review_round=<n>`; on PASS also `phase=passed`.

## Finish with
TL;DR: verdict, top 3 risks, and the exact next step
(BLOCK → "`/wf-fix <slug>` in the build session"; PASS → "open the PR"; ESCALATE → "revisit the spec").
