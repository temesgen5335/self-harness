#!/usr/bin/env python3
"""Read/update .work/<slug>/state.json.
Usage: wf-state.py <slug> get [key] | set key=value [key=value ...]"""
import json, pathlib, subprocess, sys

def main() -> int:
    if len(sys.argv) < 3 or sys.argv[2] not in ("get", "set"):
        print(__doc__, file=sys.stderr); return 3
    slug, op, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    root = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    cfg = json.loads((root / ".claude/harness/harness.json").read_text())
    p = root / cfg.get("work_dir", ".work") / slug / "state.json"
    state = json.loads(p.read_text()) if p.exists() else {"slug": slug}
    if op == "get":
        print(json.dumps(state.get(rest[0]) if rest else state, indent=2)); return 0
    for kv in rest:
        k, _, v = kv.partition("=")
        try: state[k] = json.loads(v)
        except json.JSONDecodeError: state[k] = v
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2) + "\n")
    return 0

sys.exit(main())
