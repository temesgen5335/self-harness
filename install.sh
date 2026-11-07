#!/usr/bin/env bash
# Install or update the harness in a project.
# Usage: install.sh <target-repo> [options]
#   --mode tracked|local              tracked (default): files are committed, the team shares the workflow.
#                                     local: leaves no trace in git — ignored via .git/info/exclude, settings in
#                                     settings.local.json, commit-msg hook in the git dir, .work shared across
#                                     worktrees in the git dir, CLAUDE.md/.gitignore untouched; an AGENTS.md for
#                                     other agents only when the repo has none (kept out of git too).
#                                     Fixed at first install; switch by running uninstall.sh first.
#   --profile strict|standard|light|guided   initial profile (edit harness.json later)
#   --preset <name>                   merge presets/local/<name>.json (private, gitignored) or presets/<name>.json
#                                     into harness.json once, recorded as "preset"; its _install options set
#                                     defaults such as --no-release
#   --command key=value               set a check command (install, lint, typecheck, test, stress, build); repeatable
#   --detect-commands                 re-detect commands from the repo's files: fill empty ones and replace ones
#                                     that cannot run here when a replacement is found (fresh installs and newly
#                                     applied presets fill empty ones and fix the preset's own commands)
#   --lead "Name <email>"             team lead (default: git user.name/user.email of whoever runs this)
#   --collaborator "Name <email>"     add a collaborator (repeatable)
#   --default-branch <name>           default: origin/HEAD, else current branch, else main
#   --release-type python|node|simple|go|rust   (default: auto-detect)
#   --no-release | --with-release     release-please files (default: on in tracked mode, off in local mode)
#   --no-agents-md                    do not write the harness block into AGENTS.md (local mode: do not create one)
#   --force                           overwrite harness-owned files (skills, agents, hooks, scripts, rules).
#                                     Never overwrites harness.json; only flags you pass change it.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/template"
target="${1:-}"; shift || true
mode=""; rtype=""; branch=""; release=""; force=0; profile=""; lead=""; collabs=(); agents_md=1; preset=""
commands=(); detect=0
while [[ $# -gt 0 ]]; do case "$1" in
  --mode) mode="$2"; shift 2;;
  --release-type) rtype="$2"; shift 2;; --default-branch) branch="$2"; shift 2;;
  --profile) profile="$2"; shift 2;; --lead) lead="$2"; shift 2;; --preset) preset="$2"; shift 2;;
  --collaborator) collabs+=("$2"); shift 2;; --no-agents-md) agents_md=0; shift;;
  --command) commands+=("--set" "$2"); shift 2;; --detect-commands) detect=1; shift;;
  --no-release) release=0; shift;; --with-release) release=1; shift;; --force) force=1; shift;;
  *) echo "unknown arg: $1" >&2; exit 3;; esac; done
