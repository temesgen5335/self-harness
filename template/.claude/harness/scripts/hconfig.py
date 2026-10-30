#!/usr/bin/env python3
"""Effective harness configuration: profile defaults deep-merged with .claude/harness/harness.json.

Usage: hconfig.py [dotted.key]     print the effective config (or one key) as JSON
Library: from hconfig import load; cfg = load(root)

Profiles set defaults only; any key in harness.json overrides them.
  strict   : Claude never stages/commits/pushes; gate enforces with tighter limits
  standard : git writes need explicit approval (ask); gate enforces           (default)
  light    : git writes need approval; gate is advisory; two lenses, no adversary
  guided   : the guard warns and reminds instead of blocking (secrets stay enforced); validation before PR
"""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

ALLOW, ASK, BLOCK = "allow", "ask", "block"
GIT_OPS = ("stage", "commit", "push", "pr", "merge", "tag", "release", "history", "destructive", "skip_hooks",
           # beyond git: recursive deletes, reading secret files, piping downloads into a shell
           "destructive_fs", "secrets", "remote_exec")

BASE = {
    "profile": "standard",
    "mode": "tracked",                   # tracked | local (set by install.sh; see README "Tracked vs local mode")
    "work_dir": ".work",
    "default_branch": "main",
    "team": {"lead": {"name": "", "email": ""}, "collaborators": []},
    "commands": {"install": "", "lint": "", "typecheck": "", "test": "", "stress": "", "build": ""},
    # Work branches (wf-new.sh): <prefix>/[<ticket>-]<slug>, cut from `base` (empty = default_branch).
    # ticket: "optional", or "warn" to warn when wf-new.sh gets no --ticket.
    "branching": {
        "base": "",
        "prefixes": {"feat": "feat", "fix": "fix", "chore": "chore", "refactor": "refactor", "docs": "docs"},
        "ticket": "optional",
    },
    # Project docs the workflow writes to when set: ADRs from /wf-spec, the changelog and PR body from /wf-pr.
    "docs": {"adr_dir": "", "changelog": "", "pr_template": ".github/pull_request_template.md"},
    # /wf-validate: where evidence goes is the work dir; a frozen task set is re-run for LLM/RAG changes.
    # required: /wf-pr asks for a recorded /wf-validate result (go / go with accepted risk) first.
    "validation": {"frozen_task_set": "", "required": False},
    "git": {
        "guard": "enforce",              # enforce | warn | off
        "on_unparseable": BLOCK,         # what to do with a command the guard cannot parse
        "ops": {"stage": ASK, "commit": ASK, "push": ASK, "pr": ASK, "merge": BLOCK, "tag": BLOCK,
                "release": BLOCK, "history": BLOCK, "destructive": BLOCK, "skip_hooks": BLOCK,
                "destructive_fs": ASK, "secrets": ASK, "remote_exec": ASK},
        "always_enforce": [],            # ops that keep their decision when guard is "warn"
        "notes": {},                     # op -> reminder added to warn-mode messages
    },
    "gate": {
        "mode": "enforce",               # enforce | advisory | off
        "default_threshold": 0.05,
        "critical_threshold": 0.01,
        "critical_paths": ["**/auth/**", "**/payments/**", "**/migrations/**", "**/security/**"],
        "assumption_penalty": 2.0,
        "max_review_rounds": 4,
        "security_always_blocks": True,
        "checks_required": "auto",       # "auto" = every non-empty command except install; or a list
        "require_all_lenses": True,
        "stale_review": BLOCK,           # block | warn
        "dirty_tree": BLOCK,             # block | warn
        "waivers": {"approvers": "team", "require_security_ack": True},
    },
    "review": {
        "lenses": ["correctness", "security", "scale", "operability", "design", "experience"],
        "adversary": True,
    },
    # Headless sessions started by wf-loop.sh. The review session also gets Write/Edit scoped to the work dir.
    # Both run under the git guard, and an "ask" decision is refused headless; narrow fix_tools (for example
    # "Bash(npm test:*)") to limit what an unattended fix session can run. "Task" is the older name of "Agent".
    "loop": {
        "review_tools": ["Read", "Grep", "Glob", "Bash", "Agent", "Task", "WebSearch", "WebFetch"],
        "fix_tools": ["Read", "Grep", "Glob", "Bash", "Agent", "Task", "Edit", "Write"],
    },
    # Work-item tracks (wf-new.sh --track). "standard" uses `review`; "lite" is for small, low-risk changes
    # and is upgraded to standard automatically when the diff outgrows it (see wf-track.py).
    "tracks": {
        "lite": {
            "max_changed_lines": 150,
            "lenses": ["correctness", "security"],
            "adversary": False,
            # Changes that are never "small": dependency manifests and migrations.
            "upgrade_paths": ["**/package.json", "**/package-lock.json", "**/pnpm-lock.yaml", "**/yarn.lock",
                              "**/requirements*.txt", "**/pyproject.toml", "**/poetry.lock", "**/uv.lock",
                              "**/go.mod", "**/go.sum", "**/Cargo.toml", "**/Cargo.lock", "**/pom.xml",
                              "**/build.gradle*", "**/migrations/**", "**/alembic/**", "**/*.sql"],
        },
    },
}

