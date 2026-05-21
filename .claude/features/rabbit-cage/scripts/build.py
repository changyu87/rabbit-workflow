#!/usr/bin/env python3
"""build.py — unified workspace artifact builder.

Discovers per-feature publish.json manifests and builds all declared
copy-file targets. Source paths in each manifest are relative to the
feature directory; destination paths are relative to the repo root.

Usage: build.py [REPO_ROOT]

Version: 2.0.0
Owner: rabbit-workflow team (rabbit-cage)
Deprecation criterion: when Claude Code natively manages workspace artifact generation
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _discover_manifests(root: Path):
    """Yield (feature_dir, manifest) for each active feature with publish.json."""
    for feature_json_path in sorted(root.glob(".claude/features/*/feature.json")):
        try:
            meta = json.loads(feature_json_path.read_text())
        except Exception:
            continue
        if meta.get("status") == "retired":
            continue
        publish = feature_json_path.parent / "publish.json"
        if not publish.exists():
            continue
        try:
            manifest = json.loads(publish.read_text())
        except Exception:
            sys.stderr.write(f"build: skipping malformed publish.json: {publish}\n")
            continue
        yield feature_json_path.parent, manifest


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        try:
            out = subprocess.check_output(
                ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
            )
            root = Path(out.decode().strip())
        except Exception:
            sys.stderr.write("build: cannot determine REPO_ROOT (not a git repo, no arg)\n")
            return 1

    errors = 0
    for feature_dir, manifest in _discover_manifests(root):
        for target in manifest.get("targets", []):
            name = target["name"]
            if target.get("type") != "copy-file":
                sys.stderr.write(f"  [error] unknown type for target '{name}'\n")
                errors += 1
                continue
            src = feature_dir / target["source"]
            dst = root / target["destination"]
            if not src.is_file():
                sys.stderr.write(f"  [error] source not found: {src}\n")
                errors += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            content_changed = (not dst.is_file()) or (_sha256(src) != _sha256(dst))
            if content_changed:
                shutil.copy2(src, dst)
                print(f"  [built] {name}")
            else:
                print(f"  [no-op] {name}")
            # BUG-81: widen marker write to any copy-file destination under
            # .claude/skills/<name>/ (scripts, resources, SKILL.md).
            skill_match = re.match(r'^\.claude/skills/([^/]+)/', target["destination"])
            if skill_match and content_changed:
                marker = root / ".rabbit-skills-updated"
                with open(marker, "a") as f:
                    f.write(skill_match.group(1) + "\n")

    if errors:
        sys.stderr.write(f"\nbuild: {errors} error(s)\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
