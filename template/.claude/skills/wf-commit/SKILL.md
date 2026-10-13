---
name: wf-commit
description: Draft Conventional Commit messages and the exact files to stage for the current changes. With "apply", stage and commit them — only when a maintainer explicitly asked in this conversation. Use whenever work is ready to commit.
argument-hint: "[slug] [apply]"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*)
---
# Commits

Status: !`git status --short`
Recent style: !`git log --oneline -8`

Rules: `.claude/harness/COMMITS.md` — type tag, clear title, short why-body, no Co-Authored-By or AI attribution.

## Draft (default)
1. Read `git diff` and `git diff --staged`. Group changes into the fewest atomic, logical commits
   (tests with their code; refactors separate from behaviour changes).
2. For each commit write:
   - **Files to stage** — exact paths. If a file mixes two commits, say `git add -p <file>` and which hunks.
   - **Message** — `type(scope): title`; a 1–3 line why-body only if it adds information; footers only if needed.
   - The type's release effect (minor / patch / none).
3. Check: no secrets, debug prints, stray files, or attribution in the diff or messages.
4. Overwrite `.work/<slug>/commit-drafts.md` with the same content (the loop script shows it).
5. Output the drafts as copy-ready blocks, then STOP.

## Apply (`$ARGUMENTS` contains `apply`)
Only if a maintainer explicitly asked for the commit in this conversation; otherwise draft and stop.
1. Draft first (steps above) unless current drafts already match the diff.
2. Per commit: `git add <exact paths>` then `git commit -F <message file>` — never `git add -A`/`.`,
   never `--no-verify`, never `--amend` unless asked. The guard asks the maintainer to confirm each command;
   a refusal means stop, not retry another way.
3. If the `commit-msg` hook rejects a message, fix the message and retry once.
4. Do not push unless explicitly asked as well. Report `git log --oneline -n <count>`.
