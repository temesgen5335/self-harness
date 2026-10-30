# Upgrade plan: harness draft → v0.1.0

Date: 2026-10-13 · Status: in progress
Inputs: the v0.1-draft code review, [research-plan.md](research-plan.md), and maintainer decisions (below).

The harness stays a **v0.1 draft** until every stage below is done. Then it is published on GitHub
(`temesgen5335/self-harness`) and tagged `v0.1.0`; there are no intermediate versions.

## Maintainer decisions (2026-10-13)
| # | Decision |
|---|---|
| D1 | Commits: never unless explicitly asked; concise type-tagged title, short body, no Co-Authored-By/AI attribution |
| D2 | Gate and git guard configurable from restrictive to optional (profiles + per-key overrides) |
| D3 | Team support: setup person is the default lead; any number of collaborators |
| D4 | The harness writes its core rules into `AGENTS.md` too (managed block) |
| D5 | Lite track threshold: about 150 changed lines and no `critical_paths` |
| D6 | Installs are pinned by commit SHA (documented and verified by `bootstrap.sh --sha`) |
| D7 | Local mode: the harness can run in a repo with no trace in git (team or client repos where the workflow is personal) |

## Stage 1: safe, reusable, configurable ✅ done (2026-10-13)
| Item | What changed | Verified by |
|---|---|---|
| Repo cleanup | Removed the duplicate zip, README, bootstrap, `.DS_Store` and `__pycache__`; docs moved into `harness/docs/` | — |
| Config layer | New `hconfig.py`: profiles `strict` / `standard` / `light` + per-key overrides; `hconfig.py [key]` prints effective config | tests |
| Git guard (D1, D2) | Rewritten in Python: shlex parsing, recursion into `bash -c` / `$(…)` / backticks / `eval`, git global options skipped, 10 ops, each `allow` / `ask` / `block`; blocks on parse errors, missing python or bad config | 87-command corpus + 6 tests |
| Commit policy (D1) | `COMMITS.md`, `RULES.md` and `/wf-commit apply`: commit only on request, confirmed per command via the hook's `ask`; `deny` rules removed (the hook is the single source of truth) | corpus |
| Gate (D2) | Blocks on failed or missing required checks, missing lenses or adversary, bogus `head`/`round`, bool probabilities; waivers keyed by fingerprint, bound to `head`, lapse when files change, signer must be in the team; `mode: enforce / advisory / off`; `stale_review` / `dirty_tree`: block or warn | 17 gate tests |
| Team (D3) | `team.lead` + `team.collaborators`; installer detects the lead from git config; `--lead` / `--collaborator`; banner shows maintainers; all hard-coded owner names removed | install tests |
| AGENTS.md (D4) | Installer writes or updates a managed `<!-- harness:begin/end -->` block; project text outside it is preserved; `--no-agents-md` opts out | install tests |
| Installer | Re-install no longer resets `default_branch`; branch detected from origin/HEAD; pyc and `.DS_Store` excluded; settings merge tolerates foreign hooks; templating without `sed` | install tests |
| `wf-new.sh` | Falls back to the local base when origin lacks the harness; rolls back the branch and worktree on failure | test |
| `wf-loop.sh` | Stops if the reviewer changed code or wrote no new round; reads effective config; no longer exits silently before round 1 (empty-glob `ls` under pipefail) | test (fake `claude`) |
| `bootstrap.sh` (D6) | `--sha` verification, SHA recorded in `SOURCE_REF`, guard check understands `ask`; fixed the empty-args crash on macOS bash 3.2 | end-to-end run |
| Self-tests | `tests/test_harness.py` (29 tests, stdlib only) | all pass |

## Stage 1b: local mode (D7) ✅ done (2026-10-13)
Ported from the second v0.1 draft drop (which was built on the original v0.1) onto the stage-1 code, plus fixes.

