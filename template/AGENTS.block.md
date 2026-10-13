## Harness (managed by install.sh — edit outside these markers)

This repo uses the Claude Code harness. Full rules: `.claude/harness/RULES.md`; config and team: `.claude/harness/harness.json`.
These rules apply to every coding agent, not only Claude:

- Work flows through `.work/<slug>/`: brief → investigation → approved spec → build one task at a time → independent review → gate.
- Build only what the approved spec says. Only a maintainer (team lead or collaborator) approves a spec or waives a finding.
- Never claim a check passed without running it; report the command and result.
- Git: do not stage, commit, push, open PRs, merge, tag or release unless a maintainer explicitly asks in the current
  conversation. Commits use Conventional Commits (`.claude/harness/COMMITS.md`): concise type-tagged title,
  short body, and no Co-Authored-By or other AI attribution.
- Never rewrite history, discard others' changes, or bypass git hooks (`--no-verify`).
