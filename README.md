# Harness: plan · build · review · publish for Claude Code

> **Status: v0.1 draft.** Published on GitHub and tagged `v0.1.0` once the [upgrade plan](docs/upgrade-plan.md) is done.

This harness gives every change in a project the same path:

1. Investigation, in a fresh session.
2. A spec that a maintainer approves.
3. Test-first build, one task at a time.
4. Independent review through several lenses, in a clean session.
5. A deterministic risk gate.
6. A versioned release through release-please.

Claude drafts by default. Git writes happen only when a maintainer asks, and the guard makes them confirm each one.
How strict the harness is (git policy and gate) is project config, from `strict` to `light`.

```
 wf-new.sh ──► /wf-investigate ──► /wf-spec ──► (approve) ──► /wf-build T1..Tn ──► /wf-commit ──► commit (on request)
  worktree      fresh session      fresh session              build session        drafts
                                                                     ▲                     │
                                                       /wf-fix ◄─────┤                     ▼
                                                     (response.md)   │ BLOCK      /wf-review (fresh session per round)
                                                                     └──────────── gate.py ──► PASS ──► maintainer opens PR, merges
                                                                                                         │
                                                                    release-please PR ◄──────────────────┘
                                                                    /wf-release go/no-go ──► maintainer merges release PR
```

## What is in it

| Path (in a project) | Role |
|---|---|
| `.claude/harness/RULES.md` | Always-loaded rules (imported from `CLAUDE.md`). Short on purpose. |
| `.claude/harness/harness.json` | Per-project config: profile, team, check commands, git policy, gate settings, lenses. Updates never overwrite it. |
| `.claude/harness/local-paths.txt` | The paths the harness owns in local mode (used by install, `wf-new.sh` and `uninstall.sh`). |
| `.claude/harness/scripts/hconfig.py` | Prints the **effective** config (profile defaults + your overrides): `python3 .claude/harness/scripts/hconfig.py [key]`. |
| `.claude/harness/RISK.md` | Risk model: bands, evidence types, gate rules. |
| `.claude/harness/RUBRIC.md` | Review checks per lens: correctness, security, scale, operability, design, experience, adversary. |
| `.claude/harness/COMMITS.md` | Commit rules and their release-please effect. |
| `.claude/harness/templates/` | Brief, investigation, spec and build-log templates. |
| `.claude/harness/scripts/` | `wf-new.sh`, `wf-loop.sh`, `gate.py`, `hconfig.py`, `wf-state.py`, `wf-status.sh`. |
| `.claude/skills/wf-*` | The slash commands (`/wf-investigate` … `/wf-release`). |
| `.claude/agents/` | The `wf-researcher`, `wf-lens-reviewer` and `wf-adversary` subagents. |
| `.claude/hooks/` | `guard-git.sh` + `guard_git.py` (git policy for each operation) and `session-context.sh` (banner for each new session). |
| `.claude/settings.json` | Attribution off and hook wiring, merged into your existing settings. |
| `AGENTS.md` (managed block) | The same core rules for other coding agents, between `<!-- harness:begin/end -->` markers. |
| `.githooks/commit-msg` | Enforces Conventional Commits and rejects AI attribution. |
| `release-please-config.json`, manifest, `.github/workflows/` | Versioned releases, plus a PR-title lint for squash merges. |
| `.work/<slug>/` | Per work item: brief, investigation, spec, build log, reviews, gate, waivers. Committed with the branch. |

Commands are written as skills (`.claude/skills/<name>/SKILL.md`). Each one is still a `/name` command.
Phase commands use `disable-model-invocation: true`, so they run only when you type them.
The `wf-` prefix avoids collisions with bundled commands such as `/review`.

## Team

`harness.json` → `team` has one `lead` and any number of `collaborators`. Together they are the **maintainers**:
only they approve specs, accept waivers and ask for git writes.

