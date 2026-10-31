---
name: wf-handoff
description: Hand this session's work to a fresh session without losing context. Continue the same goal when context is getting long (~60%), or --fork a parallel session with its own goal (e.g. frontend and backend) that stays in sync through a shared board. Use before /clear, when context is long, or when splitting work.
argument-hint: "[name] | --fork <name> \"<goal>\" [--board <board>] [--as <my-name>]"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(python3 .claude/harness/scripts/*)
---
# Handoff

Branch: !`git branch --show-current`

Two modes:
- **continue** — `/wf-handoff [name]`: a fresh session picks up this exact goal. Default name: the work item's
  slug, else the branch's last path segment. If this session is on a sync board, the new one takes its place.
- **fork** — `/wf-handoff --fork <name> "<goal>"`: a parallel session with a different goal (another task, the
  other half of a feature). Both join a sync board (default: the work item slug, else the repo directory name);
  `--as` names this session's own side (default `main`), e.g. `--fork frontend "…" --as backend`.

## 1. Prepare — the script fills in the facts
- continue: `python3 .claude/harness/scripts/wf-sync.py handoff <name>`
- fork: `python3 .claude/harness/scripts/wf-sync.py handoff <name> --board <board> --as <my-name>`

It prints JSON: `handoff` (a file whose Session section already holds the transcript path, git state and board),
`session_id` and `launch`. Files live in the git dir, shared by worktrees and never committed.

## 2. Fill every section of the handoff file
- **Complete beats short.** Short wording, but every fact the new session needs. Write "none" rather than
  dropping a section. Anything left out is lost, except through the transcript path.
- **Constraints from the user: verbatim**, with the date. Include rules stated in this session that are not in
  CLAUDE.md or the harness rules.
- **Verified vs believed.** Put a claim under "verified" only with the command and result, or the commit, that
  proves it. Everything else goes under "believed".
- **Pointers, not dumps:** `file:line`, commit, doc path, config key. The transcript covers the long tail.
- **Never** secret values, `.env` contents, or personal data.
- **fork:**
  - Goal is the new goal, what done looks like, and what to ignore from this session's work.
  - Ownership lists the paths each session owns; neither edits the other's.
  - For the same repo, give the fork its own checkout: `.claude/harness/scripts/wf-new.sh <slug> "<goal>"`
    (worktree + branch). Put its path in Resume and prefix the launch command with `cd <path> &&`.
- On a work item, also append the short `## HANDOFF` entry to `.work/<slug>/30-build-log.md` (template format),
  with a line pointing to the handoff file.

## 3. Check it
Read the handoff as the new session will. Could it take the first Resume step without asking the user anything,
and without repeating work already verified? If not, add what is missing.

## 4. Hand over, then STOP
Print the `launch` command in a code block. Never start the session yourself.
- continue: "Run it in a new terminal; this session can then be closed."
- fork: "Run it in a new terminal and keep this one open. Both sessions see each other's board posts at their
  next prompt; post with `/wf-sync`."
