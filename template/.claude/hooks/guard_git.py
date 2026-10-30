#!/usr/bin/env python3
"""PreToolUse(Bash) guard: applies the policy in harness.json (`git.guard`, `git.ops`) to git and gh
operations, and to three non-git risks: recursive deletes (destructive_fs), reading secret files (secrets)
and piping a download into a shell (remote_exec).

Each git/gh operation maps to an op (stage, commit, push, pr, merge, tag, release, history,
destructive, skip_hooks) whose policy is allow | ask | block:
  allow -> run;  ask -> Claude Code asks the user to approve this exact command;  block -> refused.
Unparseable commands follow `git.on_unparseable`. This is a guardrail, not a sandbox.
Committing also checks what is staged: secret files, and added lines that look like live credentials.

`git.guard: warn` turns decisions into reminders shown to the user and to Claude (with `git.notes` per op),
except ops listed in `git.always_enforce`, which keep their decision.

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
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "deno", "bun"}
# Files whose contents are credentials. Examples/templates of them are not.
SECRET_PATH = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|[\w.-]+\.(pem|key|p12|pfx)|id_(rsa|ed25519|ecdsa|dsa)|\.netrc|"
                         r"\.pgpass|credentials(\.json)?|\.aws/credentials|\.npmrc|\.pypirc)$")
SECRET_OK = re.compile(r"\.(example|sample|template|dist)$|\.pub$")
# Added lines that look like live credentials (high-confidence formats only). `pragma: allowlist secret` opts out.
SECRET_CONTENT = re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY|\bAKIA[0-9A-Z]{16}\b|"
                            r"\bgh[pousr]_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{40,}|\bxox[abprs]-[A-Za-z0-9-]{10,}|"
                            r"\bsk-(ant-|proj-)?[A-Za-z0-9_-]{32,}|\b[rs]k_live_[A-Za-z0-9]{20,}")
# Read, copy or execute a file: anything that would put its contents into the transcript or elsewhere.
READERS = {"cat", "less", "more", "head", "tail", "bat", "grep", "egrep", "rg", "ag", "sed", "awk", "cut", "sort",
           "strings", "xxd", "od", "base64", "cp", "scp", "rsync", "source", ".", "nl", "tac", "diff", "jq", "yq"}
REMOTE_EXEC = re.compile(r"\b(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(env\s+)?(ba|z|da|k|fi)?sh\b|"
                         r"\b(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(python3?|node|ruby|perl)\b|"
                         r"\b(ba|z)?sh\s+(-c\s+)?[\"']?\$\((curl|wget)\b|\b(ba|z)?sh\s+<\(\s*(curl|wget)\b")
# git invoked from inside interpreter code: subprocess lists or shell strings.
EMBEDDED_GIT = re.compile(r"""["']git["']\s*,\s*["']([a-z-]+)["']|\bgit\s+([a-z][a-z-]*)""")


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
        if sub in ("add", "stage"):
            ops += [("secrets", f"stages {r}") for r in rest if not r.startswith("-") and is_secret_path(r)]
            if has("-A", "--all") or "." in flags:
                ops += [("secrets", f"stages untracked {p}") for p in untracked_secrets()]
    elif sub == "commit":
        ops.append(("history", "commit --amend") if has("--amend") else ("commit", "commit"))
        ops += staged_secrets(all_tracked=has("-a", "--all") or any(re.match(r"^-[a-zA-Z]*a", r) for r in rest))
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


def git_out(*args: str) -> str:
    import subprocess
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


def untracked_secrets() -> list[str]:
    return [p for p in git_out("ls-files", "--others", "--exclude-standard").splitlines() if is_secret_path(p)]


def staged_secrets(all_tracked: bool = False) -> list[tuple[str, str]]:
    """Secret files and credential-looking added lines in what this commit would record."""
    diff_args = ("diff", "HEAD") if all_tracked else ("diff", "--cached")
    names = git_out(*diff_args, "--name-only", "--diff-filter=AM").splitlines()
    found = [("secrets", f"commits {p}") for p in names if is_secret_path(p)]
    path = ""
    for line in git_out(*diff_args, "--unified=0", "--diff-filter=AM").splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and SECRET_CONTENT.search(line) and "pragma: allowlist secret" not in line:
            found.append(("secrets", f"credential-like value added in {path}"))
    return found


