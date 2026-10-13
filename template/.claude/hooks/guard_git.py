#!/usr/bin/env python3
"""PreToolUse(Bash) guard: applies the git policy in harness.json (`git.guard`, `git.ops`).

Each git/gh operation maps to an op (stage, commit, push, pr, merge, tag, release, history,
destructive, skip_hooks) whose policy is allow | ask | block:
  allow -> run;  ask -> Claude Code asks the user to approve this exact command;  block -> refused.
Unparseable commands follow `git.on_unparseable`. This is a guardrail, not a sandbox.

Exit 0 (optionally with a JSON decision on stdout) or exit 2 (blocked, reason on stderr).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import sys

RANK = {"allow": 0, "ask": 1, "block": 2}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
WRAPPERS = {"command", "builtin", "exec", "nohup", "time", "sudo", "doas", "env", "xargs", "nice", "timeout", "caffeinate"}
GIT_OPT_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env", "--super-prefix"}
SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")", "\n", ";;", "|&"}


def load_policy() -> tuple[dict, str | None]:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    sys.path.insert(0, str(pathlib.Path(root) / ".claude/harness/scripts"))
    try:
        from hconfig import BASE, load  # type: ignore
    except ImportError:
        return {"guard": "enforce", "on_unparseable": "block", "ops": {}}, "hconfig.py not found; using strict fallback"
    try:
        return load(pathlib.Path(root))["git"], None
    except Exception as e:  # malformed config must not disable the guard
        return BASE["git"], f"config error ({e}); using standard git policy"


def tokens(cmd: str) -> list[str]:
    lex = shlex.shlex(cmd, posix=True, punctuation_chars="();<>|&\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def segments(toks: list[str]) -> list[list[str]]:
    out, cur = [], []
    for t in toks:
        if t in SEPARATORS or (t and set(t) <= set("();<>|&\n")):
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def nested(tok: str) -> list[str]:
    """Command text hidden inside $(...) or backticks within a single token."""
    found = re.findall(r"`([^`]*)`", tok)
    i = 0
    while (i := tok.find("$(", i)) != -1:
        depth, j = 0, i + 1
        while j < len(tok):
            depth += tok[j] == "("
            depth -= tok[j] == ")"
            if depth == 0:
                break
            j += 1
        found.append(tok[i + 2:j])
        i = j
    return found


def classify_git(args: list[str]) -> list[tuple[str, str]]:
    ops: list[tuple[str, str]] = []
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a == "-c" and i + 1 < len(args) and args[i + 1].lower().startswith("core.hookspath"):
            ops.append(("skip_hooks", "overrides core.hooksPath"))
        i += 2 if a in GIT_OPT_WITH_ARG else 1
    if i >= len(args):
        return ops
    sub, rest = args[i], args[i + 1:]
    flags = set(rest)
    has = lambda *xs: any(x in flags or any(r.startswith(x + "=") for r in rest) for x in xs)

    if "--no-verify" in flags or (sub == "commit" and "-n" in flags):
        ops.append(("skip_hooks", "--no-verify"))
    if sub in ("add", "stage", "rm", "mv", "update-index"):
        ops.append(("stage", sub))
    elif sub == "commit":
        ops.append(("history", "commit --amend") if has("--amend") else ("commit", "commit"))
    elif sub in ("cherry-pick", "revert", "am"):
        ops.append(("commit", sub))
    elif sub == "push":
        forced = has("--force", "-f", "--force-with-lease", "--mirror", "--delete", "-d", "--prune") or \
            any(r.startswith("+") or r.startswith(":") for r in rest if not r.startswith("-"))
        ops.append(("history", "force/delete push") if forced else ("push", "push"))
    elif sub in ("merge", "pull"):
        ops.append(("merge", sub))
    elif sub in ("rebase", "filter-branch", "filter-repo", "replace"):
        ops.append(("history", sub))
    elif sub == "tag":
        listing = not rest or has("-l", "--list", "-v", "--verify", "--contains", "--points-at")
        if not listing:
            ops.append(("tag", "tag"))
    elif sub == "reset":
        if has("--hard", "--merge", "--keep"):
            ops.append(("destructive", "reset --hard"))
        elif has("--soft") or any(re.match(r"^(HEAD)?[~^]|^HEAD[~^@]|^[0-9a-f]{7,40}$", r) for r in rest):
            ops.append(("history", "reset to another commit"))
        else:
            ops.append(("stage", "reset (unstage)"))
    elif sub == "clean" and any(re.match(r"^-[a-zA-Z]*f", r) or r == "--force" for r in rest):
        ops.append(("destructive", "clean -f"))
    elif sub == "checkout" and ("--" in flags or "." in flags or has("-f", "--force")):
        ops.append(("destructive", "checkout discarding changes"))
    elif sub == "restore":
        ops.append(("stage", "restore --staged") if has("--staged", "-S") and not has("--worktree", "-W")
                   else ("destructive", "restore working tree"))
    elif sub == "switch" and has("--discard-changes", "-f", "--force"):
        ops.append(("destructive", "switch --discard-changes"))
    elif sub == "stash" and rest and rest[0] in ("drop", "clear"):
        ops.append(("destructive", f"stash {rest[0]}"))
    elif sub == "branch" and (has("-D") or (has("-d", "--delete") and has("-f", "--force"))):
        ops.append(("destructive", "branch -D"))
    elif sub == "branch" and has("-f", "--force", "-M", "-C"):
        ops.append(("history", "branch force-move"))
    elif sub == "worktree" and rest[:1] == ["remove"]:
        ops.append(("destructive", "worktree remove"))
    elif sub == "update-ref":
        ops.append(("history", "update-ref"))
    elif sub in ("gc", "prune") or (sub == "reflog" and rest[:1] in (["expire"], ["delete"])):
        ops.append(("destructive", f"{sub} {' '.join(rest[:1])}".strip()))
    elif sub == "config" and any(r.lower() == "core.hookspath" for r in rest) and len(rest) >= 2 \
            and not has("--get", "--list", "-l", "--get-all"):
        ops.append(("skip_hooks", "changes core.hooksPath"))
    return ops


def classify_gh(args: list[str]) -> list[tuple[str, str]]:
    if len(args) >= 2 and args[0] == "pr":
        if args[1] == "merge":
            return [("merge", "gh pr merge")]
        if args[1] in ("create", "close", "edit", "ready", "reopen", "review", "comment"):
            return [("pr", f"gh pr {args[1]}")]
    if len(args) >= 2 and args[0] == "release" and args[1] not in ("list", "view", "download"):
        return [("release", f"gh release {args[1]}")]
    if args[:1] == ["api"]:
        method = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-X", "--method")), "GET")
        writes = method.upper() != "GET" or any(a in ("-f", "-F", "--field", "--raw-field", "--input") for a in args)
        if writes:
            return [("pr", "gh api write")]
    return []


def analyse(cmd: str, depth: int = 0) -> list[tuple[str, str]]:
    if depth > 4:
        raise ValueError("nesting too deep")
    ops: list[tuple[str, str]] = []
    for inner in nested(cmd):  # substitutions anywhere in the raw text (backticks survive tokenising badly)
        if inner.strip() and inner != cmd:
            ops += analyse(inner, depth + 1)
    for seg in segments(tokens(cmd)):
        for t in seg:
            for inner in nested(t):
                ops += analyse(inner, depth + 1)
        i = 0
        while i < len(seg) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[i]) or seg[i] in WRAPPERS
                                or (i > 0 and seg[i - 1] in WRAPPERS and seg[i].startswith("-"))):
            i += 1
        if i >= len(seg):
            continue
        prog, args = pathlib.PurePath(seg[i]).name, seg[i + 1:]
        if prog in SHELLS and "-c" in args[:-1]:
            ops += analyse(args[args.index("-c") + 1], depth + 1)
        elif prog == "eval":
            ops += analyse(" ".join(args), depth + 1)
        elif prog == "git":
            ops += classify_git(args)
        elif prog == "gh":
            ops += classify_gh(args)
    return ops


def main() -> int:
    policy, note = load_policy()
    mode = policy.get("guard", "enforce")
    if mode == "off":
        return 0
    try:
        payload = json.load(sys.stdin)
        cmd = payload.get("tool_input", {}).get("command", "")
        found = analyse(cmd) if cmd else []
        decision = max((policy.get("ops", {}).get(op, "block") for op, _ in found), key=RANK.get, default="allow")
        why = "; ".join(f"{op} ({what})" for op, what in found)
    except Exception as e:  # unparseable input: never silently allow
        decision, why = policy.get("on_unparseable", "block"), f"could not parse command ({e.__class__.__name__})"
    if note:
        why = f"{why} [{note}]"
    if decision == "allow":
        return 0
    if mode == "warn":
        print(json.dumps({"systemMessage": f"harness guard (warn mode) would {decision}: {why}"}))
        return 0
    if decision == "ask":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "ask",
            "permissionDecisionReason": f"harness git policy: {why}. Approve only if you asked for this."}}))
        return 0
    print(f"Blocked by harness git policy: {why}.\n"
          "Draft the change with /wf-commit and stop; a maintainer runs it, or changes git.ops in "
          ".claude/harness/harness.json.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
