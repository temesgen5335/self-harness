# Risk model (used by reviewers and by gate.py)

Every finding gets two estimates, each in [0, 1]:

- `p_trigger` — probability the defect is triggered in real use **within one release cycle**
  under realistic traffic, data, and configuration (not "can it ever happen").
- `p_visible` — probability that, once triggered, a **user** notices: wrong result, error, slowness
  beyond budget, data loss, security exposure, or an incident that ops cannot diagnose in time.

`exposure = p_trigger × p_visible` (× `assumption_penalty` when evidence is only an assumption).

## Anchor bands (pick the band, then a value inside it — no fake precision)
| Band | Value range | Meaning |
|---|---|---|
| Certain | 0.5 – 1.0 | Happens on a main path or with common input |
| Likely | 0.2 – 0.5 | Happens for a known, non-rare user segment or load level |
| Plausible | 0.05 – 0.2 | Needs an uncommon but realistic condition (retry, timeout, empty state, concurrency) |
| Unlikely | 0.01 – 0.05 | Needs a rare combination of conditions |
| Remote | < 0.01 | Needs conditions you can name but do not expect |

## Evidence (required on every finding)
- `executed-repro` — a repro or failing test was run and failed. Strongest.
- `failing-test` — a test exists that should fail; not yet executed.
- `code-path` — a concrete path through the code was traced, with file:line refs.
- `assumption` — reasoning without a traced path. Penalised by `assumption_penalty`.

## Classes
`security-exploitable`, `data-loss`, `functional`, `degradation`, `operability`, `design`, `cosmetic`.

## Gate rules (enforced by `scripts/gate.py`; every setting below is in `harness.json` → `gate`)
Unless noted, a rule that fails makes the verdict BLOCK. In `gate.mode: "advisory"` the verdict is still reported
but the exit code is 0; in `"off"` the gate does not run. Profiles preset these values (`strict` / `standard` / `light`).

1. Review is complete: `round` matches the file, `head` is a real commit, every configured lens is in
   `lenses_run` and `adversary_run` is true when enabled (`require_all_lenses`).
2. Checks: any check reported `fail` blocks; each of `checks_required` (default `"auto"` = every non-empty command
   except install) must be reported `pass`.
3. Any open `security-exploitable` finding blocks regardless of probability (`security_always_blocks`).
4. Per finding: `exposure` below the threshold. The **critical** threshold applies when the class is
   `security-exploitable` or `data-loss`, or any file matches `critical_paths`; otherwise **default**.
5. Aggregate: `1 − Π(1 − exposure)` over open findings below the default threshold, and over critical findings below
   the critical threshold.
6. `blocking: true` blocks (non-probabilistic must-fix issues, e.g. no rollback for a migration).
7. The review must cover current code (`stale_review`) and the tree must be clean outside the work dir
   (`dirty_tree`): `block` or `warn`.
8. Waivers are a maintainer decision, in `waivers.json` keyed by the finding's **fingerprint** (stable across rounds),
   with `reason`, `by` (must be in `team` when `waivers.approvers` is `"team"`), `date` and `head`. A waiver lapses
   when the finding's files change after `head`. Security waivers also need `"acknowledge_security": true`.

## Honesty about these numbers
These are judgements, not measurements. They are useful because they force explicit reasoning, and
because evidence requirements and conservative penalties push the uncertain cases toward "fix it".
When torn between two bands, choose the higher one.
