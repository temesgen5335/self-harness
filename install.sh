#!/usr/bin/env bash
# Install or update the harness in a project.
# Usage: install.sh <target-repo> [options]
#   --mode tracked|local              tracked (default): files are committed, the team shares the workflow.
#                                     local: leaves no trace in git — ignored via .git/info/exclude, settings in
#                                     settings.local.json, commit-msg hook in the git dir, .work shared across
#                                     worktrees in the git dir, CLAUDE.md/AGENTS.md/.gitignore untouched.
#                                     Fixed at first install; switch by running uninstall.sh first.
#   --profile strict|standard|light   initial profile (edit harness.json later)
#   --preset <name>                   merge presets/<name>.json into harness.json (e.g. tenacious); its
#                                     _install options set defaults such as --no-release
#   --lead "Name <email>"             team lead (default: git user.name/user.email of whoever runs this)
#   --collaborator "Name <email>"     add a collaborator (repeatable)
#   --default-branch <name>           default: origin/HEAD, else current branch, else main
#   --release-type python|node|simple|go|rust   (default: auto-detect)
#   --no-release | --with-release     release-please files (default: on in tracked mode, off in local mode)
#   --no-agents-md                    tracked mode: do not write the harness block into AGENTS.md
#   --force                           overwrite harness-owned files (skills, agents, hooks, scripts, rules).
#                                     Never overwrites harness.json; only flags you pass change it.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/template"
target="${1:-}"; shift || true
mode=""; rtype=""; branch=""; release=""; force=0; profile=""; lead=""; collabs=(); agents_md=1; preset=""
while [[ $# -gt 0 ]]; do case "$1" in
  --mode) mode="$2"; shift 2;;
  --release-type) rtype="$2"; shift 2;; --default-branch) branch="$2"; shift 2;;
  --profile) profile="$2"; shift 2;; --lead) lead="$2"; shift 2;; --preset) preset="$2"; shift 2;;
  --collaborator) collabs+=("$2"); shift 2;; --no-agents-md) agents_md=0; shift;;
  --no-release) release=0; shift;; --with-release) release=1; shift;; --force) force=1; shift;;
  *) echo "unknown arg: $1" >&2; exit 3;; esac; done
[[ -z "$mode" || "$mode" == tracked || "$mode" == local ]] || { echo "--mode must be tracked or local" >&2; exit 3; }
[[ -n "$target" && ( -d "$target/.git" || -f "$target/.git" ) ]] || { echo "target must be a git repo root" >&2; exit 3; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 3; }
preset_file=""
if [[ -n "$preset" ]]; then
  preset_file="$(dirname "$SRC")/presets/$preset.json"
  [[ -f "$preset_file" ]] || { echo "unknown preset: $preset (see presets/)" >&2; exit 3; }
  if [[ -z "$release" ]]; then
    release="$(python3 -c 'import json,sys; r=json.load(open(sys.argv[1])).get("_install",{}).get("release"); print("" if r is None else int(r))' "$preset_file")"
  fi
fi
cd "$target"
common="$(cd "$(git rev-parse --git-common-dir)" && pwd)"

fresh=1; [[ -e .claude/harness/harness.json ]] && fresh=0
if [[ $fresh -eq 0 ]]; then
  existing="$(python3 -c 'import json;print(json.load(open(".claude/harness/harness.json")).get("mode","tracked"))' 2>/dev/null || echo tracked)"
  if [[ -n "$mode" && "$mode" != "$existing" ]]; then
    echo "harness is installed in $existing mode; run uninstall.sh first to switch to $mode" >&2; exit 3
  fi
  mode="$existing"
fi
mode="${mode:-tracked}"
[[ -z "$release" ]] && { [[ $mode == local ]] && release=0 || release=1; }
if [[ -z "$branch" && $fresh -eq 1 ]]; then
  branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')" || true
  branch="${branch:-$(git branch --show-current 2>/dev/null)}"; branch="${branch:-main}"
fi
if [[ -z "$lead" && $fresh -eq 1 ]]; then
  n="$(git config user.name || true)"; e="$(git config user.email || true)"
  [[ -n "$n$e" ]] && lead="$n <$e>"
fi

copy() { # copy <src> <dst> : respects --force
  if [[ -e "$2" && $force -eq 0 ]]; then echo "  keep  $2"; else mkdir -p "$(dirname "$2")"; cp "$1" "$2"; echo "  write $2"; fi
}