[[ -z "$mode" || "$mode" == tracked || "$mode" == local ]] || { echo "--mode must be tracked or local" >&2; exit 3; }
[[ -n "$target" && ( -d "$target/.git" || -f "$target/.git" ) ]] || { echo "target must be a git repo root" >&2; exit 3; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 3; }
preset_file=""
if [[ -n "$preset" ]]; then
  [[ "$preset" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "invalid preset name: $preset" >&2; exit 3; }
  for d in presets/local presets; do
    [[ -f "$(dirname "$SRC")/$d/$preset.json" ]] && { preset_file="$(dirname "$SRC")/$d/$preset.json"; break; }
  done
  [[ -n "$preset_file" ]] || { echo "unknown preset: $preset (see presets/ and presets/local/)" >&2; exit 3; }
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

# A preset applied by this run may name commands this repo lacks; those are replaced by detected ones.
preset_new=0
if [[ -n "$preset_file" ]]; then
  had="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("preset",""))' .claude/harness/harness.json 2>/dev/null || true)"
  [[ "$had" == "$preset" ]] || preset_new=1
fi
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
def leaves(d, pre=""):
    for k, v in d.items():
        yield from leaves(v, f"{pre}{k}.") if isinstance(v, dict) else [(f"{pre}{k}", v)]
if preset_file:
    name = preset_file.rsplit("/", 1)[-1][:-5]
    if c.get("preset") == name:
        # Applied once; re-applying would overwrite whatever the project has changed since.
        changed.append(f"preset {name} already applied, not re-applied (edit harness.json)")
    else:
        pre = {k: v for k, v in json.load(open(preset_file)).items() if not k.startswith("_")}
        before = dict(leaves(c))
        merge(c, pre); c["preset"] = name
        diff = [k for k, v in leaves(pre) if before.get(k) != v]
        changed.append(f"preset={name} (set {', '.join(diff) or 'nothing new'})")
# Earlier templates pinned these profile-governed keys, which silently overrode every profile.
# Drop them when they still hold those old defaults; edited values are kept.
OLD = {("git", "guard"): "enforce", ("git", "ops"): {"stage": "ask", "commit": "ask", "push": "ask", "pr": "ask"},
       ("gate", "mode"): "enforce",
       ("review", "lenses"): ["correctness", "security", "scale", "operability", "design", "experience"],
       ("review", "adversary"): True}
for (sec, key), val in OLD.items():
    if isinstance(c.get(sec), dict) and c[sec].get(key) == val:
        del c[sec][key]; changed.append(f"removed pinned default {sec}.{key}")
        if not c[sec]: del c[sec]
if c.get("mode") != mode: c["mode"] = mode; changed.append(f"mode={mode}")
if branch: c["default_branch"] = branch; changed.append(f"default_branch={branch}")
if profile:
    sys.path.insert(0, ".claude/harness/scripts")
    from hconfig import PROFILES
    if profile not in PROFILES: sys.exit(f"unknown profile: {profile} (use one of: {', '.join(PROFILES)})")
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

if [[ $fresh -eq 1 || $preset_new -eq 1 || $detect -eq 1 || ${#commands[@]} -gt 0 ]]; then
  echo "Check commands (from the repo's files; nothing is run)"
  dargs=(--apply); [[ $detect -eq 1 ]] && dargs+=(--redetect)
  if [[ $preset_new -eq 1 ]]; then  # only the commands this preset just set may be replaced or cleared
    while IFS= read -r k; do [[ -n "$k" ]] && dargs+=(--replace "$k"); done < <(python3 -c \
      'import json,sys;print("\n".join(json.load(open(sys.argv[1])).get("commands",{})))' "$preset_file")
  fi
  python3 .claude/harness/scripts/detect-commands.py "${dargs[@]}" "${commands[@]+"${commands[@]}"}"
fi

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

agents_block() { # write or refresh the managed harness block in AGENTS.md
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
}

if [[ $mode == tracked ]]; then
  echo "CLAUDE.md"
  if ! grep -qs '@.claude/harness/RULES.md' CLAUDE.md; then
    printf '\n## Way of work\n@.claude/harness/RULES.md\n' >> CLAUDE.md; echo "  import added"
  else echo "  import present"; fi

  if [[ $agents_md -eq 1 ]]; then
    echo "AGENTS.md (managed block)"
    agents_block
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
  echo "Rules: injected by the SessionStart hook (CLAUDE.md and .gitignore untouched)"
  # Other coding agents (Codex, Cursor, ...) read AGENTS.md. Create it only when the repo has none, keep it out
  # of git, and record that we own it so uninstall.sh and wf-new.sh handle only our copy.
  if [[ $agents_md -eq 1 ]]; then
    echo "AGENTS.md (for other coding agents; kept out of git)"
    if git ls-files --error-unmatch AGENTS.md >/dev/null 2>&1; then
      echo "  AGENTS.md is tracked, so it is left alone; other agents do not get the harness rules in local mode"
    elif [[ -e AGENTS.md ]] && ! grep -q '<!-- harness:begin -->' AGENTS.md; then
      echo "  an untracked AGENTS.md of your own exists; left alone"
    else
      agents_block
      python3 -c 'import json;p=".claude/harness/harness.json";c=json.load(open(p));c["agents_md"]="local";open(p,"w").write(json.dumps(c,indent=2)+"\n")'
    fi
  fi
  excl_extra=()
  # Hide AGENTS.md only while it is still our copy (markers present), never a file the user put there since.
  if [[ -e AGENTS.md ]] && grep -q '<!-- harness:begin -->' AGENTS.md \
     && grep -q '"agents_md": "local"' .claude/harness/harness.json \
     && ! git ls-files --error-unmatch AGENTS.md >/dev/null 2>&1; then excl_extra+=(AGENTS.md); fi

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
  python3 - "$common/info/exclude" ".claude/harness/local-paths.txt" "${excl_extra[@]+"${excl_extra[@]}"}" << 'PY'
import pathlib, sys
p, paths = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
entries = [l.strip() for l in paths.read_text().splitlines() if l.strip() and not l.startswith("#")] + sys.argv[3:]
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
    [[ -z "$p" || -e "$p" ]] || echo "WARNING: preset '$preset' expects $p, which this repo lacks; adopt the project template or edit harness.json."
  done < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1])).get("_install",{}).get("expects",[])))' "$preset_file")
fi
echo "Next:"
echo "  1. Run each check command once (python3 .claude/harness/scripts/detect-commands.py lists them) and fix"
echo "     any in .claude/harness/harness.json; check gate.critical_paths, \"team\" and \"profile\"."
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
