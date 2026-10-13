#!/usr/bin/env bash
# PreToolUse(Bash) entry point. Fails closed: if python3 is missing the call is blocked (exit 2),
# because any other non-zero exit would let the command run.
here="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "harness guard: python3 not found; Bash blocked. Install python3 or set git.guard=off." >&2; exit 2; }
python3 "$here/guard_git.py"
code=$?
[[ $code -eq 0 || $code -eq 2 ]] && exit $code
echo "harness guard: internal error ($code); blocked." >&2
exit 2
