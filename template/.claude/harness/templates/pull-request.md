<!-- Title: a Conventional Commit of 72 characters or fewer, e.g. "feat(export): add CSV export for invoices".
     Fill every section; write "n/a" and the reason instead of deleting one.
     Never paste secrets, tokens, .env contents, raw logs, or real personal or client data. -->

## What
<!-- The change in one to three sentences, from the user's or caller's point of view. -->

## Why
<!-- The problem it solves and its ticket ("Closes ABC-123"); link the spec or issue. -->

## How
<!-- Key decisions and trade-offs, alternatives rejected, and any ADR. Not a restatement of the diff. -->

## Testing
<!-- Each command run and its one-line result (never raw logs). Which test proves which acceptance criterion.
     Manual validation of user-visible behaviour: steps, environment, result. -->

## Screenshots
<!-- Before and after for UI changes, with synthetic data only. "n/a" otherwise. -->

## Risk and rollback
<!-- What could break and who would notice. How to roll back: revert, feature flag, down-migration.
     Data or migration impact. Anything deferred or waived, and why. -->

## Checklist
<!-- Tick only what is true; explain every unticked item below the list. -->
- [ ] One concern, small enough to review in one sitting (about 400 changed lines or fewer)
- [ ] Tests cover the change and its edge cases, and fail without it
- [ ] Required checks pass: lint, typecheck, tests, build
- [ ] No secrets, credentials or `.env` contents in code, config, tests, logs or this description
- [ ] No production or client personal data; fixtures and screenshots use synthetic data
- [ ] No debug leftovers: print statements, commented-out code, stray files
- [ ] New dependencies are justified, pinned and scanned
- [ ] Higher-risk areas (auth, payments, migrations, infrastructure, personal data, prompts) flagged for code-owner review
- [ ] Database migrations are reversible, or the rollback plan says how to recover
- [ ] Docs updated: CHANGELOG `[Unreleased]` for user-visible changes, ADR for design decisions, setup and run docs
- [ ] Automated review run and every comment addressed
