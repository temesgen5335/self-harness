---
name: wf-gate
description: Run the deterministic risk gate for a work item and explain the verdict and what is needed to pass. Use when asked whether work is ready, done, or shippable.
argument-hint: "[slug]"
allowed-tools: Bash(python3 .claude/harness/scripts/*), Bash(git branch:*), Bash(git rev-parse:*)
---
# Gate

Run `python3 .claude/harness/scripts/gate.py <slug>` (slug from `$ARGUMENTS` or the current branch's work item).

Report: verdict, gate mode and profile, aggregate exposure vs limits, warnings, and for BLOCK the shortest list
of actions that would pass (fix X, add evidence for Y, re-review because stale, missing check or lens).
The script is the authority; never override or reinterpret its verdict. `gate.mode` = advisory means the verdict
is reported but does not stop the work; say so plainly.

## Waivers
Only on an explicit instruction in this chat from a maintainer (lead or collaborator in `harness.json` `team`).
Append to `.work/<slug>/waivers.json` (create as `{"waivers": []}`):
```json
{"fingerprint": "<from the gate table>", "id": "F-003", "reason": "...", "by": "<maintainer name or email>",
 "date": "YYYY-MM-DD", "head": "<git rev-parse HEAD>"}
```
Security findings also need `"acknowledge_security": true`. A waiver stops applying when the finding's files change
after `head`. Re-run the gate and show the new verdict.
