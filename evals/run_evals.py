#!/usr/bin/env python3
"""Measure the review: does a headless /wf-review catch seeded defects, and how stable is it?

Usage: python3 -I evals/run_evals.py [--case NAME ...] [--runs N] [--model MODEL] [--dry-run] [--keep] [--out DIR]

Each case in evals/cases/ is the shared fixture app plus one change (evals/cases/<name>/change/) that seeds
one known defect (case.json "defect"), or none for a control. Per run the script builds a throwaway repo,
installs the harness, commits the fixture and then the change, writes an approved spec from case.json, runs
`claude -p "/wf-review <case>"` and scores the round it wrote:
  caught   a finding names the defect's file (when given) and one of its keywords
  lens     that finding came from one of the defect's expected lenses
  blocked  the gate returned BLOCK or ESCALATE (expected for every seeded case; a control should pass);
           gate errors (no round written, malformed findings, config) are counted separately
--runs N > 1 repeats each case (G2 consistency): how often the defect is caught, verdict agreement and the
spread of the matched finding's exposure. Results go to evals/results/<utc time>.json.

Every run is a real headless review with every lens and the adversary, so it costs real tokens.
--dry-run builds each fixture and runs its tests without calling claude.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

EVALS = pathlib.Path(__file__).resolve().parent
HARNESS = EVALS.parent
TEST_CMD = "python3 -m unittest discover -s tests -q"


def run(cmd, cwd, check=True, **kw):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} failed ({r.returncode}):\n{r.stdout}{r.stderr}")
    return r


def commit(repo, msg, *paths):
    run(["git", "add", "-A", *paths], repo)
    run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", msg], repo)


def spec(case: dict) -> str:
    acs = "\n".join(f"- {a}" for a in case["acs"])
    return (f"# Spec\n\nStatus: Approved\n\n## 1. Problem and outcome\n{case['brief']}\n\n"
            f"## 3. User-visible behaviour\nAs in the acceptance criteria.\n\n## 12. Acceptance criteria\n{acs}\n\n"
            f"## 13. Tasks\n- T1: implement and test all acceptance criteria\n")


def build(name: str, case: dict, repo: pathlib.Path) -> pathlib.Path:
    """Fixture repo at `repo` with the harness installed, the case's change committed on top, and an approved spec.
    The work item's slug is the repo's directory name."""
    shutil.copytree(EVALS / "fixture", repo)
    run(["git", "init", "-q", "-b", "main"], repo)
    run(["git", "config", "user.name", "Eval Lead"], repo)
    run(["git", "config", "user.email", "lead@example.invalid"], repo)
    commit(repo, "chore: init")
    run(["bash", str(HARNESS / "install.sh"), str(repo)], repo)
    cfg_p = repo / ".claude/harness/harness.json"
    cfg = json.loads(cfg_p.read_text())
    cfg.setdefault("commands", {})["test"] = TEST_CMD
    cfg_p.write_text(json.dumps(cfg, indent=2))
    commit(repo, "build: harness")
    base = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    shutil.copytree(EVALS / "cases" / name / "change", repo, dirs_exist_ok=True)
    commit(repo, f"feat: {case['brief'][:60].lower().rstrip('.')}", "app", "tests")
    work = repo / ".work" / repo.name
    work.mkdir(parents=True)
    (work / "00-brief.md").write_text(f"# Brief\n\n{case['brief']}\n")
    (work / "20-spec.md").write_text(spec(case))
    (work / "state.json").write_text(json.dumps({"slug": repo.name, "branch": "main", "base": base, "phase": "built",
                                                 "review_round": 0, "track": "standard"}))
    return repo


def score(case: dict, findings: list) -> dict:
    d = case["defect"]
    if d is None:
        return {"caught": None, "lens": None, "exposure": None}
    hits = []
    for f in findings:
        text = json.dumps(f).lower()
        paths = [str(p).split(":")[0] for p in f.get("files", [])]
        file_ok = not d["file"] or any(p == d["file"] or p == "./" + d["file"] for p in paths)
        if file_ok and any(k.lower() in text for k in d["keywords"]):
            hits.append(f)
    best = max(hits, key=lambda f: f.get("p_trigger", 0) * f.get("p_visible", 0), default=None)
    return {"caught": bool(hits), "lens": bool(best) and best.get("lens") in d["lenses"],
            "exposure": None if best is None else round(best.get("p_trigger", 0) * best.get("p_visible", 0), 4),
            "matched": None if best is None else best.get("title")}


def review(repo: pathlib.Path, name: str, model: str | None) -> dict:
    tools = ",".join(json.loads(run(["python3", ".claude/harness/scripts/hconfig.py", "loop.review_tools"],
                                    repo).stdout))
    tools += f",Write(.work/{name}/**),Edit(.work/{name}/**)"
    cmd = ["claude", "-p", f"/wf-review {name}", "--allowedTools", tools, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    t0 = time.time()
    try:
        r = run(cmd, repo, check=False, timeout=3600)
        code, stdout = r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        code, stdout = "timeout", ""
    try:
        out = json.loads(stdout)
    except ValueError:
        out = {}
    rounds = sorted((repo / ".work" / name / "40-reviews").glob("R*.findings.json"))
    data = json.loads(rounds[-1].read_text()) if rounds else None
    gate = run(["python3", ".claude/harness/scripts/gate.py", name, "--no-write"], repo, check=False)
    return {"exit": code, "minutes": round((time.time() - t0) / 60, 1), "cost_usd": out.get("total_cost_usd"),
            "turns": out.get("num_turns"), "wrote_round": data is not None,
            "findings": (data or {}).get("findings", []), "gate_exit": gate.returncode}


def summarise(name: str, case: dict, runs: list) -> dict:
    n = len(runs)
    # gate exits: 0 pass, 1 block, 2 escalate (a block too); anything else is an error, not a verdict.
    verdicts = [{0: "pass", 1: "block", 2: "block"}.get(r["gate_exit"], "error") for r in runs]
    s = {"case": name, "seeded": case["defect"] is not None, "runs": n,
         "wrote_round": sum(r["wrote_round"] for r in runs),
         "blocked": verdicts.count("block"), "gate_errors": verdicts.count("error"),
         "verdict_agreement": max(verdicts.count("pass"), verdicts.count("block")) / n,
         "findings_per_run": [len(r["findings"]) for r in runs],
         "cost_usd": round(sum(r["cost_usd"] or 0 for r in runs), 2)}
    if s["seeded"]:
        exps = [r["score"]["exposure"] for r in runs if r["score"]["exposure"] is not None]
        s.update({"caught": sum(bool(r["score"]["caught"]) for r in runs),
                  "right_lens": sum(bool(r["score"]["lens"]) for r in runs),
                  "exposure_range": [min(exps), max(exps)] if exps else None})
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case", action="append", help="case name (repeatable); default all")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the throwaway repos and print where")
    ap.add_argument("--out", type=pathlib.Path, default=EVALS / "results", help="results directory")
    a = ap.parse_args()
    names = a.case or sorted(p.name for p in (EVALS / "cases").iterdir() if (p / "case.json").exists())
    if not a.dry_run and shutil.which("claude") is None:
        print("claude CLI not found", file=sys.stderr)
        return 3
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="harness-evals-"))
    env_ok = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    results, problems = [], []
    try:
        for name in names:
            case = json.loads((EVALS / "cases" / name / "case.json").read_text())
            runs = []
            for i in range(1 if a.dry_run else a.runs):
                repo = build(name, case, tmp / (name if i == 0 else f"{name}-{i + 1}"))
                if a.dry_run:
                    t = run(TEST_CMD.split(), repo, check=False, env=env_ok)
                    seeded = case["defect"] and case["defect"]["file"]
                    if t.returncode != 0:
                        problems.append(f"{name}: fixture tests fail:\n{t.stdout}{t.stderr}")
                    elif seeded and not (repo / seeded).exists():
                        problems.append(f"{name}: defect file {seeded} missing")
                    else:
                        print(f"ok   {name}")
                    continue
                print(f"..   {name} run {i + 1}/{a.runs}", flush=True)
                r = review(repo, repo.name, a.model)
                r["score"] = score(case, r["findings"])
                runs.append(r)
            if runs:
                results.append({"summary": summarise(name, case, runs), "runs": runs})
    finally:
        if a.keep:
            print(f"repos kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    if a.dry_run:
        for p in problems:
            print(f"FAIL {p}", file=sys.stderr)
        return 1 if problems else 0
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"date": stamp, "model": a.model, "runs_per_case": a.runs, "cases": results}, indent=2))
    print(f"\n{'case':<18} {'caught':>7} {'lens':>5} {'blocked':>8} {'agree':>6} {'exposure':>13} {'cost $':>7}")
    for r in results:
        s = r["summary"]
        caught = f"{s['caught']}/{s['runs']}" if s["seeded"] else "ctrl"
        lens = f"{s['right_lens']}/{s['runs']}" if s["seeded"] else "-"
        er = s.get("exposure_range")
        exp = f"{er[0]:.0%}–{er[1]:.0%}" if er else "-"
        print(f"{s['case']:<18} {caught:>7} {lens:>5} {s['blocked']:>6}/{s['runs']} {s['verdict_agreement']:>6.0%} "
              f"{exp:>13} {s['cost_usd']:>7.2f}")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
