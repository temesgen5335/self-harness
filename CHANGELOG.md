# Changelog

All notable changes to this harness. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/). Nothing has been tagged yet: the first release will be
`v0.1.0` (`template/.claude/harness/VERSION`).

## [Unreleased]

### Added
- `/wf-handoff` continues a session in a fresh one, or with `--fork` starts a parallel session with its own goal.
  - The handoff file gets its facts from the script (transcript path, git state, board).
  - Claude fills the rest: constraints quoted verbatim, verified vs believed, ownership, resume steps.
- `/wf-sync` and `wf-sync.py`: parallel sessions share a board of one-line events (`DONE`, `CHANGED`, `NEW`,
  `NEED`, `DECIDED`). A `UserPromptSubmit` hook shows each session the other sessions' unread entries, capped.
- `sync.dir`: share one board between separate repos (for example a frontend and a backend repo).
- Check commands are detected from the repo on a fresh install or when a preset is applied. Sources: Makefile
  targets, package.json scripts with the lockfile's package manager, and Python (uv/poetry/pdm,
  ruff/flake8, mypy/pyright, pytest), Go and Rust conventions. Nothing is executed.
  - `install.sh --command key=value` sets a command; `--detect-commands` re-detects.
  - `detect-commands.py` lists the commands and flags any that cannot run here.
- Local mode creates an `AGENTS.md` for other coding agents (Codex, Cursor, …) when the repo has none, hidden
  through `.git/info/exclude`. A tracked or personal `AGENTS.md` is never touched.
- `/wf-pr` fills `.claude/harness/templates/pull-request.md` when the project has no PR template.
  It has What / Why / How / Testing / Screenshots / Risk and rollback, and a safety checklist.
- A pull request template for this repository.

### Changed
- A preset's command that the repo cannot run (missing script, make target or package.json script) is replaced
  by a detected one, or cleared when none is found. Commands you set yourself are only reported.
- The installer warns when no test command is left, because the gate then requires no tests.

### Fixed
- In warn mode the session banner said "commit: ask, push: block" although the guard only warns. It now says so.
