#!/usr/bin/env bash
# Remove the harness from a project.
# Usage: uninstall.sh <target-repo> [--purge-work]
#   local mode  : removes every harness path, the .git/info/exclude block, the harness hooks from
#                 settings.local.json, and the commit-msg hook if it is ours. Work artifacts in the git dir
#                 (<git-common-dir>/harness-work, harness-sync) are kept unless --purge-work. Leaves git status unchanged.
#   tracked mode: prints what to delete; the removal is a normal change you review and commit yourself.
set -euo pipefail
target="${1:-}"; shift || true
purge=0
while [[ $# -gt 0 ]]; do case "$1" in --purge-work) purge=1; shift;; *) echo "unknown arg: $1" >&2; exit 3;; esac; done
[[ -n "$target" && ( -d "$target/.git" || -f "$target/.git" ) ]] || { echo "target must be a git repo root" >&2; exit 3; }
cd "$target"
[[ -f .claude/harness/harness.json ]] || { echo "no harness installed here" >&2; exit 3; }
mode="$(python3 -c 'import json;print(json.load(open(".claude/harness/harness.json")).get("mode","tracked"))')"
common="$(cd "$(git rev-parse --git-common-dir)" && pwd)"

if [[ $mode == tracked ]]; then
  cat << MSG
Tracked mode: the harness is part of the repo history, so remove it as a reviewed change:
  git rm -r .claude/harness .claude/skills/wf-* .claude/agents/wf-*.md .claude/hooks/guard-git.sh \\
            .claude/hooks/guard_git.py .claude/hooks/session-context.sh \\
            .claude/hooks/sync-context.sh .githooks/commit-msg
  then remove the '@.claude/harness/RULES.md' import from CLAUDE.md, the harness block from AGENTS.md,
  the harness hooks from .claude/settings.json, and run: git config --unset core.hooksPath
  (.work/ and release-please files are yours to keep or delete.)
MSG
  exit 0
fi

echo "Removing local-mode harness from $(pwd)"
paths="$(grep -v '^#' .claude/harness/local-paths.txt | sed 's#/$##' | grep -v -e '^$' -e '^.claude/settings.local.json$')"

python3 - << 'PY'
import json, os
p = ".claude/settings.local.json"
if os.path.exists(p):
    s = json.load(open(p))
    ours = (".claude/hooks/guard-git.sh", ".claude/hooks/session-context.sh", ".claude/hooks/sync-context.sh")
    for event, entries in list(s.get("hooks", {}).items()):
        keep = [e for e in entries if not any(any(o in h.get("command", "") for o in ours) for h in e.get("hooks", []))]
        if keep: s["hooks"][event] = keep
        else: del s["hooks"][event]
    if not s.get("hooks"): s.pop("hooks", None)
    if s.get("attribution") == {"commit": "", "pr": ""}: s.pop("attribution")
    if set(s) <= {"$schema"}: os.remove(p); print("  removed", p)
    else: open(p, "w").write(json.dumps(s, indent=2) + "\n"); print("  cleaned", p)
PY

hook="$common/hooks/commit-msg"
if [[ -f "$hook" ]] && grep -q 'Enforce Conventional Commits' "$hook"; then rm -f "$hook"; echo "  removed $hook"; fi

python3 - "$common/info/exclude" << 'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
t = p.read_text() if p.exists() else ""
if "# >>> claude-harness" in t and "# <<< claude-harness" in t:
    start, end = t.index("# >>> claude-harness"), t.index("# <<< claude-harness") + len("# <<< claude-harness\n")
    p.write_text(t[:start] + t[end:]); print("  removed exclude block")
PY

[[ -L .work ]] && rm .work && echo "  removed .work symlink"
while IFS= read -r entry; do
  [[ "$entry" == ".work" ]] && continue
  for p in $(compgen -G "$entry" || true); do rm -rf "$p"; echo "  removed $p"; done
done <<< "$paths"
rmdir .claude/hooks .claude/skills .claude/agents .claude 2>/dev/null || true

if [[ $purge -eq 1 ]]; then rm -rf "$common/harness-work" "$common/harness-sync"; echo "  purged $common/harness-work and harness-sync"
else echo "  kept work artifacts in $common/harness-work and handoffs/sync boards in harness-sync (use --purge-work to delete)"; fi
echo "Worktrees made by wf-new.sh still hold a copy: run uninstall.sh in each, or remove those worktrees."
[[ -z "$(git status --porcelain)" ]] && echo "git status: clean" || git status --short
