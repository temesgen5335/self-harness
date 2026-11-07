#!/usr/bin/env python3
"""Suggest the project's check commands (install, lint, typecheck, test, build) from its files.

Usage: detect-commands.py [--apply] [--replace-stale] [--set key=value ...]
  (no flags)        print what is configured, what was detected, and which configured commands look broken
  --apply           write to harness.json: fill empty commands with detected ones, and apply --set values
  --replace-stale   with --apply, also replace commands that look broken (install.sh passes it for commands a
                    preset just set; a command you wrote yourself is only reported)
  --set key=value   set a command explicitly (repeatable); wins over detection

It reads files only and never runs a project command. Detected commands are a best guess: run each once.
A command "looks broken" when the script it names is missing, its make target does not exist, or its
package.json script does not exist. Sources, first match wins: Makefile targets, package.json scripts, then
Python (uv / poetry / pdm), Go and Rust conventions.
"""
from __future__ import annotations

import json
import pathlib
import re
import shlex
import subprocess
import sys

KEYS = ("install", "lint", "typecheck", "test", "build")
ALIASES = {"typecheck": ("typecheck", "type-check", "types", "tsc"), "lint": ("lint",), "test": ("test",),
           "build": ("build",), "install": ("install",)}
NPM_DEFAULT_TEST = "no test specified"


