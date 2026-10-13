---
name: wf-handoff
description: Compress the current session's working state into the build log so a fresh session can continue without loss. Use when context is getting long or before switching sessions.
argument-hint: "[slug]"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*)
---
# Handoff

Append a `## HANDOFF — <date>` entry to `.work/<slug>/30-build-log.md` using the template format:
current task and step, what was done since the last handoff, uncommitted changes (files + intent),
decisions made and why, the next exact step (a command or file + function), and gotchas discovered.

Max ~25 lines. Facts only; no narrative. Then say:
"Handoff written. Run `/clear` (or open a new session) and continue with `/wf-build <slug>`."
