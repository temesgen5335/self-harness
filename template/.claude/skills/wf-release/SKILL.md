---
name: wf-release
description: Phase 4 (publish) — go/no-go check for the pending release-please release PR. Never merges, tags, or publishes.
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(gh pr list:*), Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh run list:*), Bash(ls:*), Bash(cat:*)
---
# Release readiness

Last tag: !`git describe --tags --abbrev=0 2>/dev/null || echo none`
Release PR: !`gh pr list --label "autorelease: pending" --json number,title,url 2>/dev/null || echo "gh unavailable"`

## Check (report each as pass / fail / n-a with evidence)
1. On the default branch, up to date with origin.
2. Every work item merged since the last tag has `50-gate.md` with `Verdict: PASS` for its final head, or a recorded waiver.
3. CI is green on the default branch head (`gh run list --branch <default> --limit 5`).
4. The release PR's version bump matches the commits: breaking → major (or minor pre-1.0), feat → minor, fix/perf → patch.
   Flag commits whose type looks wrong for their diff (e.g. a user-visible change typed `chore`).
5. CHANGELOG reads well for users; breaking changes have migration notes.
6. Operational readiness: migrations ordered and reversible, new config has defaults and docs, feature flags set,
   rollback path known, monitoring for new paths exists.

## Output
TL;DR with **GO** or **NO-GO**, the blockers, and the exact actions for the maintainer
(e.g. "merge release PR #42", "fix commit type via PR title before merge"). Then stop.