def read(p: pathlib.Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def make_targets(root: pathlib.Path) -> set:
    targets = set()
    for name in ("Makefile", "makefile", "GNUmakefile"):
        for line in read(root / name).splitlines():
            m = re.match(r"^([A-Za-z0-9_.\- ]+?)\s*:(?!=)", line)
            if m and not line.startswith(("\t", "#", ".")):
                targets.update(m.group(1).split())
    return targets


def pkg_scripts(root: pathlib.Path) -> dict:
    try:
        scripts = json.loads(read(root / "package.json") or "{}").get("scripts") or {}
    except ValueError:
        return {}
    return {k: v for k, v in scripts.items() if isinstance(v, str)}


def node_pm(root: pathlib.Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if (root / lock).exists():
            return pm
    return "npm"


def node_install(root: pathlib.Path, pm: str) -> str:
    return {"pnpm": "pnpm install --frozen-lockfile", "yarn": "yarn install --frozen-lockfile", "bun": "bun install",
            "npm": "npm ci" if (root / "package-lock.json").exists() else "npm install"}[pm]


def detect(root: pathlib.Path) -> dict:
    """{key: (command, source)} for each key something was found for."""
    out: dict = {}

    def put(key, cmd, src):
        out.setdefault(key, (cmd, src))

    targets = make_targets(root)
    for key in KEYS:
        for alias in ALIASES[key]:
            if alias in targets:
                put(key, f"make {alias}", f"Makefile target '{alias}'")
                break

    scripts = pkg_scripts(root)
    if (root / "package.json").exists():
        pm = node_pm(root)
        put("install", node_install(root, pm), f"package.json + {pm}")
        for key in ("lint", "typecheck", "test", "build"):
            for alias in ALIASES[key]:
                body = scripts.get(alias)
                if body and NPM_DEFAULT_TEST not in body:
                    put(key, f"{pm} run {alias}", f"package.json script '{alias}'")
                    break
        if "typecheck" not in out and (root / "tsconfig.json").exists():
            put("typecheck", "npx tsc --noEmit", "tsconfig.json")

    pyproject = read(root / "pyproject.toml")
    reqs = "".join(read(p) for p in sorted(root.glob("requirements*.txt")))
    if pyproject or reqs or (root / "setup.py").exists():
        run = ""
        for lock, prefix, inst in (("uv.lock", "uv run ", "uv sync"), ("poetry.lock", "poetry run ", "poetry install"),
                                   ("pdm.lock", "pdm run ", "pdm install")):
            if (root / lock).exists():
                run = prefix
                put("install", inst, lock)
                break
        else:
            if (root / "requirements.txt").exists():
                put("install", "pip install -r requirements.txt", "requirements.txt")

        def tool(name):
            return re.search(rf"^\[tool\.{name}[\].]", pyproject, re.M) is not None

        if tool("ruff") or (root / "ruff.toml").exists() or (root / ".ruff.toml").exists():
            put("lint", f"{run}ruff check .", "ruff config")
        elif (root / ".flake8").exists() or "[flake8]" in read(root / "setup.cfg"):
            put("lint", f"{run}flake8", "flake8 config")
        if tool("mypy") or (root / "mypy.ini").exists() or (root / ".mypy.ini").exists():
            put("typecheck", f"{run}mypy .", "mypy config")
        elif tool("pyright") or (root / "pyrightconfig.json").exists():
            put("typecheck", f"{run}pyright", "pyright config")
        if tool("pytest") or (root / "pytest.ini").exists() or (root / "conftest.py").exists() or \
                re.search(r"\bpytest\b", pyproject + reqs):
            put("test", f"{run}pytest -q", "pytest")
        elif (root / "tests").is_dir() and any((root / "tests").glob("test_*.py")):
            put("test", f"{run}python -m unittest discover -s tests -q", "tests/test_*.py")

    if (root / "go.mod").exists():
        put("lint", "go vet ./...", "go.mod"); put("test", "go test ./...", "go.mod"); put("build", "go build ./...", "go.mod")
    if (root / "Cargo.toml").exists():
        put("lint", "cargo clippy -- -D warnings", "Cargo.toml"); put("test", "cargo test", "Cargo.toml")
        put("build", "cargo build", "Cargo.toml")
    return out


def broken(root: pathlib.Path, cmd: str) -> str | None:
    """Why a configured command cannot run here, or None. Checks files only; never runs anything."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None
    if not tokens:
        return None
    if tokens[0] == "make":
        targets = make_targets(root)
        wanted = [t for t in tokens[1:] if not t.startswith("-") and "=" not in t]
        if not targets:
            return "no Makefile"
        missing = [t for t in wanted if t not in targets]
        return f"make target '{missing[0]}' does not exist" if missing else None
    if tokens[0] in ("npm", "pnpm", "yarn", "bun") and len(tokens) > 2 and tokens[1] == "run":
        return None if tokens[2] in pkg_scripts(root) else f"package.json has no script '{tokens[2]}'"
    for t in tokens[1:] if tokens[0] in ("bash", "sh", "python", "python3", "node") else tokens[:1]:
        if t.startswith("-") or "..." in t:
            continue
        if ("/" in t or t.endswith((".sh", ".py", ".js", ".mjs"))) and not t.startswith("/"):
            if not (root / t).exists():
                return f"{t} does not exist"
            break
    return None


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="detect-commands.py", description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--replace-stale", action="store_true")
    ap.add_argument("--set", action="append", default=[], metavar="key=value")
    a = ap.parse_args(argv)
    root = pathlib.Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                                       check=True).stdout.strip())
    path = root / ".claude/harness/harness.json"
    cfg = json.loads(read(path) or "{}")
    cmds = cfg.setdefault("commands", {})
    explicit = {}
    for kv in a.set:
        k, sep, v = kv.partition("=")
        if not sep or k not in KEYS + ("stress",):
            print(f"detect-commands: --set wants key=value with key in {', '.join(KEYS + ('stress',))}", file=sys.stderr)
            return 3
        explicit[k] = v.strip()
    found = detect(root)
    changed = []
    for key in KEYS + ("stress",):
        cur = str(cmds.get(key, "")).strip()
        if key in explicit:
            new, why = explicit[key], "set explicitly"
        elif key == "stress":
            continue
        else:
            det = found.get(key)
            bad = broken(root, cur) if cur else None
            if cur and not bad:
                print(f"  {key:<9} {cur}")
                continue
            if cur and bad and not a.replace_stale:
                print(f"  {key:<9} {cur}  <- WARNING: {bad}; fix it in harness.json"
                      + (f" (detected: {det[0]})" if det else ""))
                continue
            if not det:
                print(f"  {key:<9} (none)" + (f"  <- dropped '{cur}': {bad}" if cur else ""))
                if cur and a.apply:
                    cmds[key] = ""; changed.append(key)
                continue
            new, why = det[0], f"detected from {det[1]}" + (f"; replaced '{cur}': {bad}" if cur else "")
        print(f"  {key:<9} {new or '(none)'}  <- {why}")
        if a.apply and cmds.get(key) != new:
            cmds[key] = new; changed.append(key)
    if not str(cmds.get("test", "")).strip():
        print("  WARNING: no test command, so the gate will not require tests. Set one:\n"
              "           install.sh <repo> --command test='<your test command>'")
    if a.apply and changed:
        path.write_text(json.dumps(cfg, indent=2) + "\n")
    if found and (a.apply and changed):
        print("  Detected commands are a best guess: run each once before relying on the gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
