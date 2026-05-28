#!/usr/bin/env python3
"""install.py — install rabbit as a plugin at <project>/.rabbit/.

Invoked by install.sh after the upstream tarball is extracted. Lays down
the minimum file closure needed for the user-promised surfaces:

  1. Drift-protected Claude on session start (policy block via CLAUDE.md)
  2. rabbit-feature-new <name> <path-glob> (declare a feature mapping)
  3. Scope-guard blocking edits to declared-feature paths
  4. .rabbit/.runtime/scope-bypass-once one-shot override marker

Each (source, dest) tuple below is explicit so the installer doesn't
depend on the publish flow having been run against the source tarball.

Excludes development surfaces: test/, docs/, scripts/enforcement/,
deferred features (rabbit-config, rabbit-file, tdd-subagent), retired
tombstones (tdd-state-machine, rabbit-spec).

Usage:
    install.py --src <extracted-tarball-dir> --target <project>/.rabbit

Version: 6.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit's per-project plugin model is superseded
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# ───────────────────────────────────────────────────────────────────────────
# MVP file closure as (src_rel, dst_rel) tuples — explicit source→destination
# ───────────────────────────────────────────────────────────────────────────

# Top-level files (same path on both sides)
SAME_PATH_FILES = [
    "CLAUDE.md",
    ".claude/settings.json",
]

# Hooks: source → deployed
HOOKS = [
    (".claude/features/rabbit-cage/hooks/scope-guard.py", ".claude/hooks/scope-guard.py"),
    (".claude/features/rabbit-cage/hooks/session-start-dispatcher.py", ".claude/hooks/session-start-dispatcher.py"),
    (".claude/features/rabbit-cage/hooks/stop-dispatcher.py", ".claude/hooks/stop-dispatcher.py"),
    (".claude/features/rabbit-cage/hooks/user-prompt-submit-dispatcher.py", ".claude/hooks/user-prompt-submit-dispatcher.py"),
    (".claude/features/rabbit-cage/hooks/_dispatcher_lib.py", ".claude/hooks/_dispatcher_lib.py"),
    (".claude/features/contract/hooks/prompt-injector.py", ".claude/hooks/prompt-injector.py"),
]

# Skills: source SKILL.md → deployed SKILL.md
SKILLS = [
    (".claude/features/rabbit-feature/skills/rabbit-feature-new/SKILL.md", ".claude/skills/rabbit-feature-new/SKILL.md"),
]

# Agents: source → deployed
AGENTS = [
    (".claude/features/spec-seeder/agents/spec-seeder.md", ".claude/agents/spec-seeder.md"),
]

# Commands: source → deployed
COMMANDS: list[tuple[str, str]] = []

# Per-feature sub-path includes (whole subset; same path on both sides)
FEATURE_INCLUDES: dict[str, list[str]] = {
    "contract": [
        "feature.json",
        "lib/__init__.py",
        "lib/runtime.py",
        "lib/checks.py",
        "lib/policy_block.py",
        "lib/mutation.py",
        "lib/producers.py",
        "lib/publish.py",
        "scripts/build-prompt.py",
        "scripts/rabbit_print.py",
        "scripts/validate-feature.py",
        "scripts/validate-meta-contract.py",
        "scripts/find-feature.py",
        "scripts/policy-block.py",
        "schemas/feature.json.schema.json",
        "schemas/runtime.schema.json",
        "schemas/prompts.schema.json",
        "schemas/project-map.json.schema.json",
        "schemas/manifest.schema.json",
        "schemas/rabbit-print.schema.json",
        "templates/spec-template.md",
        "templates/contract-template.md",
        "templates/feature-json-template.json",
        "templates/project-map-template.json",
        "templates/prompts/rabbit-feature-new.txt",
        "templates/prompts/spec-seeder.txt",
    ],
    "policy": [
        "feature.json",
        "philosophy.md",
        "spec-rules.md",
        "coding-rules.md",
    ],
    "rabbit-cage": [
        "feature.json",
        "lib/__init__.py",
        "lib/project_map_reader.py",
    ],
    "rabbit-meta": [
        "feature.json",
        "lib/__init__.py",
        "lib/mode_detection.py",
        "lib/generate_claude_md.py",
        "lib/generate_readme.py",
        "templates/CLAUDE.md.template",
        "templates/README.md.template",
    ],
    "rabbit-feature": [
        "feature.json",
        "scripts/new-feature.py",
    ],
    "spec-seeder": [
        "feature.json",
        "scripts/dispatch-spec-seeder.py",
    ],
}


def copy_one(src_root: Path, dst_root: Path, src_rel: str, dst_rel: str) -> bool:
    src = src_root / src_rel
    dst = dst_root / dst_rel
    if not src.is_file():
        print(f"error: missing required source file: {src_rel}", file=sys.stderr)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    # Preserve executable bit for shell + python scripts copied to user-runnable locations
    if dst.suffix in (".py", ".sh") or "scripts/" in dst_rel or "hooks/" in dst_rel:
        os.chmod(dst, os.stat(dst).st_mode | 0o111)
    return True


def write_rabbit_gitignore(dst_root: Path) -> None:
    content = (
        "# rabbit-owned ephemerals — never commit these\n"
        ".runtime/\n"
        "prompts/\n"
        "tdd-report-*.json\n"
        "impl-suggestion-*.json\n"
        ".scope-active-*\n"
        ".scope-bypass-once\n"
        "__pycache__/\n"
        "*.pyc\n"
    )
    (dst_root / ".gitignore").write_text(content)


def write_version_pin(dst_root: Path) -> None:
    label = os.environ.get("RABBIT_INSTALLED_REF", "unknown")
    (dst_root / ".version").write_text(label + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install rabbit into a target directory")
    parser.add_argument("--src", required=True, type=Path, help="extracted upstream source dir")
    parser.add_argument("--target", required=True, type=Path, help="target install dir (typically <project>/.rabbit)")
    args = parser.parse_args()

    src_root: Path = args.src.resolve()
    dst_root: Path = args.target.resolve()

    if not src_root.is_dir():
        print(f"error: --src is not a directory: {src_root}", file=sys.stderr)
        return 1
    if dst_root.exists() and any(dst_root.iterdir()):
        print(f"error: --target exists and is not empty: {dst_root}", file=sys.stderr)
        return 1

    dst_root.mkdir(parents=True, exist_ok=True)
    ok = True

    for rel in SAME_PATH_FILES:
        ok &= copy_one(src_root, dst_root, rel, rel)

    for src_rel, dst_rel in HOOKS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for src_rel, dst_rel in SKILLS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for src_rel, dst_rel in AGENTS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for src_rel, dst_rel in COMMANDS:
        ok &= copy_one(src_root, dst_root, src_rel, dst_rel)

    for feature, paths in FEATURE_INCLUDES.items():
        base = f".claude/features/{feature}"
        for rel in paths:
            full = f"{base}/{rel}"
            ok &= copy_one(src_root, dst_root, full, full)

    if not ok:
        print("install: aborting due to missing source files", file=sys.stderr)
        return 1

    write_rabbit_gitignore(dst_root)
    write_version_pin(dst_root)

    total_files = sum(1 for p in dst_root.rglob("*") if p.is_file())
    print(f"Installed {total_files} files to {dst_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
