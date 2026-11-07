#!/usr/bin/env bash
# UserPromptSubmit: unread sync-board entries from other sessions (stdout becomes context).
# Silent when this session is on no board or nothing is new; never blocks the prompt.
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
s="$root/.claude/harness/scripts/wf-sync.py"
[[ -f "$s" ]] && command -v python3 >/dev/null 2>&1 || exit 0
python3 "$s" inbox 2>/dev/null
exit 0
