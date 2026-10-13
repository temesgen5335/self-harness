#!/usr/bin/env bash
# One-shot onboarding: preflight checks, fetch a pinned harness version, install into the current repo.
#
#   Recommended (pinned to an exact commit you have reviewed):
#   curl -fsSL https://raw.githubusercontent.com/temesgen5335/harness/<sha>/bootstrap.sh \
#     | bash -s -- --ref v0.1.0 --sha <sha> [install.sh options]
#
# Or from a local clone:  ~/dev/harness/bootstrap.sh --ref v0.1.0
#
# Options (bootstrap): --ref <tag|branch|sha>   version to install (default: latest tag, else main)
#                      --sha <40-char sha>      refuse to install unless --ref resolves to exactly this commit
#                      --repo <git url>         harness source (default: $HARNESS_REPO or GitHub)
#                      --target <dir>           project root (default: current git repo)
# Everything else is passed to install.sh (--mode tracked|local, --profile, --lead, --collaborator,
# --release-type, --default-branch, --no-release, --with-release, --no-agents-md, --force).
set -euo pipefail

HARNESS_REPO="${HARNESS_REPO:-https://github.com/temesgen5335/harness.git}"
HARNESS_HOME="${HARNESS_HOME:-$HOME/.local/share/claude-harness}"
ref=""; sha=""; target=""; pass=()
while [[ $# -gt 0 ]]; do case "$1" in
  --ref) ref="$2"; shift 2;; --sha) sha="$2"; shift 2;; --repo) HARNESS_REPO="$2"; shift 2;;
  --target) target="$2"; shift 2;; *) pass+=("$1"); shift;; esac; done

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf 'bootstrap: %s\n' "$*" >&2; exit 1; }

say "1/4 Preflight"
missing=()
for c in git python3; do command -v "$c" >/dev/null || missing+=("$c"); done
((${#missing[@]})) && fail "missing required tools: ${missing[*]}"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' || fail "python3 >= 3.8 required"
command -v claude >/dev/null || echo "  warn: Claude Code CLI not found (needed to use the harness, not to install it)"
command -v gh     >/dev/null || echo "  warn: gh CLI not found (needed only for /wf-release)"
target="${target:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[[ -n "$target" ]] || fail "run inside a git repo, or pass --target <repo root>"
git -C "$target" rev-parse HEAD >/dev/null 2>&1 || fail "$target has no commits yet; make an initial commit first"
if [[ -n "$(git -C "$target" status --porcelain)" ]]; then
  echo "  warn: $target has uncommitted changes; the installer will add files alongside them"
fi
echo "  target: $target"

say "2/4 Fetch harness"
if [[ -d "$HARNESS_HOME/.git" ]]; then
  git -C "$HARNESS_HOME" fetch --quiet --tags --force origin
else
  git clone --quiet "$HARNESS_REPO" "$HARNESS_HOME"
fi
if [[ -z "$ref" ]]; then
  ref="$(git -C "$HARNESS_HOME" tag --sort=-v:refname | head -1)"
  ref="${ref:-origin/main}"
fi
git -C "$HARNESS_HOME" -c advice.detachedHead=false checkout --quiet "$ref" || fail "unknown ref: $ref"
resolved="$(git -C "$HARNESS_HOME" rev-parse HEAD)"
if [[ -n "$sha" ]]; then
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || fail "--sha must be a full 40-character commit sha"
  [[ "$resolved" == "$sha" ]] || fail "ref $ref resolves to $resolved, expected $sha (tag moved or wrong ref); not installing"
  echo "  sha verified: $sha"
else
  echo "  note: not pinned by sha; to pin this exact version next time use --sha $resolved"
fi
echo "  harness $ref ($resolved) from $HARNESS_REPO"

say "3/4 Install"
installed=""
[[ -f "$target/.claude/harness/VERSION" ]] && installed="$(cat "$target/.claude/harness/VERSION")"
if [[ -n "$installed" && ! " ${pass[*]-} " =~ " --force " ]]; then
  echo "  existing install $installed found; adding --force to refresh harness-owned files (harness.json is kept)"
  pass+=("--force")
fi
"$HARNESS_HOME/install.sh" "$target" ${pass[@]+"${pass[@]}"}
printf '%s %s\n' "$ref" "$resolved" > "$target/.claude/harness/SOURCE_REF"

say "4/4 Verify"
ok=1
mode="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("mode","tracked"))' "$target/.claude/harness/harness.json")"
echo "  mode: $mode"
for f in .claude/harness/RULES.md .claude/harness/harness.json .claude/hooks/guard-git.sh \
         .claude/skills/wf-review/SKILL.md; do
  [[ -f "$target/$f" ]] || { echo "  missing $f"; ok=0; }
done
probe='{"tool_name":"Bash","tool_input":{"command":"git commit -m x"}}'
rc=0; out="$(cd "$target" && printf '%s' "$probe" | CLAUDE_PROJECT_DIR="$target" .claude/hooks/guard-git.sh 2>/dev/null)" || rc=$?
if [[ $rc -eq 2 ]]; then echo "  guard: commits blocked (draft-only policy): ok"
elif [[ "$out" == *'"ask"'* ]]; then echo "  guard: commits need explicit approval: ok"
else echo "  guard did NOT stop a commit (git.guard off/warn or commit=allow?)"; ok=0; fi
hp="$(git -C "$target" config --get core.hooksPath || true)"
gitdir="$(cd "$target" && cd "$(git rev-parse --git-common-dir)" && pwd)"
if [[ "$mode" == tracked && "$hp" == ".githooks" ]] || [[ "$mode" == local && -z "$hp" && -x "$gitdir/hooks/commit-msg" ]]; then
  echo "  commit-msg hook active: ok"
else echo "  warn: commit-msg hook inactive (see install output)"; fi
if [[ "$mode" == local ]]; then
  leaked="$(git -C "$target" status --porcelain --untracked-files=all -- .claude .work CLAUDE.md AGENTS.md .gitignore .githooks)"
  [[ -z "$leaked" ]] && echo "  no trace in git status: ok" || { echo "  visible in git status:"; echo "$leaked"; ok=0; }
fi
grep -q '"lint": ""' "$target/.claude/harness/harness.json" && \
  echo "  todo: fill commands in .claude/harness/harness.json (lint/typecheck/test/stress/build)"
((ok)) || fail "verification failed"
if [[ "$mode" == local ]]; then say "Done. Local mode: nothing to commit."; else say "Done. Review the diff, then commit it yourself."; fi
