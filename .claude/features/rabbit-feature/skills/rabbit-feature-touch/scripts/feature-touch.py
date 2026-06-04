#!/usr/bin/env python3
"""Companion script for the rabbit-feature-touch SKILL.md.

Owns the orchestration logic that involves computed values and mode-aware
branching, so the SKILL.md body stays script-tier (spec-rules.md §4
Script-Backed Orchestration) instead of carrying bash blocks with runtime
placeholders the model would assemble at invocation time.

Two subcommands:

  resolve-spec-path <feature-name>
      Print the resolved spec path for a feature. Prefers the flat
      `docs/spec.md` layout (ratified migration target) and falls back only
      to the legacy `docs/spec/spec.md` for any not-yet-migrated nested-docs
      feature. The dead specs/ fallback has been removed. Mode-aware: detects
      standalone vs plugin mode from <repo_root>/.rabbit/.runtime/mode and
      picks the matching feature_dir prefix.

  resolve-contract-path <feature-name>
      Like resolve-spec-path, for the contract: prefers flat
      `docs/contract.md`, then the legacy `docs/spec/contract.md`.

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

Version: 0.3.0
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


def _resolve_doc(feature_dir: Path, name: str) -> Path:
    """Resolve a doc surface (spec.md / contract.md) across the doc layouts.

    Preference order:
      1. flat    docs/<name>        (ratified migration target — PREFERRED)
      2. legacy  docs/spec/<name>   (not-yet-migrated nested-docs layout)
    Returns the first that exists; defaults to the flat docs/ target when none
    exists yet (so new resolutions point at the ratified location). The dead
    specs/ fallback is removed — every feature has migrated to flat docs/.
    """
    flat = feature_dir / "docs" / name
    legacy = feature_dir / "docs/spec" / name
    for cand in (flat, legacy):
        if cand.is_file():
            return cand
    return flat


def _spec_path(feature_dir: Path) -> Path:
    """Prefer flat docs/spec.md; fall back to legacy docs/spec/spec.md."""
    return _resolve_doc(feature_dir, "spec.md")


def _contract_path(feature_dir: Path) -> Path:
    """Prefer flat docs/contract.md; fall back to legacy docs/spec/contract.md."""
    return _resolve_doc(feature_dir, "contract.md")


def _emit_relative(repo_root: Path, path: Path) -> None:
    # Emit repo-root-relative when possible, else absolute.
    try:
        print(str(path.relative_to(repo_root)))
    except ValueError:
        print(str(path))


def cmd_resolve_spec_path(feature: str) -> int:
    repo_root = _repo_root(Path.cwd())
    mode = _mode(repo_root)
    feature_dir = _feature_dir(repo_root, feature, mode)
    _emit_relative(repo_root, _spec_path(feature_dir))
    return 0


def cmd_resolve_contract_path(feature: str) -> int:
    repo_root = _repo_root(Path.cwd())
    mode = _mode(repo_root)
    feature_dir = _feature_dir(repo_root, feature, mode)
    _emit_relative(repo_root, _contract_path(feature_dir))
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
            "usage: feature-touch.py "
            "{resolve-spec-path|resolve-contract-path|commit-spec} ...\n"
            "  resolve-spec-path <feature-name>\n"
            "  resolve-contract-path <feature-name>\n"
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
    if sub == "resolve-contract-path":
        if len(argv) != 3:
            sys.stderr.write(
                "usage: feature-touch.py resolve-contract-path <feature-name>\n"
            )
            return 2
        return cmd_resolve_contract_path(argv[2])
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
