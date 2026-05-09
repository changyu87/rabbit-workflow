#!/bin/bash
# relink.sh — create/refresh symlinks declared in each feature's surface block.
#
# Usage:
#   relink.sh <features-dir> [repo-root]
#
#   <features-dir>  directory containing registry.json and feature subdirs
#                   (e.g., .claude/features)
#   [repo-root]     workspace root where surface symlinks land
#                   default: parent of parent of features-dir
#                   (so .claude/features -> .claude -> repo root)
#
# For each feature, reads surface.{hooks,commands,agents,skills}:
#   Each value is a repo-relative symlink path. Creates:
#     <repo-root>/<surface-path> -> <features-dir>/<feature-name>/<basename>
#   Skips if the target already exists as a regular file (not a symlink).
#   Overwrites stale symlinks.
#
# For surface.root[]:
#   Each value is a filename relative to repo root. Looks for the actual file in
#   <features-dir>/<feature-name>/artifacts/<filename>. Creates:
#     <repo-root>/<filename> -> <features-dir>/<feature-name>/artifacts/<filename>
#   Skips if target exists as a regular file.
#
# Idempotent. Exit 0 on success, 1 on missing inputs, 2 on usage error.

set -u

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "ERROR: usage: relink.sh <features-dir> [repo-root]" >&2
  exit 2
fi

FEATURES_DIR="$1"

if [ ! -d "$FEATURES_DIR" ]; then
  echo "ERROR: features-dir does not exist: $FEATURES_DIR" >&2
  exit 1
fi

REGISTRY="$FEATURES_DIR/registry.json"

if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: registry.json not found: $REGISTRY" >&2
  exit 1
fi

# Default repo-root: parent of parent of features-dir
# .claude/features -> .claude -> repo root
if [ $# -eq 2 ]; then
  REPO_ROOT="$2"
else
  REPO_ROOT="$(cd "$FEATURES_DIR/../.." && pwd)"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required" >&2
  exit 1
fi

python3 - "$FEATURES_DIR" "$REGISTRY" "$REPO_ROOT" <<'PYEOF'
import json
import os
import sys

features_dir = sys.argv[1]
registry_path = sys.argv[2]
repo_root = sys.argv[3]

with open(registry_path) as f:
    registry = json.load(f)

features = registry.get("features", {})
errors = 0

def make_symlink(link_path, target_path, label):
    """Create symlink at link_path pointing to target_path.
    Skips if link_path is already a regular file.
    Overwrites if link_path is a stale symlink.
    """
    # Ensure parent directory exists
    parent = os.path.dirname(link_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    if os.path.islink(link_path):
        existing_target = os.readlink(link_path)
        if existing_target == target_path:
            print(f"  [skip] already linked: {label}")
            return
        # Stale symlink — remove and recreate
        os.remove(link_path)
        print(f"  [update] relinking: {label}")
    elif os.path.isfile(link_path):
        # Regular file exists — skip, do not overwrite
        print(f"  [skip] regular file exists: {label}")
        return
    else:
        print(f"  [link] {label}")

    os.symlink(target_path, link_path)

for name, entry in features.items():
    fj_path = os.path.join(features_dir, name, "feature.json")
    if not os.path.isfile(fj_path):
        print(f"[warn] feature.json not found for '{name}': {fj_path}")
        continue

    with open(fj_path) as f:
        data = json.load(f)

    surface = data.get("surface", {})

    # Process hooks, commands, agents, skills — each value is a repo-relative symlink path
    for category in ("hooks", "commands", "agents", "skills"):
        for surface_path in surface.get(category, []):
            # The surface_path is the repo-relative path where the symlink should appear
            link_abs = os.path.join(repo_root, surface_path)
            basename = os.path.basename(surface_path)
            # Look for the source file in two locations:
            #   1. features_dir/<name>/<category>/<basename>  (new canonical layout)
            #   2. features_dir/<name>/<basename>             (flat layout)
            candidate_in_subdir = os.path.join(features_dir, name, category, basename)
            candidate_flat      = os.path.join(features_dir, name, basename)
            if os.path.exists(candidate_in_subdir):
                actual_file = candidate_in_subdir
            elif os.path.exists(candidate_flat):
                actual_file = candidate_flat
            else:
                # The surface path itself is the canonical location (pre-existing file
                # not yet moved into feature subdir); skip symlink creation.
                print(f"  [skip] source not in feature dir, surface path is canonical: {surface_path}")
                continue
            make_symlink(link_abs, actual_file, f"{surface_path} -> {actual_file}")

    # Process root[] — filenames relative to repo root, sourced from artifacts/
    for filename in surface.get("root", []):
        link_abs = os.path.join(repo_root, filename)
        artifacts_file = os.path.join(features_dir, name, "artifacts", filename)
        if not os.path.isfile(artifacts_file):
            print(f"  [skip] artifact not found: {artifacts_file}")
            continue
        make_symlink(link_abs, artifacts_file, f"{filename} -> {artifacts_file}")

print("relink complete")
sys.exit(0)
PYEOF
