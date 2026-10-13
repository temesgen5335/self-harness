#!/usr/bin/env bash
# One line per work item: slug, phase, review round, latest gate verdict.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
python3 - "$root" << 'PY'
import json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
wd = json.loads((root / ".claude/harness/harness.json").read_text()).get("work_dir", ".work")
print(f"{'SLUG':<28} {'PHASE':<14} {'ROUND':<6} {'GATE':<9} BRANCH")
for sp in sorted((root / wd).glob("*/state.json")):
    s = json.loads(sp.read_text()); g = "-"
    gp = sp.parent / "50-gate.md"
    if gp.exists():
        m = re.search(r"Verdict: (\w+)", gp.read_text()); g = m.group(1) if m else "?"
    print(f"{s.get('slug','?'):<28} {s.get('phase','?'):<14} {str(s.get('review_round',0)):<6} {g:<9} {s.get('branch','')}")
PY
