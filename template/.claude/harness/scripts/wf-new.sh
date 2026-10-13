#!/usr/bin/env bash
# Start a work item: branch + worktree + .work/<slug>/ from templates.
# Usage: wf-new.sh <slug> "<one-line brief>" [--type feat|fix|chore|refactor|docs] [--here]
#   --here   use the current checkout instead of a new worktree
set -euo pipefail
usage() { echo "usage: wf-new.sh <slug> \"<one-line brief>\" [--type feat|fix|chore|refactor|docs] [--here]" >&2; exit 3; }
[[ $# -ge 2 ]] || usage
slug="$1"; brief="$2"; shift 2
type="feat"; here=0
while [[ $# -gt 0 ]]; do case "$1" in
  --type) type="$2"; shift 2;; --here) here=1; shift;;
  *) echo "unknown arg: $1" >&2; usage;; esac; done
[[ "$slug" =~ ^[a-z0-9][a-z0-9-]{1,40}$ ]] || { echo "slug must be kebab-case, 2-41 chars" >&2; exit 3; }
[[ -n "$brief" ]] || usage

root="$(git rev-parse --show-toplevel)"
cfg="$root/.claude/harness/harness.json"
H="$root/.claude/harness/scripts"
[[ -f "$cfg" ]] || { echo "harness not installed (no $cfg)." >&2; exit 3; }
work_dir="$(python3 "$H/hconfig.py" work_dir)"; default_branch="$(python3 "$H/hconfig.py" default_branch)"
mode="$(python3 "$H/hconfig.py" mode)"
if [[ "$mode" == tracked ]]; then
  git -C "$root" ls-files --error-unmatch .claude/harness/harness.json >/dev/null 2>&1 \
    || { echo "harness files are not committed; worktrees would not see them. Commit them first (or install with --mode local)." >&2; exit 3; }
fi

# Local mode: excluded files do not exist in new worktrees, so copy the harness in and share .work.
sync_local_harness() {
  local src="$1" dst="$2" entry p
  while IFS= read -r entry; do
    [[ -z "$entry" || "$entry" == \#* || "$entry" == ".work" ]] && continue
    entry="${entry%/}"
    for p in $(cd "$src" && compgen -G "$entry" || true); do
      mkdir -p "$dst/$(dirname "$p")"; rm -rf "${dst:?}/$p"; cp -R "$src/$p" "$dst/$p"
    done
  done < "$src/.claude/harness/local-paths.txt"
  [[ -e "$dst/$work_dir" ]] || ln -s "$(cd "$src/$work_dir" && pwd -P)" "$dst/$work_dir"
}

# Tracked mode: base on origin/<default> only if it already contains the harness; otherwise the local branch.
branch="$type/$slug"
base_ref="$default_branch"
if git -C "$root" remote get-url origin >/dev/null 2>&1 && git -C "$root" fetch --quiet origin "$default_branch" 2>/dev/null; then
  if [[ "$mode" == local ]] || git -C "$root" cat-file -e "origin/$default_branch:.claude/harness/harness.json" 2>/dev/null; then
    base_ref="origin/$default_branch"
  else
    echo "note: origin/$default_branch has no harness yet (not pushed?); basing on local $default_branch" >&2
  fi
fi
git -C "$root" rev-parse --verify --quiet "$base_ref^{commit}" >/dev/null || { echo "base '$base_ref' not found" >&2; exit 3; }
if [[ "$mode" == tracked ]]; then
  git -C "$root" cat-file -e "$base_ref:.claude/harness/harness.json" 2>/dev/null \
    || { echo "base '$base_ref' does not contain the harness; commit it on $default_branch first" >&2; exit 3; }
fi

created_branch=0; created_dir=""
cleanup() {
  [[ -n "$created_dir" ]] && git -C "$root" worktree remove --force "$created_dir" 2>/dev/null
  [[ $created_branch -eq 1 && $here -eq 0 ]] && git -C "$root" branch -D "$branch" >/dev/null 2>&1
  echo "wf-new: failed; rolled back branch/worktree" >&2
}
trap cleanup ERR

if [[ $here -eq 1 ]]; then
  dir="$root"; git -C "$root" switch -c "$branch" "$base_ref"
else
  dir="$(dirname "$root")/$(basename "$root").worktrees/$slug"
  git -C "$root" worktree add -b "$branch" "$dir" "$base_ref"; created_branch=1; created_dir="$dir"
  [[ "$mode" == local ]] && sync_local_harness "$root" "$dir"
fi
base_sha="$(git -C "$dir" rev-parse HEAD)"
w="$dir/$work_dir/$slug"; mkdir -p "$w/40-reviews" "$w/repros"
today="$(date -u +%Y-%m-%d)"
for f in 00-brief.md 10-investigation.md 20-spec.md 30-build-log.md; do
  python3 - "$dir/.claude/harness/templates/$f" "$w/$f" "$slug" "$today" "$branch" "$base_sha" "$brief" << "PY"
import sys
src, dst, slug, date, branch, base, brief = sys.argv[1:]
t = open(src).read()
for k, v in {"SLUG": slug, "DATE": date, "BRANCH": branch, "BASE": base, "BRIEF": brief}.items():
    t = t.replace("{{" + k + "}}", v)
open(dst, "w").write(t)
PY
done
( cd "$dir" && python3 .claude/harness/scripts/wf-state.py "$slug" set \
    slug="$slug" branch="$branch" base="$base_sha" phase=new review_round=0 created="$today" worktree="$dir" )
trap - ERR

cat << MSG
Work item ready: $slug
  branch   : $branch   (base $base_ref @ ${base_sha:0:10})
  worktree : $dir
  artifacts: $w

Next (fresh session):
  cd "$dir" && claude
  /wf-investigate $slug
MSG
