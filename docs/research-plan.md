# Research plan: harness adoption in other projects

Date: 2026-10-13 · Owner: Temesgen · Status: Draft

## 1. Why this research

The harness was built around one person and one workflow. Before it is used in other projects,
we need evidence on four claims the design makes:

| Claim | What would prove it wrong |
|---|---|
| **Reusable** | A project needs edits outside `harness.json` to adopt it, or a second adopter cannot start without help |
| **Concrete and safe** | The agent commits, pushes or edits code it shouldn't, or the gate passes work a human would reject |
| **Fast** | Small changes cost more time in the harness than without it, so people bypass it |
| **Quality** | Defects caught after PASS (in PR review, CI, production) are about as common as without the harness |

## 2. Research questions

1. **Setup:** How long does it take from `bootstrap.sh` to the first `/wf-investigate`? Where do people get stuck?
   This includes filling in `harness.json` commands and `critical_paths`, the GitHub settings, and pinning action SHAs.
2. **Fit:** Which parts don't match how the project already works? For example: a different default branch,
   monorepos, existing hooks or release tooling, no Python, or a team where someone other than "Temesgen" commits.
3. **Cost per change:** How many minutes and tokens does each phase take, for a 1-line fix, a 1-day feature and a multi-day feature?
   For which change sizes do people skip phases?
4. **Gate trust:** Do people believe PASS and BLOCK? How often do they waive findings or argue with them,
   and are the `p_trigger`/`p_visible` scores stable when the same diff is reviewed twice?
5. **Escapes:** What does the harness miss? Defects found after PASS, by lens.
6. **Safety:** Did the agent ever change git state, edit source during review, or work around a guardrail? How?

## 3. Methods

| Method | Answers | Who / sample | Duration |
|---|---|---|---|
| **Instrumented pilots**: install in 3 real projects with different stacks (Python, Node, one monorepo or other stack) | Q1–Q5 | Temesgen plus 2–3 other developers | 3–4 weeks |
| **Usability test of onboarding**: think-aloud from `bootstrap.sh` to the first spec | Q1, Q2 | 5 developers who have never seen the harness | 1 week, 60 min each |
| **Telemetry from artifacts**: parse `.work/*/` (rounds, gate verdicts, waivers, timestamps) | Q3, Q4 | Every pilot work item | Continuous |
| **Gate consistency test**: review the same frozen diff 3× in fresh sessions and compare findings and exposure | Q4 | 5 diffs, including 2 with seeded bugs | 2 days |
| **Seeded-defect evals**: plant known bugs (security, race, missing AC test) and check whether the gate blocks them | Q5, Q6 | 10–15 seeded defects | 3 days |
| **Red-team the guardrails**: prompt the agent to commit or push and log the bypasses | Q6 | Scripted, plus 1 adversarial session | 1 day |
| **Short interviews after pilots** | Q2–Q4 "why" | All pilot developers | 30 min each |

The seeded-defect and red-team checks should also become a permanent regression suite for the harness,
so they run on every harness release, not just once.

## 4. Metrics (collected per work item)

- Setup: time to first spec; number of manual steps; number of questions asked.
- Speed: wall-clock and tokens per phase; review rounds to PASS; share of items that reached ESCALATE.
- Quality: seeded-defect catch rate per lens; escapes after PASS within 30 days; how much findings vary between repeat reviews.
- Trust: number of waivers per item; number of disputed findings and the share upheld; times the harness was bypassed and why.
- Safety: guard blocks, bypasses found, and source edits made during review (target: 0).

## 5. Interview guide (30 min, after pilot)

1. **Warm-up (3 min):** your role and the project; how you shipped changes before the harness.
2. **Context (7 min):** walk me through the last work item you ran through the harness, step by step.
3. **Deep dive (12 min):**
   - Where did you wait, or redo work? Which phase felt like ceremony?
   - Tell me about a finding you disagreed with. What happened next?
   - Was there a change you didn't put through the harness? Why?
   - Did the gate verdict match your own judgement? Give an example where it didn't.
4. **Reaction (5 min):** show a "lite track" sketch (spec, build and one review session for small changes). Would you use it, and when?
5. **Wrap-up (3 min):** one thing to remove, one thing to add.

Probes: "What did you expect to happen?", "What did you do instead?", "How long did that take?"

## 6. Timeline

| Week | Activity |
|---|---|
| 1 | Fix the safety and gate defects from the code review; build the seeded-defect and red-team suite |
| 2 | Onboarding usability tests (5); refine bootstrap and docs |
| 2–5 | Pilots in 3 projects with artifact telemetry |
| 5 | Gate consistency test; interviews |
| 6 | Synthesis: affinity map → themes → impact/effort matrix → harness v0.2 backlog |

## 7. Deliverables

- Synthesis report: themes, insights and recommendations ranked by impact and effort.
- Harness eval suite (seeded defects plus guardrail red-team), kept in the repo and run on every harness release.
- An updated README "Adopting in a new project" section, based on what onboarding participants struggled with.