def is_secret_path(tok: str) -> bool:
    tok = tok.split("=", 1)[-1]  # --file=.env
    return bool(SECRET_PATH.search(tok)) and not SECRET_OK.search(tok)


def classify_other(prog: str, args: list[str]) -> list[tuple[str, str]]:
    """Operations outside git that the guard still governs."""
    ops: list[tuple[str, str]] = []
    if prog == "rm" and any(re.match(r"^-[a-zA-Z]*[rR]", a) or a == "--recursive" for a in args):
        ops.append(("destructive_fs", "rm -r"))
    elif prog == "find" and "-delete" in args:
        ops.append(("destructive_fs", "find -delete"))
    if prog in READERS:
        hits = [a for a in args if not a.startswith("-") and is_secret_path(a)]
        if hits:
            ops.append(("secrets", f"{prog} {hits[0]}"))
    if prog in INTERPRETERS:
        code = next((args[args.index(f) + 1] for f in ("-c", "-e", "--eval") if f in args[:-1]), "")
        for m in EMBEDDED_GIT.finditer(code):
            sub = m.group(1) or m.group(2)
            ops += [(op, f"{what} (inside {prog} code)") for op, what in classify_git([sub])]
    return ops


def analyse(cmd: str, depth: int = 0) -> list[tuple[str, str]]:
    if depth > 4:
        raise ValueError("nesting too deep")
    ops: list[tuple[str, str]] = []
    if depth == 0 and REMOTE_EXEC.search(cmd):
        ops.append(("remote_exec", "downloaded script piped into a shell or interpreter"))
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
        else:
            ops += classify_other(prog, args)
    # `< .env`: a secret file redirected into any command (`<` splits segments, so check the token stream)
    toks = tokens(cmd)
    ops += [("secrets", f"< {t}") for j, t in enumerate(toks[1:], 1) if toks[j - 1] == "<" and is_secret_path(t)]
    return ops


def main() -> int:
    policy, note = load_policy()
    mode = policy.get("guard", "enforce")
    if mode == "off":
        return 0
    try:
        payload = json.load(sys.stdin)
        tool_input = payload.get("tool_input", {})
        if payload.get("tool_name") == "Read":  # Claude's file tool reading a secret file
            path = str(tool_input.get("file_path", ""))
            found = [("secrets", f"Read {path}")] if is_secret_path(path) else []
        else:
            cmd = tool_input.get("command", "")
            found = analyse(cmd) if cmd else []
        decision = max((policy.get("ops", {}).get(op, "block") for op, _ in found), key=RANK.get, default="allow")
        why = "; ".join(f"{op} ({what})" for op, what in found)
    except Exception as e:  # unparseable input: never silently allow
        decision, why = policy.get("on_unparseable", "block"), f"could not parse command ({e.__class__.__name__})"
    if note:
        why = f"{why} [{note}]"
    if mode == "warn":
        # Reminders for everything, except ops the project always enforces (e.g. reading secrets).
        enforced = set(policy.get("always_enforce", []))
        kept = [(op, what) for op, what in found if op in enforced]
        if decision != "allow":
            notes = policy.get("notes", {})
            tips = sorted({notes[op] for op, _ in found if op in notes and op not in enforced})
            msg = f"harness guard (warn mode) would {decision}: {why}"
            if tips:
                msg += "\nReminder: " + " ".join(tips)
            if not kept:
                print(json.dumps({"systemMessage": msg, "hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "additionalContext": msg +
                    "\nProceed only if the user asked for exactly this; otherwise stop and tell them."}}))
                return 0
        decision = max((policy.get("ops", {}).get(op, "block") for op, _ in kept), key=RANK.get, default="allow")
        why = "; ".join(f"{op} ({what})" for op, what in kept)
    if decision == "allow":
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
