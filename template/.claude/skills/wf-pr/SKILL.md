---
name: wf-pr
description: Draft the pull request for a work item that passed the gate — title, body from the project's PR template, base branch — and print the exact command. Never opens, pushes or merges anything itself.
argument-hint: "[slug]"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(python3 .claude/harness/scripts/*)
---
# Pull request draft

Branch: !`git branch --show-current`
Config: !`python3 .claude/harness/scripts/hconfig.py docs`

## Check first (stop and say what is missing)
1. Slug from `$ARGUMENTS` or the branch's state.json. `python3 .claude/harness/scripts/gate.py <slug> --no-write`
   must PASS for this head; otherwise name the blocking findings and stop.
2. No uncommitted code (`git status --porcelain`, ignoring the work dir).
3. If `validation.required` is true (`hconfig.py validation.required`): `.work/<slug>/60-validation.md` must
   record `go` or `go with accepted risk`. If it does not, say "manual validation is required before the PR —
   run /wf-validate <slug>" and stop; draft anyway only if the maintainer says so, and then the Testing section
   states "Manual validation: pending".
4. Base = harness.json `branching.base`, else `default_branch`. Diff size: `git diff --shortstat origin/<base>...HEAD`
   (the local `<base>` only when there is no remote);
   over ~400 changed lines, say so and suggest how to split.

## Draft
Read the spec (§1, §4, §11, §12), `git log --oneline <base>..HEAD`, the latest review round and, if present,
`.work/<slug>/60-validation.md`. Do not read the build log.
- **Title:** Conventional Commit, ≤ 72 chars, the main change (it becomes the squash commit).
- **Body:** the project's PR template (`docs.pr_template`) with every section filled from those artifacts — never
  left as template comments. Without a template use: What / Why / How / Testing / Screenshots / Risk and rollback.
  - Why: the ticket (state.json `ticket`, e.g. "Closes ACME-123") and the problem.
  - How: decisions and trade-offs from the spec, not a restatement of the diff. Link any ADR it created.
  - Testing: commands the review ran and their results, AC → test mapping, validation evidence if recorded.
  - Risk and rollback: spec §11, any waived findings with their reason.
  - Checklists: tick only what the artifacts prove; leave the rest unticked and say why below the list.
- **Docs:** if `docs.changelog` is set and the change is user-visible, check that the diff adds an `[Unreleased]`
  entry; if not, draft it and say it must be committed first.
- No attribution lines, no "Generated with" footer.

Write the title on line 1 and the body below it to `.work/<slug>/pr.md`, then print:

```
gh pr create --base <base> --head <branch> --title "<title>" --body-file <body file>
```

Use a body file holding the body only (e.g. `tail -n +3 .work/<slug>/pr.md > /tmp/<slug>-pr.md`). Never `--fill`.
Push and PR creation are the maintainer's: print the commands (`git push -u origin <branch>` first) and STOP.