| Item | What changed | Verified by |
|---|---|---|
| `install.sh --mode local` | Harness paths hidden via a managed `.git/info/exclude` block; settings go to `settings.local.json`; commit-msg hook in `<git-dir>/hooks`; `.work` → `<git-dir>/harness-work` (shared by worktrees, never pushed); CLAUDE.md, AGENTS.md and `.gitignore` untouched; release-please off unless `--with-release` | test + bootstrap end-to-end |
| Fixes vs the drop | Mode is fixed at first install (re-install keeps it; switching requires uninstall) — the drop rewrote `mode`/`default_branch` on every run; local paths come from one list (`local-paths.txt`) instead of three hand-kept copies, so `guard_git.py` and future files are not missed; `readlink -f` replaced for portability | tests |
| `wf-new.sh` | Local mode copies the harness into new worktrees and links the shared `.work`; skips the "harness committed" checks | test |
| Session hook | Local mode injects `RULES.md` at session start | test |
| `uninstall.sh` (new) | Local: removes all harness paths, the exclude block, the harness hooks in `settings.local.json` (keeps the user's own settings), our commit-msg hook; keeps artifacts unless `--purge-work`; tracked: prints the steps for a reviewed removal commit | 2 tests |
| `bootstrap.sh` | Verify step checks each mode: hook location, and in local mode that `git status` shows nothing from the harness | end-to-end run |
| Self-tests | 7 new local-mode tests (36 total) | all pass |

## Stage 2: context-aware onboarding (next)
Read the project before changing it. Detection is deterministic; interpretation is done by Claude and approved by a maintainer.

| ID | Change | Acceptance |
|---|---|---|
| E1 | `scripts/detect.py` → `.claude/harness/DETECTED.json`: agent and governance files (`CLAUDE.md`, `AGENTS.md`, `.claude/**`, `.cursor/rules`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`, `CODEOWNERS`), hook managers (husky, lefthook, pre-commit, commitlint), release tools (semantic-release, changesets, goreleaser, release-please), build commands (`package.json` scripts, Makefile, justfile, `pyproject.toml`, tox/nox, CI workflows), critical-looking directories, monorepo markers | Fixture repos for each stack produce the expected JSON |
| E2 | Install acts on the detection: skip release-please if another release tool exists; never change `core.hooksPath` under a hook manager (print the snippet instead); stop on `wf-*` name collisions | Install tests per fixture |
| E3 | `/wf-onboard` skill (fresh session): reads `DETECTED.json` + governance files as data; writes `.claude/harness/PROJECT.md` (≤ 60 lines: stack, how to run, conventions, conflict table project-rule vs harness-rule); proposes a `harness.json` diff and stops for approval | Manual run on 3 real repos |
| E4 | `RULES.md` imports `PROJECT.md`; `/wf-investigate` and `wf-researcher` read it first | — |

## Stage 3: speed
| ID | Change | Acceptance |
|---|---|---|
| F1 | **Done for `lite` / `standard`** (`wf-track.py`; `critical` not built). Tracks `lite` / `standard` / `critical` (`wf-new.sh --track`, `harness.json` `tracks.*`). Lite (D5) = ≤ ~150 changed lines, no `critical_paths`, no new deps or migrations → short spec, one review with correctness + security, no adversary | Gate test: lite track on a diff over the limit or touching a critical path is upgraded automatically |
| F2 | Per-role models in agent frontmatter, configurable in `harness.json` `models` (fast model for researcher and lens reviewers on lite; strongest model for adversary, consolidation and spec) | — |
| F3 | **Done** (`wf-metrics.py`; also turns, refused tool calls, per-phase summary). `wf-loop.sh` writes `.work/<slug>/metrics.jsonl` (duration and cost per headless call) | — |
| F4 | `install.sh --dry-run` | Test: no files written |

## Stage 4: measured quality, then release
| ID | Change |
|---|---|
| G1 | **Built, not yet run** (`evals/run_evals.py`, 5 seeded cases + 1 clean control; scoring unit-tested with a stand-in `claude`). `evals/`: fixture repos with seeded defects (injection, race, missing AC test, unbounded query, swallowed error); headless `/wf-review` catch rate per lens |
| G2 | **Built, not yet run** (`run_evals.py --runs 3`: catch rate, verdict agreement, exposure range). Gate consistency test: the same diff reviewed 3×; report how much the findings and exposures vary |
| G3 | **Done** (`.github/workflows/test.yml`). CI for the harness repo (macOS + Ubuntu, Python 3.8 + 3.12) running `tests/` |
| G4 | One real pilot project run end to end (research plan §3) |
| G5 | **Release:** create the GitHub repo, push, tag `v0.1.0`, publish the release with its SHA, and update the README install line |

## Stage 5: team presets ✅ done (2026-10-30)
| ID | Change | Acceptance |
|---|---|---|
| P1 | `branching.*` (base, type → prefix, ticket), `docs.*` (ADR dir, changelog, PR template), `validation.*` config | test |
| P2 | `install.sh --preset <name>`; `presets/example.json` (dev base, `feature/<ticket>-…`, make commands, code-owner critical paths, release-please off); private presets in gitignored `presets/local/`; `guided` profile | test |
| P3 | `/wf-pr` (PR draft from the project template, commands printed, never run) and `/wf-validate` (AC test cases, evidence, go / hold) | manual (not yet run on a real repo) |
| P4 | `/wf-spec` drafts an ADR in `docs.adr_dir` for architecture decisions | manual |

## Open questions
- Local mode: should `wf-new.sh` offer a `--sync` to refresh the harness copy in existing worktrees after an update?
- Should `strict` also add Claude Code `permissions.deny` rules as a second layer under the hook? (Currently the hook is the only layer, so `ask` works.)
- Confirm that the current Claude Code CLI still accepts `Task` in `--allowedTools` (`wf-loop.sh` lists both `Agent` and `Task`).
