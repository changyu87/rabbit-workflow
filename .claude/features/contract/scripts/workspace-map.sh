#!/usr/bin/env bash
# workspace-map.sh — workspace hierarchy map for rabbit-workflow.
#
# Usage (machine mode, default):
#   workspace-map.sh [--repo-root <path>]
#   Produces JSON conforming to workspace-map.json.schema.json.
#
# Usage (human mode):
#   workspace-map.sh --human [--repo-root <path>]
#   Produces human-readable terminal output of the workspace tree.
#
# Usage (backlog path, legacy subcommand — preserved for rabbit-backlog):
#   workspace-map.sh backlog <feature-name> [--repo-root <path>]
#   Outputs the canonical backlog directory path for the named feature.
#
# Exit:
#   0  success
#   1  error
#
# Owner: rabbit-workflow team (contract feature)
# Version: 2.0.0
# Deprecation criterion: when rabbit features adopt a native workspace registry.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_root() {
  local root_arg="$1"
  if [ -n "$root_arg" ]; then
    echo "$root_arg"
  elif [ -n "${RABBIT_ROOT:-}" ]; then
    echo "$RABBIT_ROOT"
  else
    git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null \
      || { echo "ERROR: cannot resolve repo root" >&2; exit 1; }
  fi
}

# ---------------------------------------------------------------------------
# Legacy subcommand: backlog (used by rabbit-backlog/file-backlog-item.sh)
# ---------------------------------------------------------------------------
if [ "${1:-}" = "backlog" ]; then
  shift
  FEATURE_NAME="${1:-}"
  shift || true
  REPO_ROOT_ARG=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo-root) REPO_ROOT_ARG="$2"; shift 2 ;;
      *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
    esac
  done
  if [ -z "$FEATURE_NAME" ]; then
    echo "ERROR: feature-name is required" >&2
    exit 1
  fi
  RESOLVED_ROOT="$(resolve_root "$REPO_ROOT_ARG")"
  echo "${RESOLVED_ROOT}/.claude/backlogs/${FEATURE_NAME}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Parse flags for JSON/human mode
# ---------------------------------------------------------------------------
HUMAN=0
REPO_ROOT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --human) HUMAN=1; shift ;;
    --repo-root) REPO_ROOT_ARG="$2"; shift 2 ;;
    -h|--help) echo "usage: workspace-map.sh [--human] [--repo-root <path>]"; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(resolve_root "$REPO_ROOT_ARG")"

# All data collection and output via a single Python script to avoid heredoc quoting issues
python3 << PYEOF
import json, os, sys

REPO_ROOT = "$REPO_ROOT"
HUMAN = $HUMAN
CLAUDE_DIR = os.path.join(REPO_ROOT, ".claude")
REGISTRY = os.path.join(CLAUDE_DIR, "features", "registry.json")

# Features
features = []
if os.path.isfile(REGISTRY):
    try:
        reg = json.load(open(REGISTRY))
        for name, meta in sorted(reg.get("features", {}).items()):
            entry = {
                "name": name,
                "path": meta.get("path", ""),
                "version": meta.get("version", ""),
                "tdd_state": ""
            }
            feat_json_path = os.path.join(REPO_ROOT, meta.get("path", ""), "feature.json")
            if os.path.isfile(feat_json_path):
                try:
                    fd = json.load(open(feat_json_path))
                    entry["tdd_state"] = fd.get("tdd_state", "")
                    entry["version"] = fd.get("version", entry["version"])
                except Exception:
                    pass
            features.append(entry)
    except Exception:
        pass

# Scripts
scripts = []
feat_dir = os.path.join(CLAUDE_DIR, "features")
if os.path.isdir(feat_dir):
    for feat in sorted(os.listdir(feat_dir)):
        scripts_path = os.path.join(feat_dir, feat, "scripts")
        if os.path.isdir(scripts_path):
            for root, dirs, files in os.walk(scripts_path):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith(".sh"):
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, REPO_ROOT)
                        scripts.append({"path": rel, "executable": os.access(full, os.X_OK)})

# Schemas
schemas = []
if os.path.isdir(feat_dir):
    for feat in sorted(os.listdir(feat_dir)):
        schemas_path = os.path.join(feat_dir, feat, "schemas")
        if os.path.isdir(schemas_path):
            for f in sorted(os.listdir(schemas_path)):
                if f.endswith(".json"):
                    rel = os.path.relpath(os.path.join(schemas_path, f), REPO_ROOT)
                    schemas.append({"path": rel, "feature": feat})

# Commands
commands = []
cmd_dir = os.path.join(CLAUDE_DIR, "commands")
if os.path.isdir(cmd_dir):
    for f in sorted(os.listdir(cmd_dir)):
        if f.endswith(".md"):
            commands.append({"name": f[:-3], "path": ".claude/commands/" + f})

# Skills
skills = []
skills_dir = os.path.join(CLAUDE_DIR, "skills")
if os.path.isdir(skills_dir):
    for skill in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, skill, "SKILL.md")
        if os.path.isfile(skill_md):
            skills.append({"name": skill, "path": ".claude/skills/" + skill + "/SKILL.md"})

# Hooks
hooks = []
hooks_dir = os.path.join(CLAUDE_DIR, "hooks")
if os.path.isdir(hooks_dir):
    for f in sorted(os.listdir(hooks_dir)):
        if f.endswith(".sh"):
            full = os.path.join(hooks_dir, f)
            sym_target = None
            if os.path.islink(full):
                target = os.path.realpath(full)
                sym_target = os.path.relpath(target, REPO_ROOT)
            hooks.append({"name": f, "path": ".claude/hooks/" + f, "symlink_target": sym_target})

# User project dirs (non-hidden top-level dirs)
user_dirs = []
try:
    for e in sorted(os.listdir(REPO_ROOT)):
        if not e.startswith('.') and os.path.isdir(os.path.join(REPO_ROOT, e)):
            user_dirs.append({"name": e, "path": e})
except Exception:
    pass

if HUMAN:
    print("=== rabbit workspace map ===")
    print("repo:", REPO_ROOT)
    print()
    print("--- features ---")
    for f in features:
        print("  {} ({}) [{}]".format(f["name"], f["version"], f["tdd_state"]))
    print()
    print("--- skills ---")
    for s in skills:
        print("  " + s["name"])
    print()
    print("--- commands ---")
    for c in commands:
        print("  /" + c["name"])
    print()
    print("--- hooks ---")
    for h in hooks:
        sym = " -> " + h["symlink_target"] if h.get("symlink_target") else ""
        print("  " + h["name"] + sym)
    print()
    print("--- user directories ---")
    for d in user_dirs:
        print("  " + d["name"] + "/")
else:
    output = {
        "schemaVersion": "1.0.0",
        "repoRoot": REPO_ROOT,
        "features": features,
        "scripts": scripts,
        "schemas": schemas,
        "commands": commands,
        "skills": skills,
        "hooks": hooks,
        "userProjectDirs": user_dirs
    }
    print(json.dumps(output, indent=2))
PYEOF
