#!/usr/bin/env python3
"""Effective review plan for a work item: its track, and the lenses and adversary that review must run.

Usage: wf-track.py <slug>       prints JSON {"track", "requested", "lenses", "adversary", "reasons"}
Library: gate.py loads this file and calls plan(), so /wf-review and the gate always agree.

A work item started with `wf-new.sh --track lite` is reviewed by the lite lenses only while it stays small:
it is upgraded to the standard track when the diff exceeds tracks.lite.max_changed_lines, touches
gate.critical_paths, or touches tracks.lite.upgrade_paths (dependencies, migrations).
"""
from __future__ import annotations

import fnmatch
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hconfig import ConfigError, load  # noqa: E402


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch("/" + path, p) for p in patterns)


def plan(root: pathlib.Path, cfg: dict, slug: str, head: str = "HEAD") -> dict:
    state_p = root / cfg["work_dir"] / slug / "state.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    requested = state.get("track", "standard")
    full = {"track": "standard", "requested": requested, "lenses": list(cfg["review"]["lenses"]),
            "adversary": bool(cfg["review"]["adversary"]), "reasons": []}
    lite = cfg.get("tracks", {}).get("lite")
    if requested != "lite" or not lite:
        return full
    base = state.get("base", "")
    reasons = []
    if base:
        work_dir = cfg["work_dir"]
        numstat = git(root, "diff", "--numstat", f"{base}...{head}", "--", ".", f":(exclude){work_dir}")
        changed, files = 0, []
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                files.append(parts[2])
                changed += sum(int(x) for x in parts[:2] if x.isdigit())
        if changed > int(lite["max_changed_lines"]):
            reasons.append(f"{changed} changed lines > lite limit {lite['max_changed_lines']}")
        crit = [f for f in files if matches(f, cfg["gate"]["critical_paths"])]
        if crit:
            reasons.append(f"touches critical path(s): {', '.join(crit[:3])}")
        deps = [f for f in files if matches(f, lite.get("upgrade_paths", []))]
        if deps:
            reasons.append(f"touches dependencies or migrations: {', '.join(deps[:3])}")
    if reasons:
        full["reasons"] = ["lite track upgraded to standard: " + r for r in reasons]
        return full
    return {"track": "lite", "requested": "lite", "lenses": list(lite["lenses"]),
            "adversary": bool(lite["adversary"]), "reasons": []}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 3
    root = pathlib.Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                                       text=True, check=True).stdout.strip())
    try:
        cfg = load(root)
    except ConfigError as e:
        print(f"wf-track: {e}", file=sys.stderr)
        return 3
    print(json.dumps(plan(root, cfg, sys.argv[1]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
