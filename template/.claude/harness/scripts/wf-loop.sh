#!/usr/bin/env bash
# Review <-> fix loop between sessions. Run inside the work item's worktree.
#
# Usage: wf-loop.sh <slug> [--manual] [--fix-session <session-id>]
#   default        : each round = fresh headless review session, gate, fresh headless fix session,
#                    then PAUSE for a maintainer to commit the drafted commits.
#   --manual       : only run review + gate; you run /wf-fix yourself in your build session.
#   --fix-session  : resume that build session for fixes instead of a fresh one.
#
# Headless sessions cannot answer permission prompts, so git ops set to "ask" are refused there:
# the loop always waits for a human at every commit point.
set -euo pipefail
slug="${1:-}"; shift || true
manual=0; fix_sid=""
while [[ $# -gt 0 ]]; do case "$1" in
  --manual) manual=1; shift;; --fix-session) fix_sid="$2"; shift 2;;
  *) echo "unknown arg: $1" >&2; exit 3;; esac; done
[[ -n "$slug" ]] || { echo "usage: wf-loop.sh <slug> [--manual] [--fix-session id]" >&2; exit 3; }
command -v claude >/dev/null || { echo "claude CLI not found" >&2; exit 3; }

root="$(git rev-parse --show-toplevel)"; cd "$root"
H=.claude/harness/scripts
max="$(python3 "$H/hconfig.py" gate.max_review_rounds)"
wd="$(python3 "$H/hconfig.py" work_dir)"; work="$wd/$slug"
[[ -d "$work" ]] || { echo "no work item at $work" >&2; exit 3; }

code_status() { git status --porcelain -- . ":(exclude)$wd"; }
wait_for_clean_tree() {
  # Work artifacts may stay uncommitted between rounds; code may not.
  while [[ -n "$(code_status)" ]]; do
    echo
    echo "Uncommitted changes. Drafted commits: $work/commit-drafts.md"
    echo "Commit them yourself (or stash), then press Enter. Type q to stop."
    read -r ans; [[ "$ans" == "q" ]] && exit 1
  done
}
latest_review() { ls "$work"/40-reviews/R*.findings.json 2>/dev/null | wc -l | tr -d ' '; }  # count of rounds

# Reviewer: may write only under the work dir. Bash is broad, so the loop also verifies nothing else changed.
REVIEW_TOOLS="Read,Grep,Glob,Bash,Agent,Task,WebSearch,WebFetch,Write(${work}/**),Edit(${work}/**)"
FIX_TOOLS="Read,Grep,Glob,Bash,Agent,Task,Edit,Write"

for ((i = 1; i <= max; i++)); do
  wait_for_clean_tree
  before="$(latest_review)"
  echo "== Round: fresh review session =="
  claude -p "/wf-review $slug" --allowedTools "$REVIEW_TOOLS" --output-format text || echo "review session exited non-zero"
  if [[ -n "$(code_status)" ]]; then
    echo "STOP — the review session changed files outside $wd/ (reviewers must not edit code):"; code_status; exit 4
  fi
  if [[ "$(latest_review)" == "$before" ]]; then
    echo "STOP — the review session wrote no new R<n>.findings.json; not re-gating old findings."; exit 4
  fi
  set +e; python3 "$H/gate.py" "$slug"; code=$?; set -e
  case $code in
    0) echo "Gate done (PASS, or advisory/off mode) — a maintainer opens the PR, later /wf-release."; exit 0;;
    2) echo "ESCALATE — stop and revisit the spec with a maintainer."; exit 2;;
    1) ;;
    *) echo "gate error ($code)"; exit "$code";;
  esac
  if [[ $manual -eq 1 ]]; then
    echo "BLOCK — run /wf-fix $slug in your build session, commit, then re-run this loop."; exit 1
  fi
  echo "== Fix session =="
  if [[ -n "$fix_sid" ]]; then
    claude -p "/wf-fix $slug" --resume "$fix_sid" --allowedTools "$FIX_TOOLS" --permission-mode acceptEdits --output-format text
  else
    claude -p "/wf-fix $slug" --allowedTools "$FIX_TOOLS" --permission-mode acceptEdits --output-format text
  fi
done
echo "Max rounds ($max) reached without PASS."; exit 2
