---
name: wf-validate
description: Validate a work item against its acceptance criteria with recorded evidence before it is promoted — test cases, results, defects and a go / hold / go-with-accepted-risk recommendation. Re-runs the frozen task set for LLM/RAG changes.
argument-hint: "[slug]"
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(python3 .claude/harness/scripts/*), Bash(ls:*)
---
# Validation

Branch: !`git branch --show-current`
Config: !`python3 .claude/harness/scripts/hconfig.py validation`

Validation proves the change does what the spec says, in a running system, with evidence. "Looks fine" is not a result.
You record only what you observed in this session or what a person reports to you; mark the source of each result.

## Plan
1. Slug from `$ARGUMENTS` or the branch's state.json. Read spec §3 (behaviour, including empty, error and
   degraded states) and §12 (acceptance criteria). Read the latest review round for known risks.
2. Write test cases to `.work/<slug>/60-validation.md`: one or more per AC, plus the edge cases §3 names.
   Each: id (TC-n), AC, preconditions, steps, expected result, and who runs it (`claude` if you can run it
   here with a command, otherwise `manual`). Test data is synthetic — never production or client personal data.

## Run
3. Run the `claude` cases; record the command, the actual result and the evidence (output excerpt, file path).
4. LLM/RAG behaviour changed and `validation.frozen_task_set` exists: run the project's eval command against
   it (ask which, if none is documented), compare with the last recorded result, and record both.
5. List the `manual` cases for the maintainer as a checklist and STOP until they report results. Record what
   they report with "reported by <name>".

## Conclude
6. For each failure write a defect: TC id, steps to reproduce, expected vs actual, severity.
7. Recommendation: `go`, `hold` (with the blocking defects) or `go with accepted risk` (which risk, who
   accepted it). Only a maintainer accepts risk.
8. go or go with accepted risk: `python3 .claude/harness/scripts/wf-state.py <slug> set phase=validated validation=<go|go-with-risk>`.
   hold: `wf-state.py <slug> set phase=validation-hold validation=hold`; the defects go back to `/wf-fix`.

Finish with the result table (TC, AC, result, evidence) and the recommendation. `/wf-pr` adds it to the PR's Testing section.
