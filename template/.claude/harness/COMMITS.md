# Commit rules

**When:** never on your own. Only when a maintainer explicitly asks in the current conversation
(the guard then asks them to confirm each git command). Otherwise draft with `/wf-commit` and stop.

**Format:** `type(scope)!: title`

- **type** — one tag from the table. Pick by user effect, not by files touched.
- **title** — clear and descriptive, imperative, lower-case start, ≤ 72 chars, no trailing period.
  Good: `fix(api): return 404 for unknown job id`. Bad: `fix: updates`, `chore: misc changes`.
- **body** — optional, short and to the point: 1–3 lines on *why* (and any trade-off), wrapped at 72.
  The diff already shows what changed. No changelogs, no file lists, no narration.
- **footers** — only when needed: `BREAKING CHANGE: <what and how to migrate>`, `Refs: <slug>/T3`.
- **never** — `Co-Authored-By`, "Generated with", 🤖, or any other AI attribution. The `commit-msg` hook rejects them.

| type | release-please effect | use for |
|---|---|---|
| feat | minor | user-visible capability |
| fix | patch | user-visible bug fix |
| perf | patch | measurable performance improvement |
| revert | patch | reverting a released change |
| refactor | none | code change with no behaviour change |
| test | none | tests only |
| docs | none | documentation only |
| build, ci | none | build system, dependencies, pipelines |
| chore | none | maintenance that fits nothing above |
| style | none | formatting only |

- Breaking change: `!` after type/scope AND a `BREAKING CHANGE:` footer.
- One logical change per commit. Tests ship in the same commit as the code they cover.
  Never mix a refactor with a behaviour change.
- Squash merges: the PR title becomes the commit, so PR titles follow the same format.

Example:
```
fix(jobs): retry webhook delivery with backoff

Receivers rate-limit bursts; immediate retries were dropped.
Refs: webhook-retry/T2
```
