#!/usr/bin/env python3
"""Per-work-item session metrics for wf-loop.sh (duration, cost, turns, refused tool calls).

Usage:
  claude -p ... --output-format json | wf-metrics.py <slug> record <phase> <round>
      appends one line to <work_dir>/<slug>/metrics.jsonl and prints the session's result text.
      Output that is not JSON is passed through unchanged and recorded as unparsed.
  wf-metrics.py <slug> summary
      prints totals per phase.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hconfig import ConfigError, load  # noqa: E402


def metrics_path(slug: str) -> pathlib.Path:
    root = pathlib.Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                                       text=True, check=True).stdout.strip())
    return root / load(root)["work_dir"] / slug / "metrics.jsonl"


def record(path: pathlib.Path, phase: str, rnd: str, raw: str) -> str:
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "phase": phase, "round": int(rnd) if rnd.isdigit() else rnd}
    try:
        out = json.loads(raw)
        if not isinstance(out, dict):
            raise ValueError("not an object")
    except ValueError:
        row["parsed"] = False
        text = raw
    else:
        row.update({"parsed": True, "session_id": out.get("session_id"), "is_error": out.get("is_error"),
                    "duration_ms": out.get("duration_ms"), "cost_usd": out.get("total_cost_usd"),
                    "turns": out.get("num_turns"), "denied_tool_calls": len(out.get("permission_denials") or []),
                    "models": sorted(out.get("modelUsage") or {})})
        text = out.get("result") or ""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return text


def summary(path: pathlib.Path) -> str:
    if not path.exists():
        return "no metrics yet"
    totals: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        t = totals.setdefault(row.get("phase", "?"), {"sessions": 0, "minutes": 0.0, "cost_usd": 0.0,
                                                       "turns": 0, "denied": 0, "errors": 0})
        t["sessions"] += 1
        t["minutes"] += (row.get("duration_ms") or 0) / 60000
        t["cost_usd"] += row.get("cost_usd") or 0
        t["turns"] += row.get("turns") or 0
        t["denied"] += row.get("denied_tool_calls") or 0
        t["errors"] += 1 if row.get("is_error") or not row.get("parsed") else 0
    lines = [f"{'phase':<8} {'sessions':>8} {'minutes':>8} {'cost $':>8} {'turns':>6} {'denied':>6} {'errors':>6}"]
    for phase, t in totals.items():
        lines.append(f"{phase:<8} {t['sessions']:>8} {t['minutes']:>8.1f} {t['cost_usd']:>8.2f} "
                     f"{t['turns']:>6} {t['denied']:>6} {t['errors']:>6}")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 4 and args[1] == "record" or len(args) == 2 and args[1] == "summary":
        try:
            path = metrics_path(args[0])
        except (ConfigError, subprocess.CalledProcessError) as e:
            print(f"wf-metrics: {e}", file=sys.stderr)
            return 3
        if args[1] == "record":
            print(record(path, args[2], args[3], sys.stdin.read()))
        else:
            print(summary(path))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
