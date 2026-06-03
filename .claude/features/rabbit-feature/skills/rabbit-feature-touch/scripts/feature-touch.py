#!/usr/bin/env python3
"""Companion script for the rabbit-feature-touch SKILL.md.

Owns the orchestration logic that involves computed values and mode-aware
branching, so the SKILL.md body stays script-tier (spec-rules.md §4
Script-Backed Orchestration) instead of carrying bash blocks with runtime
placeholders the model would assemble at invocation time.

Two subcommands:

  resolve-spec-path <feature-name>
      Print the resolved spec path for a feature. Prefers the
      `specs/spec.md` layout (issue #399) and falls back to the legacy
      `docs/spec/spec.md` for not-yet-migrated features. Mode-aware:
      detects standalone vs plugin mode from <repo_root>/.rabbit/.runtime/mode
      and picks the matching feature_dir prefix.

  commit-spec <feature-name> <summary>
      Stage and commit the feature's spec change (if any) BEFORE the TDD
      subagent is dispatched (Step 5). Mode-aware:
        - standalone: feature_dir = .claude/features/<name>/, `git add`.
        - plugin:     feature_dir = .rabbit/rabbit-project/features/<name>/,
                      `git add -f` (host .gitignore typically ignores
                      .rabbit/, and without -f the add silently produces an
                      empty staged diff so no commit lands).
      Skips the commit when the staged diff against the resolved spec path
      is empty. Commit message pattern:
      `spec(<feature-name>): update spec for <summary>`.

All paths are resolved relative to the repo root, which the script derives
by walking up from the cwd to the nearest ancestor containing a `.git`
entry (file or directory, so git worktrees are handled).

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when feature-touch orchestration is natively handled
by the rabbit CLI or by Claude Code's native workflow mechanism.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root(start: Path) -> Path:
    """Walk up from start to the nearest ancestor containing a `.git` entry."""
    cur = start.resolve()
    for cand in (cur, *cur.parents):
        if (cand / ".git").exists():
            return cand
    # Fall back to cwd if no .git found (e.g. tests in a temp dir).
    return cur


def _mode(repo_root: Path) -> str:
    """Detect rabbit mode from <repo_root>/.rabbit/.runtime/mode.

    Returns 'plugin' only when the marker content equals 'plugin';
    otherwise 'standalone' (marker absent or any other content).
    """
    marker = repo_root / ".rabbit/.runtime/mode"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == "plugin":
        return "plugin"
    return "standalone"


def _feature_dir(repo_root: Path, feature: str, mode: str) -> Path:
    if mode == "plugin":
        return repo_root / ".rabbit/rabbit-project/features" / feature
    return repo_root / ".claude/features" / feature


def _spec_path(feature_dir: Path) -> Path:
    """Prefer specs/spec.md (issue #399); fall back to legacy docs/spec/spec.md."""
    preferred = feature_dir / "specs/spec.md"
    legacy = feature_dir / "docs/spec/spec.md"
    if preferred.is_file():
        return preferred
    if legacy.is_file():
        return legacy
    # Not-yet-created: default to the preferred layout.
    return preferred


def cmd_resolve_spec_path(feature: str) -> int:
    repo_root = _repo_root(Path.cwd())
    mode = _mode(repo_root)
    feature_dir = _feature_dir(repo_root, feature, mode)
    spec = _spec_path(feature_dir)
    # Emit repo-root-relative when possible, else absolute.
    try:
        rel = spec.relative_to(repo_root)
        print(str(rel))
    except ValueError:
        print(str(spec))
    return 0


def cmd_commit_spec(feature: str, summary: str) -> int:
    repo_root = _repo_root(Path.cwd())
    mode = _mode(repo_root)
    feature_dir = _feature_dir(repo_root, feature, mode)

    # Mode-aware staging: plugin mode needs -f because the host .gitignore
    # typically ignores .rabbit/.
    add_cmd = ["git", "add"]
    if mode == "plugin":
        add_cmd.append("-f")
    add_cmd.append(str(feature_dir))
    subprocess.run(add_cmd, cwd=repo_root, check=False)

    spec = _spec_path(feature_dir)
    # Empty-diff skip: only commit when the staged spec actually changed.
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", str(spec)],
        cwd=repo_root,
        check=False,
    )
    if diff.returncode == 0:
        print(f"NOOP: no staged spec change for {feature}; skipping commit")
        return 0

    msg = f"spec({feature}): update spec for {summary}"
    commit = subprocess.run(
        ["git", "commit", "-m", msg], cwd=repo_root, check=False
    )
    if commit.returncode != 0:
        print(f"ERROR: git commit failed for {feature}", file=sys.stderr)
        return 1
    print(f"OK: committed spec change for {feature}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(
            "usage: feature-touch.py {resolve-spec-path|commit-spec} ...\n"
            "  resolve-spec-path <feature-name>\n"
            "  commit-spec <feature-name> <summary>\n"
        )
        return 2
    sub = argv[1]
    if sub == "resolve-spec-path":
        if len(argv) != 3:
            sys.stderr.write(
                "usage: feature-touch.py resolve-spec-path <feature-name>\n"
            )
            return 2
        return cmd_resolve_spec_path(argv[2])
    if sub == "commit-spec":
        if len(argv) != 4:
            sys.stderr.write(
                "usage: feature-touch.py commit-spec <feature-name> <summary>\n"
            )
            return 2
        return cmd_commit_spec(argv[2], argv[3])
    sys.stderr.write(f"unknown subcommand: {sub!r}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
