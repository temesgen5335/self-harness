#!/usr/bin/env python3
"""Suggest the project's check commands (install, lint, typecheck, test, build) from its files.

Usage: detect-commands.py [--apply] [--redetect] [--replace KEY ...] [--set key=value ...]
  (no flags)       print what is configured, what was detected, and which configured commands cannot run here
  --apply          write harness.json: fill EMPTY commands with detected ones and apply --set values
  --redetect       with --apply, also replace a command that cannot run here when a replacement was detected
                   (install.sh --detect-commands); a command is never cleared this way
  --replace KEY    with --apply, KEY was just set by a preset rather than by you: replace it when it cannot run
                   here, or clear it when nothing was detected (install.sh passes these; repeatable)
  --set key=value  set a command explicitly (repeatable); wins over everything

It reads files only and never runs a project command. Detected commands are a best guess: run each once.
"Cannot run here" is said only when sure: the script it names is missing, its make target is not in the makefile
make would read (following -C, -f and includes), or its package.json script does not exist. Compound shell
commands, inline code and anything with variables are left alone. Sources, first match wins: Makefile targets,
package.json scripts, then Python (uv / poetry / pdm), Go and Rust conventions.
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


def makefile(root: pathlib.Path) -> pathlib.Path | None:
    """The file make reads by default: the first of GNUmakefile, makefile, Makefile."""
    for name in ("GNUmakefile", "makefile", "Makefile"):
        if (root / name).is_file():
            return root / name
    return None


def parse_make(path: pathlib.Path | None, seen=None) -> tuple:
    """(targets, certain). certain is False when targets may come from somewhere this cannot follow:
    variables or patterns in rule names, or an include that is missing or uses variables."""
    if path is None:
        return set(), True
    seen = seen if seen is not None else set()
    if path in seen:
        return set(), True
    seen.add(path)
    targets, certain = set(), True
    for line in read(path).splitlines():
        if line.startswith(("\t", "#")):
            continue
        inc = re.match(r"^-?include\s+(.+)", line)
        if inc:
            for name in inc.group(1).split():
                p = path.parent / name
                if "$" in name or "%" in name or not p.is_file():
                    certain = False
                else:
                    t, c = parse_make(p, seen)
                    targets |= t; certain = certain and c
            continue
        m = re.match(r"^([^:=#]+?)\s*::?(?!=)", line)
        if m and not line.startswith("."):
            names = m.group(1).split()
            if any("$" in n or "%" in n for n in names):
                certain = False
            targets.update(n for n in names if "$" not in n and "%" not in n)
    return targets, certain


def make_targets(root: pathlib.Path) -> set:
    return parse_make(makefile(root))[0]


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


def broken_make(root: pathlib.Path, args: list) -> str | None:
    """make [-C dir] [-f file] [other options] [VAR=value] target...; None when unsure."""
    directory, file, wanted, i = root, None, [], 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "--directory", "-f", "--file", "--makefile", "-I", "--include-dir", "-o", "-W"):
            if i + 1 >= len(args):
                return None
            if a in ("-C", "--directory"):
                directory = directory / args[i + 1]
            elif a in ("-f", "--file", "--makefile"):
                file = args[i + 1]
            i += 2
            continue
        if a.startswith(("--directory=", "--file=", "--makefile=")):
            key, _, val = a.partition("=")
            directory, file = (directory / val, file) if key == "--directory" else (directory, val)
        elif a.startswith("-C") and len(a) > 2:
            directory = directory / a[2:]
        elif a.startswith("-f") and len(a) > 2:
            file = a[2:]
        elif a.startswith("-") or "=" in a:
            if a in ("-j", "-l", "--jobs", "--load-average") and i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
        else:
            wanted.append(a)
        i += 1
    if "$" in str(directory) or (file and "$" in file) or any("$" in t for t in wanted):
        return None
    if not directory.is_dir():
        return f"directory {directory.relative_to(root) if directory != root else '.'} does not exist"
    path = (directory / file) if file else makefile(directory)
    if path is None or not path.is_file():
        return f"{file} does not exist" if file else "no Makefile"
    targets, certain = parse_make(path)
    missing = [t for t in wanted if t not in targets]
    return f"make target '{missing[0]}' does not exist" if missing and certain else None


def broken(root: pathlib.Path, cmd: str) -> str | None:
    """Why a configured command cannot run here, or None. Says broken only when sure; reads files only."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None
    if not tokens or any(t in ("&&", "||", ";", "|") for t in tokens):
        return None  # compound shell commands: too many ways to be right
    if tokens[0] == "make":
        return broken_make(root, tokens[1:])
    if tokens[0] in ("npm", "pnpm", "yarn", "bun") and "run" in tokens[1:2]:
        rest = [t for t in tokens[2:] if not t.startswith("-")]
        if not (root / "package.json").exists():
            return "no package.json"
        if not rest:
            return None
        return None if rest[0] in pkg_scripts(root) else f"package.json has no script '{rest[0]}'"
    if tokens[0] in ("bash", "sh", "zsh", "python", "python3", "node"):
        if any(t in ("-c", "-e", "-m", "--eval") for t in tokens[1:]):
            return None  # inline code or a module, not a file
        script = next((t for t in tokens[1:] if not t.startswith("-")), None)
    else:
        script = tokens[0] if "/" in tokens[0] else None
    if not script or "$" in script or "..." in script:
        return None
    path = pathlib.Path(script).expanduser()
    if not path.is_absolute():
        path = root / path
    return None if path.exists() else f"{script} does not exist"


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="detect-commands.py", description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--redetect", action="store_true")
    ap.add_argument("--replace", action="append", default=[], metavar="KEY")
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

    def put(key, value):
        if a.apply and cmds.get(key) != value:
            cmds[key] = value
            changed.append(key)

    for key in KEYS + ("stress",):
        cur = str(cmds.get(key, "")).strip()
        det = found.get(key)
        if key in explicit:
            print(f"  {key:<9} {explicit[key] or '(none)'}  <- set explicitly")
            put(key, explicit[key])
            continue
        if key == "stress":
            continue
        if not cur:
            print(f"  {key:<9} {det[0] + '  <- detected from ' + det[1] if det else '(none)'}")
            if det:
                put(key, det[0])
            continue
        bad = broken(root, cur)
        if not bad:
            print(f"  {key:<9} {cur}")
        elif key in a.replace and det:
            print(f"  {key:<9} {det[0]}  <- detected from {det[1]}; replaced the preset's '{cur}': {bad}")
            put(key, det[0])
        elif key in a.replace:
            print(f"  {key:<9} (none)  <- cleared the preset's '{cur}': {bad}; nothing detected")
            put(key, "")
        elif a.redetect and det:
            print(f"  {key:<9} {det[0]}  <- detected from {det[1]}; replaced '{cur}': {bad}")
            put(key, det[0])
        else:
            print(f"  {key:<9} {cur}  <- WARNING: {bad}; kept, fix it in harness.json"
                  + (f" (detected: {det[0]})" if det else ""))
    test_cmd = str((cmds if a.apply else {**cmds, **explicit}).get("test", "")).strip()
    if not test_cmd:
        print("  WARNING: no test command, so the gate will not require tests. Set one:\n"
              "           install.sh <repo> --command test='<your test command>'")
    if a.apply and changed:
        path.write_text(json.dumps(cfg, indent=2) + "\n")
        print("  Detected commands are a best guess: run each once before relying on the gate.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