echo "Harness files ($mode mode)"
while IFS= read -r f; do
  rel="${f#"$SRC"/}"
  case "$rel" in
    release/*|.claude/settings.json|AGENTS.block.md) continue;;
    .githooks/*) [[ $mode == local ]] && continue;;
    .claude/harness/harness.json) [[ -e "$rel" ]] && { echo "  keep  $rel (project config)"; continue; } ;;
  esac
  copy "$f" "$rel"
done < <(find "$SRC" -type f ! -path "$SRC/release/*" ! -name '*.pyc' ! -name '.DS_Store' ! -path '*/__pycache__/*')
chmod +x .claude/hooks/*.sh .claude/hooks/*.py .claude/harness/scripts/*

echo "harness.json"
python3 - "$branch" "$profile" "$lead" "$mode" "$preset_file" "${collabs[@]+"${collabs[@]}"}" << 'PY'
import json, re, sys
branch, profile, lead, mode, preset_file, *collabs = sys.argv[1:]
p = ".claude/harness/harness.json"; c = json.load(open(p))
def person(s):
    m = re.match(r"^\s*(.*?)\s*<([^>]*)>\s*$", s)
    return {"name": m.group(1), "email": m.group(2)} if m else {"name": s.strip(), "email": ""}
changed = []
def merge(base, over):
    for k, v in over.items():
        base[k] = merge(base.get(k, {}), v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base
if preset_file:
    pre = {k: v for k, v in json.load(open(preset_file)).items() if not k.startswith("_")}
    merge(c, pre); changed.append(f"preset={preset_file.rsplit('/', 1)[-1][:-5]}")
if c.get("mode") != mode: c["mode"] = mode; changed.append(f"mode={mode}")
if branch: c["default_branch"] = branch; changed.append(f"default_branch={branch}")
if profile:
    if profile not in ("strict", "standard", "light"): sys.exit(f"unknown profile: {profile}")
    c["profile"] = profile; changed.append(f"profile={profile}")
team = c.setdefault("team", {"lead": {"name": "", "email": ""}, "collaborators": []})
if lead: team["lead"] = person(lead); changed.append(f"lead={lead}")
for s in collabs:
    who = person(s)
    if who not in team.setdefault("collaborators", []):
        team["collaborators"].append(who); changed.append(f"collaborator={s}")
open(p, "w").write(json.dumps(c, indent=2) + "\n")
print("  " + (", ".join(changed) if changed else "unchanged"))
PY

settings=".claude/settings.json"; [[ $mode == local ]] && settings=".claude/settings.local.json"
echo "Claude settings (merge into $settings)"
python3 - "$SRC/.claude/settings.json" "$settings" << 'PY'
import json, os, sys
src = json.load(open(sys.argv[1])); dst_p = sys.argv[2]
dst = json.load(open(dst_p)) if os.path.exists(dst_p) else {}
dst.setdefault("$schema", src["$schema"])
dst["attribution"] = src["attribution"]
hooks = dst.setdefault("hooks", {})
for event, entries in src["hooks"].items():
    cur = hooks.setdefault(event, [])
    for e in entries:
        cmds = {h.get("command") for h in e["hooks"]}
        mine = [c for c in cur if cmds & {h.get("command") for h in c.get("hooks", [])}]
        if not mine:
            cur.append(e)
        elif "matcher" in e:
            for c in mine:  # an upgrade may widen what a harness hook covers (e.g. Bash -> Bash|Read)
                c["matcher"] = e["matcher"]
os.makedirs(".claude", exist_ok=True)
open(dst_p, "w").write(json.dumps(dst, indent=2) + "\n")
print("  merged", dst_p)
PY

if [[ $mode == tracked ]]; then
  echo "CLAUDE.md"
  if ! grep -qs '@.claude/harness/RULES.md' CLAUDE.md; then
    printf '\n## Way of work\n@.claude/harness/RULES.md\n' >> CLAUDE.md; echo "  import added"
  else echo "  import present"; fi

  if [[ $agents_md -eq 1 ]]; then
    echo "AGENTS.md (managed block)"
    python3 - "$SRC/AGENTS.block.md" << 'PY'
import pathlib, re, sys
block = pathlib.Path(sys.argv[1]).read_text().strip()
p = pathlib.Path("AGENTS.md"); text = p.read_text() if p.exists() else ""
begin, end = "<!-- harness:begin -->", "<!-- harness:end -->"
managed = f"{begin}\n{block}\n{end}"
if begin in text and end in text:
    text = re.sub(re.escape(begin) + r".*?" + re.escape(end), lambda _: managed, text, flags=re.S); action = "updated"
else:
    text = (text.rstrip() + "\n\n" if text.strip() else "") + managed + "\n"; action = "added"
p.write_text(text); print(f"  {action}")
PY
  fi

  echo "Git hooks"
  chmod +x .githooks/commit-msg
  cur="$(git config --get core.hooksPath || true)"
  if [[ -z "$cur" || "$cur" == ".githooks" ]]; then git config core.hooksPath .githooks; echo "  core.hooksPath=.githooks"
  else echo "  WARNING: core.hooksPath is '$cur'; call .githooks/commit-msg from your hook manager yourself"; fi

  echo ".gitignore"
  for line in ".work/*/state.json" ".claude/settings.local.json" "__pycache__/"; do
    grep -qxF "$line" .gitignore 2>/dev/null || { echo "$line" >> .gitignore; echo "  + $line"; }
  done
