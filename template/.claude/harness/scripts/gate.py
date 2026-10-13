#!/usr/bin/env python3
"""Deterministic risk gate for a work item. Blocks whenever it is unsure.

Usage: gate.py <slug> [--no-write] [--allow-stale]
Exit codes: 0 PASS (or advisory/off mode), 1 BLOCK, 2 ESCALATE (max rounds reached), 3 usage/config error.
Reads the latest <work_dir>/<slug>/40-reviews/R<n>.findings.json and optional waivers.json.
Writes <work_dir>/<slug>/50-gate.md unless --no-write. Behaviour is configured by `gate` in harness.json.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hconfig import ConfigError, is_team_member, load, required_checks, team_members  # noqa: E402

CLASSES = {"security-exploitable", "data-loss", "functional", "degradation",
           "operability", "design", "cosmetic"}
EVIDENCE = {"executed-repro", "failing-test", "code-path", "assumption"}
OPEN_STATUSES = {"open", "disputed"}          # counted by the gate
CLOSED_STATUSES = {"verified", "rejected"}    # verified = fix confirmed; rejected = not a real issue
REQUIRED = ("id", "title", "lens", "class", "status", "p_trigger", "p_visible", "evidence")


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check).stdout.strip()


def is_commit(sha: str) -> bool:
    return bool(sha) and subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode == 0


def die(msg: str, code: int = 3) -> None:
    print(f"gate: {msg}", file=sys.stderr)
    sys.exit(code)


def paths_of(f: dict) -> list[str]:
    return [p.split(":", 1)[0] for p in f.get("files", []) if p]


def matches_critical(paths: list[str], patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch("/" + p, pat) for p in paths for pat in patterns)


def fingerprint(f: dict) -> str:
    """Stable identity of a finding across rounds (ids are renumbered; this is not)."""
    title = re.sub(r"[^a-z0-9]+", " ", str(f.get("title", "")).lower()).strip()
    first = (sorted(paths_of(f)) or [""])[0]
    return hashlib.sha1(f"{f.get('lens')}|{f.get('class')}|{first}|{title}".encode()).hexdigest()[:12]


def is_prob(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1


def validate(f: dict, i: int) -> list[str]:
    errs = [f"finding[{i}] missing '{k}'" for k in REQUIRED if k not in f]
    if errs:
        return errs
    if f["class"] not in CLASSES:
        errs.append(f"{f['id']}: unknown class '{f['class']}'")
    if f["evidence"] not in EVIDENCE:
        errs.append(f"{f['id']}: unknown evidence '{f['evidence']}'")
    if f["status"] not in OPEN_STATUSES | CLOSED_STATUSES:
        errs.append(f"{f['id']}: unknown status '{f['status']}'")
    for k in ("p_trigger", "p_visible"):
        if not is_prob(f[k]):
            errs.append(f"{f['id']}: {k} must be a number in [0,1], got {f[k]!r}")
    return errs


def load_waivers(path: pathlib.Path, problems: list[str]) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        problems.append(f"waivers.json invalid: {e}")
        return []
    items = data.get("waivers") if isinstance(data, dict) else None
    if not isinstance(items, list):
        problems.append('waivers.json must be {"waivers": [ {fingerprint, reason, by, date, head}, ... ]}')
        return []
    return items


def waiver_for(f: dict, fp: str, waivers: list[dict], cfg: dict, notes: list[str]) -> dict | None:
    wcfg = cfg["gate"]["waivers"]
    for w in waivers:
        if w.get("fingerprint") != fp:
            continue
        if not (w.get("reason") and w.get("by") and w.get("head")):
            notes.append(f"waiver {fp} ignored: needs reason, by and head")
            continue
        if wcfg.get("approvers") == "team":
            if team_members(cfg) and not is_team_member(cfg, str(w["by"])):
                notes.append(f"waiver {fp} ignored: '{w['by']}' is not in team (harness.json)")
                continue
        if f["class"] == "security-exploitable" and wcfg.get("require_security_ack", True) \
                and w.get("acknowledge_security") is not True:
            notes.append(f"waiver {fp} ignored: security waiver needs \"acknowledge_security\": true")
            continue
        files = paths_of(f)
        if not is_commit(str(w["head"])):
            notes.append(f"waiver {fp} ignored: head {str(w['head'])[:10]} is not a commit in this repo")
            continue
        if files:
            changed = git("diff", "--name-only", str(w["head"]), "HEAD", "--", *files, check=False)
            if changed:
                notes.append(f"waiver {fp} expired: {', '.join(changed.splitlines())} changed since {str(w['head'])[:10]}")
                continue
        return w
    return None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 1:
        die(__doc__.strip())
    slug = args[0]

    try:
        root = pathlib.Path(git("rev-parse", "--show-toplevel"))
        cfg = load(root)
    except (ConfigError, subprocess.CalledProcessError) as e:
        die(f"config: {e}")
    g = cfg["gate"]
    mode = g["mode"]
    work_dir = cfg["work_dir"]
    work = root / work_dir / slug
    if mode == "off":
        print(f"# Gate: {slug}\n\n**Verdict: OFF** · gate.mode is \"off\" in harness.json")
        return 0

    t_default, t_crit = float(g["default_threshold"]), float(g["critical_threshold"])
    penalty, max_rounds = float(g["assumption_penalty"]), int(g["max_review_rounds"])

    files = sorted((work / "40-reviews").glob("R*.findings.json"),
                   key=lambda p: int((re.search(r"R(\d+)", p.name) or [0, 0])[1]))
    blocks: list[str] = []
    warnings: list[str] = []
    rows: list[str] = []
    rnd = 0
    head_now = git("rev-parse", "HEAD")

    def flag(setting: str, msg: str) -> None:
        (warnings if g.get(setting) == "warn" else blocks).append(msg)

    if not files:
        blocks.append("no review found — run /wf-review in a fresh session")
        data: dict = {"findings": []}
    else:
        latest = files[-1]
        rnd = int(re.search(r"R(\d+)", latest.name).group(1))
        try:
            data = json.loads(latest.read_text())
        except json.JSONDecodeError as e:
            die(f"{latest} is not valid JSON: {e}")
        if data.get("round") != rnd:
            blocks.append(f"{latest.name}: 'round' is {data.get('round')!r}, expected {rnd}")
        reviewed = str(data.get("head", ""))
        if not is_commit(reviewed):
            blocks.append(f"{latest.name}: 'head' {reviewed!r} is not a commit in this repo")
        elif not head_now.startswith(reviewed) and "--allow-stale" not in flags:
            # Commits that only touch work artifacts (reviews, responses, logs) do not invalidate a review.
            code_changed = git("diff", "--name-only", reviewed, "HEAD", "--", ".", f":(exclude){work_dir}", check=False)
            if code_changed:
                flag("stale_review", f"stale review: code changed since {reviewed[:10]} (HEAD {head_now[:10]}) — re-run /wf-review")
        if git("status", "--porcelain", "--", ".", f":(exclude){work_dir}"):
            flag("dirty_tree", "uncommitted code changes — the gate only certifies committed work")

        # Checks the reviewer ran itself.
        checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
        for name, result in checks.items():
            if str(result).lower().startswith("fail"):
                blocks.append(f"check '{name}' failed in the review run")
        for name in required_checks(cfg):
            if str(checks.get(name, "")).lower() not in ("pass", "passed", "ok"):
                blocks.append(f"required check '{name}' not reported as pass (got {checks.get(name, 'missing')!r})")

        # Every configured reviewer actually ran.
        if g["require_all_lenses"]:
            ran = set(data.get("lenses_run", []))
            missing = [l for l in cfg["review"]["lenses"] if l not in ran]
            if cfg["review"]["adversary"] and not data.get("adversary_run"):
                missing.append("adversary")
            if missing:
                blocks.append(f"review incomplete — lenses not run: {', '.join(missing)}")

    findings = data.get("findings", [])
    if not isinstance(findings, list):
        blocks.append("'findings' must be a list")
        findings = []
    errs = [e for i, f in enumerate(findings) for e in validate(f, i)]
    blocks += [f"malformed findings: {e}" for e in errs]

    waivers = load_waivers(work / "waivers.json", blocks)
    survive_all, survive_crit = 1.0, 1.0
    if not errs:
        for f in findings:
            if f["status"] in CLOSED_STATUSES:
                continue
            fid, fp = f["id"], fingerprint(f)
            is_sec = f["class"] == "security-exploitable"
            is_crit = is_sec or f["class"] == "data-loss" or matches_critical(paths_of(f), g["critical_paths"])
            thr = t_crit if is_crit else t_default
            exp = min(1.0, f["p_trigger"] * f["p_visible"] * (penalty if f["evidence"] == "assumption" else 1.0))

            w = waiver_for(f, fp, waivers, cfg, warnings)
            verdict = f"waived by {w['by']}" if w else "ok"
            if not w:
                if is_sec and g["security_always_blocks"]:
                    verdict = "BLOCK (security)"
                elif f.get("blocking") is True:
                    verdict = "BLOCK (must-fix)"
                elif exp >= thr:
                    verdict = f"BLOCK (≥ {thr:.0%})"
                survive_all *= 1 - exp
                if is_crit:
                    survive_crit *= 1 - exp
                if verdict.startswith("BLOCK"):
                    blocks.append(f"{fid} {f['title']} — {verdict}, exposure {exp:.1%}")
            rows.append(f"| {fid} | `{fp}` | {f['class']} | {f['evidence']} | {exp:.1%} | {thr:.0%} | {verdict} | {f['title']} |")

    agg, agg_c = 1 - survive_all, 1 - survive_crit
    if agg >= t_default:
        blocks.append(f"aggregate exposure {agg:.1%} ≥ {t_default:.0%}")
    if agg_c >= t_crit:
        blocks.append(f"aggregate critical exposure {agg_c:.1%} ≥ {t_crit:.0%}")

    if not blocks:
        verdict, code = "PASS", 0
    elif rnd >= max_rounds:
        verdict, code = "ESCALATE", 2
    else:
        verdict, code = "BLOCK", 1
    if mode == "advisory" and code:
        warnings.insert(0, f"gate.mode is advisory: verdict {verdict} is reported but does not stop the work")
        code = 0

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# Gate: {slug}", "",
           f"**Verdict: {verdict}** · mode {mode} · profile {cfg['profile']} · round {rnd}/{max_rounds} · HEAD `{head_now[:10]}` · {now}", "",
           f"Aggregate exposure {agg:.2%} (limit {t_default:.0%}) · critical {agg_c:.2%} (limit {t_crit:.0%})", ""]
    if blocks:
        out += ["## Blocking", *[f"- {b}" for b in blocks], ""]
    if warnings:
        out += ["## Warnings", *[f"- {w}" for w in warnings], ""]
    if verdict == "ESCALATE":
        out += ["## Escalation", "Max review rounds reached. Likely a design problem, not a bug list:",
                "revisit the spec with a maintainer before another fix round.", ""]
    if rows:
        out += ["## Open findings", "Waive by fingerprint (see /wf-gate).", "",
                "| ID | Fingerprint | Class | Evidence | Exposure | Limit | Verdict | Title |",
                "|---|---|---|---|---|---|---|---|", *rows, ""]
    text = "\n".join(out)
    if "--no-write" not in flags and work.exists():
        (work / "50-gate.md").write_text(text)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
