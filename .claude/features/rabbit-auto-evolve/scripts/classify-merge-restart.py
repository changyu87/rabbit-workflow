#!/usr/bin/env python3
"""classify-merge-restart.py — three-rung refresh ladder for a merged PR.

Usage:
  classify-merge-restart.py <pr#>

Per rabbit-auto-evolve spec.md Inv 8, fetches the merged PR's file list via
  gh pr view <#> --json files
and emits exactly one of three literal rung names on stdout (followed by a
single trailing newline; no JSON):

  restart   — any path containing settings.json, OR
              a brand-new file under .claude/skills/*/SKILL.md
              (additions > 0 AND deletions == 0 — pure add), OR
              any path matching .claude/hooks/*.py
  refresh   — any path matching .claude/features/policy/*.md OR
              basename CLAUDE.md (at any depth)
  no-op     — none of the above

Rungs are evaluated in order; first match wins (restart > refresh > no-op).

Exit code: 0 on success; non-zero on gh failure or unexpected error
(stderr passthrough). Reads only the gh CLI output stream — no git
shellouts, no filesystem mutations.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys


def is_restart(path, additions, deletions):
    # (a) settings.json — any path whose basename is settings.json.
    if os.path.basename(path) == "settings.json":
        return True
    # (b) brand-new .claude/skills/*/SKILL.md (additions > 0, deletions == 0).
    if fnmatch.fnmatchcase(path, ".claude/skills/*/SKILL.md"):
        if additions > 0 and deletions == 0:
            return True
    # (c) any .claude/hooks/*.py.
    if fnmatch.fnmatchcase(path, ".claude/hooks/*.py"):
        return True
    return False


def is_refresh(path):
    # .claude/features/policy/*.md
    if fnmatch.fnmatchcase(path, ".claude/features/policy/*.md"):
        return True
    # CLAUDE.md at any depth (basename match).
    if os.path.basename(path) == "CLAUDE.md":
        return True
    return False


def classify(files):
    """Return one of 'restart', 'refresh', 'no-op'. First match wins
    (restart > refresh > no-op)."""
    restart_hit = False
    refresh_hit = False
    for entry in files:
        path = entry.get("path", "")
        additions = entry.get("additions", 0) or 0
        deletions = entry.get("deletions", 0) or 0
        if is_restart(path, additions, deletions):
            restart_hit = True
        if is_refresh(path):
            refresh_hit = True
    if restart_hit:
        return "restart"
    if refresh_hit:
        return "refresh"
    return "no-op"


def main():
    parser = argparse.ArgumentParser(
        description="Classify a merged PR's file list into one of three "
                    "refresh rungs: restart, refresh, or no-op. "
                    "Emits the rung name on stdout."
    )
    parser.add_argument("pr", type=int, help="PR number to classify")
    args = parser.parse_args()

    try:
        proc = subprocess.run(
            ["gh", "pr", "view", str(args.pr), "--json", "files"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or "")
        sys.exit(e.returncode or 1)

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"classify-merge-restart: gh emitted invalid JSON: {e}\n")
        sys.exit(1)

    files = payload.get("files", []) or []
    rung = classify(files)
    sys.stdout.write(rung + "\n")


if __name__ == "__main__":
    main()
