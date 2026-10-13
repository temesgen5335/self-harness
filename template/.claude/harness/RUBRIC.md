# Review rubric

Each lens reviews only the diff `base..head` plus the code it touches or is called by.
Report a finding only with evidence (see RISK.md). No style nitpicks unless they hit a lens.

## correctness — does it do what the spec says, on every path?
- Every acceptance criterion has a test that would fail if the behaviour broke.
- Edge inputs: empty, null, max size, unicode, duplicate, out-of-order, timezone, locale.
- Error paths: every external call has a defined failure behaviour; no swallowed exceptions.
- Concurrency: shared state, races, idempotency of retries, transaction boundaries.
- Tests: assert behaviour not implementation; no sleeps for synchronisation; no test that cannot fail.

## security — can someone make it do something it should not?
- Trust boundaries: which inputs are attacker-controlled (HTTP, files, webhooks, LLM output, tool results).
- Injection: SQL, shell, path traversal, template, SSRF, deserialisation, prompt injection into agents/tools.
- AuthN/AuthZ on every new endpoint or action; tenant isolation; IDOR.
- Secrets: none in code, logs, errors, URLs, or LLM prompts; least-privilege credentials.
- Dependencies: new packages are maintained, pinned, and free of known advisories.
- Agentic code: tool permissions scoped; model output never executed or trusted without validation.

## scale — what happens at 10× and 100× load or data?
- Complexity: no N+1 queries, unbounded loops, or full-table scans on hot paths.
- Bounded resources: queues, caches, memory, file handles, connection pools, retries with backoff + jitter.
- Timeouts on every network call; backpressure; pagination on list endpoints.
- LLM features: token and cost per request bounded; rate limits handled; batching where it matters.
- Indexes and migrations safe on large tables (no long locks).

## operability — when it breaks at 3am, can someone tell why within minutes?
- Structured logs at decision points with correlation/request ids; no secrets or PII.
- Errors are actionable: what failed, with which input id, and what to do.
- Metrics or traces for the new path (rate, errors, latency); health checks updated.
- Feature flag or config switch to disable the new behaviour; rollback path tested.
- Migrations reversible or explicitly documented as one-way with a recovery plan.

## design — will this still be easy to change in six months?
- Matches the approved spec; deviations have a Spec Change Request.
- Configuration over hard-coded values; sensible defaults; validated config at startup.
- Clear module boundaries; dependencies point inward; no premature abstraction.
- Public interfaces versioned and backwards compatible, or the breaking change is flagged for semver.
- Uses current, non-deprecated APIs and library versions noted in the investigation.

## experience — what does the user actually see?
- Loading, empty, error, partial and offline/degraded states are designed, not accidental.
- Error messages are human, specific, and safe (no stack traces or internals).
- Accessibility basics (labels, keyboard, contrast) for UI; clear CLI/API error contracts for non-UI.
- Latency within the spec budget on realistic data; no regressions in existing flows.
- Docs/changelog-worthy changes are described for users.

## adversary — try to break it
- Write the smallest repro you can for each suspected defect, under `.work/<slug>/repros/`, and run it.
- Attack angles: boundary values, malformed and hostile input, concurrency, dependency down/slow,
  clock skew, partial failure mid-operation, misconfiguration, large payloads, prompt injection.
- A defect you reproduced is `executed-repro` evidence; report the exact command and output.
