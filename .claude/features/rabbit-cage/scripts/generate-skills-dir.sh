#!/usr/bin/env bash
# generate-skills-dir.sh — create/refresh .claude/skills/ from feature surface declarations.
#
# Usage:
#   generate-skills-dir.sh [--check] [REPO_ROOT]
#
#   --check    Dry-run: exit 0 if up-to-date, 1 if structural or content drift detected.
#   REPO_ROOT  Optional; defaults to git rev-parse --show-toplevel.
#
# Default mode: creates .claude/skills/, copies (cp -rp) each declared skill directory,
# removes stale copies. Idempotent. Prints changes.
#
# Copy convention:
#   .claude/skills/<name>  ←  copy of  ../features/<feat>/skills/<name>
#
# Version: 2.0.0
# Owner: rabbit-cage

set -euo pipefail

CHECK=0
REPO_ROOT=""
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    -*) echo "Error: unknown option '$arg'" >&2; exit 2 ;;
    *) REPO_ROOT="$arg" ;;
  esac
done

REPO_ROOT="${REPO_ROOT:-$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)}"
FEATURES_DIR="$REPO_ROOT/.claude/features"
REGISTRY="$FEATURES_DIR/registry.json"
SKILLS_DIR="$REPO_ROOT/.claude/skills"

[ -f "$REGISTRY" ] || { echo "Error: registry.json not found at $REGISTRY" >&2; exit 1; }

# Prints "feat_name|skill_name" for every declared skill whose source dir exists.
collect_expected() {
  python3 - "$REGISTRY" "$FEATURES_DIR" <<'PYEOF'
import json, os, sys
registry_path, features_dir = sys.argv[1], sys.argv[2]
with open(registry_path) as f:
    registry = json.load(f)
for feat_name in registry.get("features", {}):
    fj = os.path.join(features_dir, feat_name, "feature.json")
    if not os.path.isfile(fj):
        continue
    with open(fj) as f:
        data = json.load(f)
    for skill_name in data.get("surface", {}).get("skills", []):
        src = os.path.join(features_dir, feat_name, "skills", skill_name)
        if os.path.isdir(src):
            print(f"{feat_name}|{skill_name}")
PYEOF
}

declare -A EXPECTED
while IFS='|' read -r feat skill; do
  if [ -n "${EXPECTED[$skill]:-}" ]; then
    echo "Warning: skill name '$skill' declared by both '${EXPECTED[$skill]}' and '$feat' — '$feat' ignored" >&2
    continue
  fi
  EXPECTED["$skill"]="$feat"
done < <(collect_expected)

if [ "$CHECK" -eq 1 ]; then
  DRIFT=0

  # Content: verify every expected skill has a copy with matching sha256
  for name in "${!EXPECTED[@]}"; do
    feat="${EXPECTED[$name]}"
    src_md="$FEATURES_DIR/$feat/skills/$name/SKILL.md"
    copy_md="$SKILLS_DIR/$name/SKILL.md"
    if [ ! -d "$SKILLS_DIR/$name" ] || [ ! -f "$copy_md" ]; then
      echo "drift: missing copy .claude/skills/$name"
      DRIFT=1
    elif ! sha256sum "$src_md" "$copy_md" 2>/dev/null | awk '{print $1}' | sort -u | wc -l | grep -q "^1$"; then
      echo "drift: SKILL.md content differs for .claude/skills/$name"
      DRIFT=1
    fi
  done

  # Structural: flag stale entries in skills dir not in expected set
  if [ -d "$SKILLS_DIR" ]; then
    for entry in "$SKILLS_DIR"/*; do
      [ -e "$entry" ] || continue
      name="$(basename "$entry")"
      if [ -z "${EXPECTED[$name]:-}" ]; then
        echo "drift: stale entry .claude/skills/$name"
        DRIFT=1
      fi
    done
  fi

  exit "$DRIFT"
fi

# Default mode: generate / refresh via copy
mkdir -p "$SKILLS_DIR"
CHANGED=0

for name in "${!EXPECTED[@]}"; do
  feat="${EXPECTED[$name]}"
  source_dir="$FEATURES_DIR/$feat/skills/$name"
  copy_dir="$SKILLS_DIR/$name"

  if [ -L "$copy_dir" ]; then
    # Remove old symlink and replace with real copy
    rm "$copy_dir"
    cp -rp "$source_dir" "$copy_dir"
    echo "  [update] .claude/skills/$name (replaced symlink with copy)"
    CHANGED=1
  elif [ -d "$copy_dir" ]; then
    # Real directory exists; re-copy to ensure freshness
    rm -rf "$copy_dir"
    cp -rp "$source_dir" "$copy_dir"
    echo "  [refresh] .claude/skills/$name"
    CHANGED=1
  else
    cp -rp "$source_dir" "$copy_dir"
    echo "  [copy] .claude/skills/$name"
    CHANGED=1
  fi
done

# Remove stale entries (symlinks or directories) not in expected set
if [ -d "$SKILLS_DIR" ]; then
  for entry in "$SKILLS_DIR"/*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    name="$(basename "$entry")"
    if [ -z "${EXPECTED[$name]:-}" ]; then
      rm -rf "$entry"
      echo "  [remove] stale .claude/skills/$name"
      CHANGED=1
    fi
  done
fi

[ "$CHANGED" -eq 0 ] && echo "skills directory up to date" || echo "skills directory refreshed"
exit 0
