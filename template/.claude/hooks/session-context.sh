#!/usr/bin/env bash
# SessionStart: print a short orientation (stdout becomes session context). Keep it tiny.
set -uo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[[ -f "$root/.claude/harness/harness.json" ]] || exit 0
branch="$(git -C "$root" branch --show-current 2>/dev/null)"
python3 - "$root" "$branch" << 'PY' || true
import json, pathlib, re, sys
root, branch = pathlib.Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(root / ".claude/harness/scripts"))
from hconfig import load, team_members
cfg = load(root); wd = cfg["work_dir"]
if cfg.get("mode") == "local":  # CLAUDE.md is not touched in local mode, so the rules are injected here
    print((root / ".claude/harness/RULES.md").read_text())
team = ", ".join(p.get("name") or p.get("email") for p in team_members(cfg)) or "not set (edit team in harness.json)"
ops = cfg["git"]["ops"]
print(f"[harness] maintainers: {team} · profile {cfg['profile']} · gate {cfg['gate']['mode']} · "
      f"git guard {cfg['git']['guard']} (commit: {ops.get('commit')}, push: {ops.get('push')})")
nxt = {"new": "/wf-investigate", "investigated": "/wf-spec (fresh session)",
       "specified": "wait for a maintainer to approve the spec", "approved": "/wf-build",
       "building": "/wf-build (next task) or /wf-commit", "built": "/wf-review (fresh session)",
       "reviewed": "/wf-fix in build session, or done if gate PASS", "fixing": "/wf-fix, then /wf-commit",
       "passed": "/wf-pr drafts the PR; /wf-validate before promotion; after merge /wf-release",
       "validated": "/wf-pr, or promote", "validation-hold": "/wf-fix the validation defects, then /wf-validate",
       "released": "nothing"}
for sp in (root / wd).glob("*/state.json"):
    s = json.loads(sp.read_text())
    if s.get("branch") != branch:
        continue
    g = sp.parent / "50-gate.md"
    gate = (re.search(r"Verdict: (\w+)", g.read_text()) or [None, "-"])[1] if g.exists() else "-"
    ph = s.get("phase", "?")
    print(f"[harness] work item '{s.get('slug')}' · phase {ph} · review round {s.get('review_round', 0)} · gate {gate}")
    print(f"[harness] artifacts: {wd}/{s.get('slug')}/ · next: {nxt.get(ph, '/wf-status')}")
    break
else:
    print("[harness] no work item on this branch. Start one with: .claude/harness/scripts/wf-new.sh <slug> \"<brief>\"")
PY
exit 0