else
  echo "Rules: injected by the SessionStart hook (CLAUDE.md, AGENTS.md and .gitignore untouched)"

  echo "Git hooks (local, in the git dir, shared by all worktrees)"
  cur="$(git config --get core.hooksPath || true)"
  hook="$common/hooks/commit-msg"
  if [[ -n "$cur" ]]; then
    echo "  WARNING: core.hooksPath is '$cur'; chain $SRC/.githooks/commit-msg into that hook manager yourself"
  elif [[ -e "$hook" ]] && ! grep -q 'Enforce Conventional Commits' "$hook"; then
    echo "  WARNING: existing $hook kept; chain $SRC/.githooks/commit-msg into it yourself"
  else
    mkdir -p "$common/hooks"; cp "$SRC/.githooks/commit-msg" "$hook"; chmod +x "$hook"; echo "  write $hook"
  fi

  echo "Work artifacts (in the git dir, shared by all worktrees, never pushed)"
  mkdir -p "$common/harness-work"
  if [[ -L .work ]]; then echo "  .work -> $(readlink .work)"
  elif [[ -e .work ]]; then echo "  WARNING: .work exists and is not a symlink; left as is"
  else ln -s "$common/harness-work" .work; echo "  .work -> $common/harness-work"; fi

  echo "Local excludes ($common/info/exclude)"
  python3 - "$common/info/exclude" ".claude/harness/local-paths.txt" << 'PY'
import pathlib, sys
p, paths = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
entries = [l.strip() for l in paths.read_text().splitlines() if l.strip() and not l.startswith("#")]
block = "# >>> claude-harness (local mode)\n" + "".join(f"/{e}\n" for e in entries) + "# <<< claude-harness\n"
p.parent.mkdir(parents=True, exist_ok=True)
t = p.read_text() if p.exists() else ""
if "# >>> claude-harness" in t and "# <<< claude-harness" in t:
    start, end = t.index("# >>> claude-harness"), t.index("# <<< claude-harness") + len("# <<< claude-harness\n")
    t = t[:start] + block + t[end:]
else:
    t = t + ("" if t.endswith("\n") or not t else "\n") + block
p.write_text(t); print("  exclude block written")
PY
fi

if [[ $release -eq 1 ]]; then
  echo "release-please (these files must be tracked: GitHub only runs committed workflows)"
  if [[ -z "$rtype" ]]; then
    if [[ -f pyproject.toml ]]; then rtype=python; elif [[ -f package.json ]]; then rtype=node; else rtype=simple; fi
  fi
  rbranch="$(python3 -c 'import json;print(json.load(open(".claude/harness/harness.json")).get("default_branch","main"))')"
  python3 - "$SRC/release" "$rtype" "$rbranch" << 'PY'
import json, os, re, sys
src, rtype, branch = sys.argv[1:]
v = None
if os.path.exists("package.json"):
    v = json.load(open("package.json")).get("version")
if not v and os.path.exists("pyproject.toml"):
    m = re.search(r'^version\s*=\s*"([^"]+)"', open("pyproject.toml").read(), re.M); v = m and m.group(1)
subs = {"__RELEASE_TYPE__": rtype, "__VERSION__": v or "0.0.0", "__DEFAULT_BRANCH__": branch}
for f in ("release-please-config.json", ".release-please-manifest.json",
          ".github/workflows/release-please.yml", ".github/workflows/pr-title.yml"):
    if os.path.exists(f):
        print(f"  keep  {f}"); continue
    t = open(os.path.join(src, f)).read()
    for k, val in subs.items():
        t = t.replace(k, val)
    os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
    open(f, "w").write(t); print(f"  write {f}")
print(f"  release-type={rtype} current-version={v or '0.0.0'}")
PY
fi

echo
echo "Installed harness $(cat .claude/harness/VERSION) in $mode mode · effective config: python3 .claude/harness/scripts/hconfig.py"
if [[ -n "$preset_file" ]]; then
  while IFS= read -r p; do
    [[ -e "$p" ]] || echo "WARNING: preset '$preset' expects $p, which this repo lacks; adopt the project template or edit harness.json."
  done < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1])).get("_install",{}).get("expects",[])))' "$preset_file")
fi
echo "Next:"
echo "  1. Fill .claude/harness/harness.json \"commands\" (lint, typecheck, test, stress, build) and gate.critical_paths;"
echo "     check \"team\" and \"profile\" (strict | standard | light)."
if [[ $mode == tracked ]]; then
  echo "  2. Review and commit the harness files yourself (worktrees only see committed files), then push:"
  echo "       git add .claude .githooks CLAUDE.md AGENTS.md .gitignore release-please-config.json .release-please-manifest.json .github"
  echo "       git commit -m \"build(harness): add planning, review and release workflow\""
  echo "  3. GitHub: Settings > Actions > General > allow Actions to create pull requests; prefer squash merges."
else
  echo "  2. Nothing to commit: 'git status' shows no harness files$([[ $release -eq 1 ]] && echo ' except the release-please files')."
  echo "     Create worktrees with wf-new.sh (it copies the harness in). Remove everything with uninstall.sh."
fi
echo "  Start work:  .claude/harness/scripts/wf-new.sh <slug> \"<one-line brief>\""