- The installer sets the lead from the `git config user.name/email` of whoever runs it.
- Override the lead with `--lead "Name <email>"`; add collaborators with `--collaborator "Name <email>"` (repeatable), or edit the JSON.
- The session banner names the maintainers. The gate ignores waivers signed by anyone else.

## Profiles: how strict it is

Set `"profile"` in `harness.json`. A profile only sets defaults; any key you set yourself overrides it.

| | `strict` | `standard` (default) | `light` |
|---|---|---|---|
| Stage / commit / push / open PR | block (draft only) | **ask**: maintainer confirms each command | ask |
| Merge, tag, release, history rewrite, destructive, `--no-verify` | block | block | block |
| Read a secret file (`.env`, keys), pipe a download into a shell | block | **ask** | ask |
| Recursive delete (`rm -r`, `find -delete`) | ask | ask | ask |
| Gate mode | enforce | enforce | **advisory** (reports, doesn't stop) |
| Thresholds (default / critical) | 3% / 0.5% | 5% / 1% | 5% / 1% |
| Stale review, dirty tree | block | block | warn |
| Lenses | all 6 + adversary | all 6 + adversary | correctness + security |

Fine-tuning:
- `git.guard`: `enforce` / `warn` / `off`.
- `git.ops.<op>`: `allow` / `ask` / `block`, for each of `stage`, `commit`, `push`, `pr`, `merge`, `tag`, `release`,
  `history`, `destructive` and `skip_hooks`, plus three non-git ops: `destructive_fs` (recursive deletes),
  `secrets` (reading `.env`, private keys and credential files, through Bash or the Read tool) and
  `remote_exec` (piping a downloaded script into a shell or interpreter).
- `gate.mode`: `enforce` / `advisory` / `off`.
- `gate.checks_required`, `gate.stale_review`, `gate.dirty_tree`, `gate.security_always_blocks`, thresholds and
  `critical_paths`.

Run `hconfig.py` to see what is in effect. Turning the guard or the gate `off` removes that protection, and the session banner shows it.

## Tracked vs local mode

Pick one at the first install with `--mode`. To switch later, run `uninstall.sh` first.

| | `--mode tracked` (default) | `--mode local` (no trace in git) |
|---|---|---|
| Harness files | committed with the project | hidden via `.git/info/exclude`, so no tracked file (not even `.gitignore`) changes |
| Rules | `@import` in `CLAUDE.md` + managed block in `AGENTS.md` | injected by the SessionStart hook; `CLAUDE.md` and `AGENTS.md` untouched |
| Settings | merged into `.claude/settings.json` | merged into `.claude/settings.local.json` |
| commit-msg hook | `.githooks/` + `core.hooksPath` | `<git-dir>/hooks/commit-msg`, shared by all worktrees |
| `.work/` artifacts | committed on each feature branch | symlink to `<git-dir>/harness-work/`, shared by all worktrees, never pushed |
| New worktrees | get the harness from git | `wf-new.sh` copies the harness in (paths from `local-paths.txt`) |
| release-please | installed | skipped unless `--with-release` (those files must be tracked: GitHub only runs committed workflows) |
| Teammates | get the same workflow | see nothing |
| Remove | a reviewed commit (`uninstall.sh` prints the steps) | `uninstall.sh <repo> [--purge-work]` restores a clean `git status` |

Use **local** for team or client repos where the workflow is yours alone. Use **tracked** when the whole team should work this way.

Trade-offs of local mode:
- Review history lives only on your machine.
- Worktrees created outside `wf-new.sh` have no harness.
- After updating the harness in the main checkout, re-run `wf-new.sh` (or `uninstall.sh` + re-create) for existing worktrees.
- `bootstrap.sh` checks that `git status` shows nothing from the harness.

## Install into a project

```bash
git clone <this repo> ~/dev/harness
~/dev/harness/install.sh /path/to/project                                    # detects branch, lead, release type
~/dev/harness/install.sh /path/to/project --profile strict --collaborator "Ana <ana@example.com>"
~/dev/harness/install.sh /path/to/client-repo --mode local                    # leaves no trace in git
~/dev/harness/uninstall.sh /path/to/client-repo                               # remove it again
```

Options: `--mode`, `--profile`, `--lead`, `--collaborator`, `--default-branch`, `--release-type`, `--no-release`,
`--with-release`, `--no-agents-md` and `--force`. On a re-install, `harness.json` changes only for the flags you pass.

Then:
1. Fill in the `commands` in `harness.json` (`lint`, `typecheck`, `test`, `stress`, `build`) and `gate.critical_paths`. Check `team` and `profile`.
2. Review the harness files, commit them, and push. Worktrees only see committed files.
3. On GitHub, go to Settings → Actions → General and allow Actions to create pull requests. Prefer squash merges.
4. The release workflows ship pinned to reviewed commit SHAs; review any bump before you merge it.

Requirements: git, python3 ≥ 3.8 (stdlib only) and Claude Code. `gh` is needed only for `/wf-release`.

## Onboard another project (one command, pinned by SHA)

Pin installs to an **exact commit SHA**, not only a tag. Tags can be moved or re-pointed; a SHA can't.

```bash
cd /path/to/project
SHA=<40-char commit sha of the release you reviewed>
curl -fsSL "https://raw.githubusercontent.com/temesgen5335/self-harness/$SHA/bootstrap.sh" | bash -s -- --ref v0.1.0 --sha "$SHA"
# no trace in git (client or team repos): add --mode local
# or, with a local clone:  ~/dev/harness/bootstrap.sh --ref v0.1.0 --sha "$SHA"
```

- Fetching `bootstrap.sh` itself from `/$SHA/` means the script you run is the one you reviewed.
- `--sha` makes bootstrap refuse to install if `--ref` resolves to any other commit.
- Without `--sha`, bootstrap installs and prints the SHA to pin next time.
- `.claude/harness/SOURCE_REF` records `<ref> <sha>`, so every project shows exactly which harness it runs.
- To find a release's SHA: `git ls-remote https://github.com/temesgen5335/self-harness refs/tags/v0.1.0`.
  Check it against the GitHub release page before you pin it.

`bootstrap.sh` does the rest:
- checks prerequisites;
- clones or updates the harness into `~/.local/share/claude-harness` and checks out the ref;
- runs `install.sh`;
- verifies that the guard stops a commit and that the commit-msg hook is active.

Re-running it updates an existing install (`--force` is added automatically; `harness.json` is kept). Other flags pass through to `install.sh`.

## Daily use

```bash
.claude/harness/scripts/wf-new.sh rate-limit "Add per-tenant rate limiting to the jobs API"
cd ../<repo>.worktrees/rate-limit && claude
```

| Step | Session | Command | Output |
|---|---|---|---|
| Investigate | fresh | `/wf-investigate rate-limit` | `10-investigation.md`: sourced facts, current versions, unknowns |
| Spec | fresh | `/wf-spec rate-limit` | `20-spec.md`: design, alternatives, ACs, tasks, decisions. A maintainer approves. |
| Build | build | `/wf-build rate-limit` (repeat) | One task, test-first, all checks run, a build-log entry, commit drafts |
| Commit | maintainer | `/wf-commit` (drafts) · `/wf-commit apply` (on request) | Concise Conventional Commits, no attribution |
| Review | fresh, per round | `/wf-review rate-limit` | `R<n>.md`, `R<n>.findings.json`, `50-gate.md` |
| Fix | build | `/wf-fix rate-limit` | Regression tests + fixes, `R<n>.response.md`, commit drafts |
| Gate | any | `/wf-gate rate-limit` | PASS / BLOCK / ESCALATE (advisory or off when configured) |
| Publish | default branch | `/wf-release` | GO / NO-GO on the release-please PR |

Other commands: `/wf-status` (all work items), `/wf-handoff` (compress state before `/clear`), `/wf-commit` (any time).

### Sessions talking to each other

Sessions never share chat history; they share files. The reviewer reads the spec and the commits, never the build log,
so the builder's reasoning doesn't bias it. The builder answers each finding in `R<n>.response.md`
(fixed / disputed with evidence / deferred for a waiver), and the next fresh reviewer rules on those answers.

- **By hand:** run `/wf-review` in a new session, then `/wf-fix` in your build session.
- **Automated:** `wf-loop.sh rate-limit` loops fresh headless review sessions, the gate and headless fix sessions,
  and pauses for you at every commit point (headless sessions can't approve "ask" operations).
  The loop stops if a reviewer changes code, or if a review session writes no new round.
  `--manual` runs only review + gate. `--fix-session <id>` resumes your build session instead of starting a fresh one.

## The risk gate

Each finding carries:
- `p_trigger`: the chance it's triggered in real use within one release;
- `p_visible`: the chance a user notices;
- its evidence (`executed-repro`, `failing-test`, `code-path` or `assumption`) and a class.

`gate.py` is deterministic. In `enforce` mode it blocks when unsure:

- the review must be complete: every configured lens and the adversary ran, `round` and `head` are valid;
- any check reported `fail` blocks, and every required check must be reported `pass`;
- any open `security-exploitable` finding blocks;
- each finding's exposure must be under 5% (default), or 1% for security, data loss or files in `critical_paths`.
  The total exposure `1 − Π(1 − p)` must be under the same limits;
- assumption-only evidence counts double;
- a review of an older HEAD is stale if code changed since then (commits that only touch artifacts are fine);
- uncommitted code means BLOCK;
- after `max_review_rounds` without PASS → ESCALATE. That usually means a design problem: go back to the spec;
- waivers belong to maintainers. They are stored in `waivers.json`, keyed by the finding's **fingerprint**, which stays
  the same across rounds. A waiver lapses when the finding's files change. Security waivers need an explicit acknowledgement.

The probabilities are structured judgement, not measurement. What makes the gate trustworthy is the evidence requirement,
the reviewer running the checks itself, the adversary's executed repros, and the conservative penalties, not the decimals.

## Commits and releases

- **When:** never on Claude's own initiative. Only when a maintainer asks, and the guard asks them to confirm each git command.
- **Format** (`COMMITS.md`): a type tag (`feat`, `fix`, `docs`, `chore`, …), a clear descriptive title, a short why-body,
  and no Co-Authored-By or AI attribution. The `commit-msg` hook enforces the format and the no-attribution rule.
- **Versions:** `feat` → minor, `fix`/`perf`/`revert` → patch, `!` + `BREAKING CHANGE:` → major (minor while < 1.0).
  Other types don't produce a release.

## Developing the harness

```bash
python3 -I tests/test_harness.py
```

The tests cover the installer, the git-guard corpus (`tests/guard_corpus.tsv`, about 90 commands), gate cases,
the commit-msg hook, `wf-new.sh`, and local mode (no trace, shared worktree artifacts, uninstall). Add a test for every bug fixed.

## Limits worth knowing

- The guard is a guardrail, not a sandbox. It parses shell commands (including `bash -c`, `$(…)`, `eval`, git global
  options and git calls written inside `python -c` / `node -e` code), but a determined process - a script file, an
  alias, writing to `.git` directly - can still get around it. For hard isolation, enable Claude Code's sandbox
  (filesystem and network restrictions enforced by the OS), especially with the `strict` profile.
- The guard does not scan file contents for secrets. Pair it with a secret scanner in your git hooks or CI.
- Headless loop runs give the fix session Bash; the guard still applies. To be stricter, narrow `FIX_TOOLS` in `wf-loop.sh`.
- Review cost grows with the number of lenses. For small changes use the `light` profile or trim `review.lenses`.
- Monorepos: add packages to `release-please-config.json` `packages` and set `include-component-in-tag: true`.
