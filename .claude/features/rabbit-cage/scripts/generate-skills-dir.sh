#!/usr/bin/env bash
# generate-skills-dir.sh — create/refresh .claude/skills/ from feature surface declarations.
#
# Usage:
#   generate-skills-dir.sh [--check] [REPO_ROOT]
#
#   --check    Dry-run: exit 0 if up-to-date, 1 if structural or content drift detected.
#   REPO_ROOT  Optional; defaults to git rev-parse --show-toplevel.
#
# Default mode: creates .claude/skills/, creates/updates/removes symlinks,
# saves sha256 baseline to .rbt-skills-hash. Idempotent. Prints changes.
#
# Symlink convention:
#   .claude/skills/<name>  →  ../features/<feat>/skills/<name>
#
# Version: 1.0.0
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
HASH_FILE="$REPO_ROOT/.rbt-skills-hash"

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

# Computes a deterministic sha256 hash over all source SKILL.md files.
compute_hash() {
  python3 - "$REGISTRY" "$FEATURES_DIR" <<'PYEOF'
import hashlib, json, os, sys
registry_path, features_dir = sys.argv[1], sys.argv[2]
with open(registry_path) as f:
    registry = json.load(f)
lines = []
for feat_name in sorted(registry.get("features", {})):
    fj = os.path.join(features_dir, feat_name, "feature.json")
    if not os.path.isfile(fj):
        continue
    with open(fj) as f:
        data = json.load(f)
    for skill_name in sorted(data.get("surface", {}).get("skills", [])):
        skill_md = os.path.join(features_dir, feat_name, "skills", skill_name, "SKILL.md")
        if os.path.isfile(skill_md):
            with open(skill_md, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            lines.append(f"{h}  {feat_name}/{skill_name}/SKILL.md")
for l in lines:
    print(l)
PYEOF
}

declare -A EXPECTED
while IFS='|' read -r feat skill; do
  EXPECTED["$skill"]="$feat"
done < <(collect_expected)

if [ "$CHECK" -eq 1 ]; then
  DRIFT=0

  # Structural: verify every expected skill has a valid symlink
  for name in "${!EXPECTED[@]}"; do
    link="$SKILLS_DIR/$name"
    if [ ! -L "$link" ] || [ ! -e "$link" ]; then
      echo "drift: missing or broken symlink .claude/skills/$name"
      DRIFT=1
    fi
  done

  # Structural: flag stale symlinks not in expected set
  if [ -d "$SKILLS_DIR" ]; then
    for link in "$SKILLS_DIR"/*; do
      [ -L "$link" ] || continue
      name="$(basename "$link")"
      if [ -z "${EXPECTED[$name]:-}" ]; then
        echo "drift: stale symlink .claude/skills/$name"
        DRIFT=1
      fi
    done
  fi

  # Content: compare current hash against saved baseline
  if [ -f "$HASH_FILE" ]; then
    CURRENT="$(compute_hash)"
    SAVED="$(cat "$HASH_FILE")"
    if [ "$CURRENT" != "$SAVED" ]; then
      echo "drift: SKILL.md content changed since session start"
      DRIFT=1
    fi
  else
    if [ "${#EXPECTED[@]}" -gt 0 ]; then
      echo "drift: no hash baseline (.rbt-skills-hash absent)"
      DRIFT=1
    fi
  fi

  exit "$DRIFT"
fi

# Default mode: generate / refresh
mkdir -p "$SKILLS_DIR"
CHANGED=0

for name in "${!EXPECTED[@]}"; do
  feat="${EXPECTED[$name]}"
  target="../features/$feat/skills/$name"
  link="$SKILLS_DIR/$name"
  if [ -L "$link" ]; then
    existing="$(readlink "$link")"
    [ "$existing" = "$target" ] && continue
    rm "$link"
    echo "  [update] .claude/skills/$name"
    CHANGED=1
  else
    echo "  [link] .claude/skills/$name → $target"
    CHANGED=1
  fi
  ln -s "$target" "$link"
done

# Remove stale symlinks
if [ -d "$SKILLS_DIR" ]; then
  for link in "$SKILLS_DIR"/*; do
    [ -L "$link" ] || continue
    name="$(basename "$link")"
    if [ -z "${EXPECTED[$name]:-}" ]; then
      rm "$link"
      echo "  [remove] stale .claude/skills/$name"
      CHANGED=1
    fi
  done
fi

compute_hash > "$HASH_FILE"
[ "$CHANGED" -eq 0 ] && echo "skills directory up to date" || echo "skills directory refreshed"
exit 0