PROFILES = {
    "standard": {},
    "strict": {
        "git": {"on_unparseable": BLOCK,
                "ops": {"stage": BLOCK, "commit": BLOCK, "push": BLOCK, "pr": BLOCK,
                        "secrets": BLOCK, "remote_exec": BLOCK}},
        "gate": {"default_threshold": 0.03, "critical_threshold": 0.005, "max_review_rounds": 3},
    },
    # For teams whose guard must never block: it warns and reminds, except for secrets, which stay
    # enforced because a warning after a secret was read is too late. A preset adds team conventions.
    "guided": {
        "git": {
            "guard": "warn",
            "on_unparseable": ASK,
            "always_enforce": ["secrets"],
            "ops": {"stage": ALLOW, "commit": ASK, "push": BLOCK, "pr": ASK, "merge": BLOCK,
                    "secrets": BLOCK, "remote_exec": ASK},
            "notes": {
                "commit": "Commit at a natural completion point; no Co-Authored-By or attribution; tell the user the hash, message and files.",
                "push": "Push is the user's: print the exact git push command and wait for them to run it.",
                "merge": "Merging is the user's: print the exact command and wait.",
                "pr": "Draft the PR with /wf-pr (the project's PR template, never --fill) and print gh pr create for the user.",
                "skip_hooks": "Never bypass hooks (--no-verify, core.hooksPath): fix what the hook found.",
                "history": "Rewrites history: only when the user asked for exactly this; never on dev/staging/production.",
                "destructive": "Discards work: only when the user asked for exactly this.",
                "destructive_fs": "Recursive delete: check the target first.",
                "remote_exec": "Piping a download into a shell: pin and inspect it instead.",
            },
        },
        "validation": {"required": True},
    },
    "light": {
        "git": {"on_unparseable": ASK},
        "gate": {"mode": "advisory", "require_all_lenses": False, "stale_review": "warn", "dirty_tree": "warn"},
        "review": {"lenses": ["correctness", "security"], "adversary": False},
    },
}


def merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def repo_root() -> pathlib.Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return pathlib.Path(out.stdout.strip())


class ConfigError(Exception):
    pass


def load(root: pathlib.Path | None = None) -> dict:
    """Return the effective config. Raises ConfigError on unreadable JSON or an unknown profile."""
    root = root or repo_root()
    path = root / ".claude/harness/harness.json"
    user: dict = {}
    if path.exists():
        try:
            user = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path}: invalid JSON: {e}") from e
    profile = user.get("profile", BASE["profile"])
    if profile not in PROFILES:
        raise ConfigError(f"unknown profile '{profile}' (use one of: {', '.join(PROFILES)})")
    cfg = merge(merge(BASE, PROFILES[profile]), user)
    cfg["profile"] = profile
    return cfg


def required_checks(cfg: dict) -> list[str]:
    req = cfg["gate"]["checks_required"]
    if req == "auto":
        return [k for k, v in cfg["commands"].items() if k != "install" and str(v).strip()]
    return list(req)


def team_members(cfg: dict) -> list[dict]:
    t = cfg.get("team", {})
    people = [t.get("lead", {})] + list(t.get("collaborators", []))
    return [p for p in people if p.get("name") or p.get("email")]


def is_team_member(cfg: dict, who: str) -> bool:
    who = who.strip().lower()
    return any(who and who in {str(p.get("name", "")).lower(), str(p.get("email", "")).lower()}
               for p in team_members(cfg))


def main() -> int:
    try:
        cfg = load()
    except (ConfigError, subprocess.CalledProcessError) as e:
        print(f"hconfig: {e}", file=sys.stderr)
        return 3
    val = cfg
    for part in (sys.argv[1].split(".") if len(sys.argv) > 1 else []):
        if not isinstance(val, dict) or part not in val:
            print(f"hconfig: no key '{sys.argv[1]}'", file=sys.stderr)
            return 3
        val = val[part]
    print(val if isinstance(val, str) else json.dumps(val, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
