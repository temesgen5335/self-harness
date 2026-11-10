<!-- Title: a Conventional Commit of 72 characters or fewer, e.g. "feat(guard): cover git worktree remove".
     Fill every section; write "n/a" and the reason instead of deleting one.
     This repository is public: never include secrets, tokens, .env contents, raw logs, personal data,
     or the names of companies, clients or private projects (keep those in presets/local/, which is gitignored). -->

## What
<!-- The change in one to three sentences: what a harness user will notice. -->

## Why
<!-- The problem it solves; link the issue or the docs/upgrade-plan.md item. -->

## How
<!-- Key decisions and trade-offs, and the alternatives rejected. Not a restatement of the diff. -->

## Testing
<!-- `python3 -I tests/test_harness.py` on Python 3.8 and the latest Python: the one-line result for each.
     New tests and the behaviour each one proves; whether you checked that they fail without the change.
     Anything verified by hand (an install into a throwaway repo, a live Claude Code session) and how. -->

## Screenshots
<!-- Terminal output or session banner, if the change is visible there. "n/a" otherwise. -->

## Risk and rollback
<!-- Which installed projects are affected and how: hooks, guard decisions, gate verdicts, config keys.
     Upgrade path for existing installs (install.sh --force). How to roll back. -->

## Checklist
<!-- Tick only what is true; explain every unticked item below the list. -->
- [ ] One concern, small enough to review in one sitting (about 400 changed lines or fewer)
- [ ] Tests cover the change and fail without it; the suite passes on Python 3.8 and the latest Python
- [ ] Works in both tracked and local mode; local mode still leaves `git status` clean
- [ ] Existing installs upgrade without losing their `harness.json` edits
- [ ] A hook that fails never blocks the user by accident; a guard that must block fails closed
- [ ] No secrets, credentials, personal data, or company, client or project names
- [ ] No new dependencies (stdlib only), or the new one is justified and pinned
- [ ] README and docs/upgrade-plan.md updated for user-visible changes
- [ ] Automated review run and every comment addressed
