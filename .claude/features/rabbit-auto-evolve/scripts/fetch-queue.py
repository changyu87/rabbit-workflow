#!/usr/bin/env python3
"""fetch-queue.py — emit a deterministic JSON array of open rabbit-managed issues.

Usage:
  fetch-queue.py            # emit sorted JSON array on stdout

Per rabbit-auto-evolve spec.md Inv 2, invokes
  gh issue list --repo <repo> --state open --label rabbit-managed
                --json number,title,labels,body,createdAt --limit 500
and emits a deterministic JSON array on stdout, sorted by priority
(critical > high > medium > low; no-priority issues sort to the END)
then createdAt ascending within each bucket.

Repo slug resolves via rabbit-issue/_gh.repo_slug — no `git remote get-url`
shellouts. The script never reads or writes anything other than the gh CLI
output stream (no git, no filesystem mutations).

Exit code: 0 on success; non-zero on gh-auth failure or any unexpected gh
error (stderr passthrough).

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when Claude Code or rabbit gains a native always-on
autonomous-agent mode that supersedes this skill.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PRIORITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}
NO_PRIORITY_RANK = 4  # sort no-priority issues to the END

# Add rabbit-issue/scripts to sys.path so `from _gh import repo_slug` works.
# Mirror the import style used by rabbit-issue/scripts/item-status.py.
_HERE = Path(__file__).resolve().parent
_RABBIT_ISSUE_SCRIPTS = _HERE.parent.parent / "rabbit-issue" / "scripts"
if str(_RABBIT_ISSUE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RABBIT_ISSUE_SCRIPTS))
from _gh import repo_slug  # noqa: E402


def priority_rank(issue):
    """Return the priority rank for an issue based on its 'priority:<level>'
    label. Issues with no recognized priority label sort to NO_PRIORITY_RANK
    (the end)."""
    for lbl in issue.get("labels", []):
        name = lbl.get("name", "")
        if name.startswith("priority:"):
            level = name.split(":", 1)[1]
            if level in PRIORITY_RANK:
                return PRIORITY_RANK[level]
    return NO_PRIORITY_RANK


def sort_key(issue):
    # createdAt from gh is ISO 8601 UTC ("YYYY-MM-DDTHH:MM:SSZ") so string
    # sort is lexicographically equivalent to chronological order.
    return (priority_rank(issue), issue.get("createdAt", ""))


def main():
    parser = argparse.ArgumentParser(
        description="List open rabbit-managed issues, sorted by priority "
                    "then createdAt, as JSON on stdout."
    )
    parser.parse_args()

    repo = repo_slug()
    try:
        proc = subprocess.run(
            ["gh", "issue", "list",
             "--repo", repo,
             "--state", "open",
             "--label", "rabbit-managed",
             "--json", "number,title,labels,body,createdAt",
             "--limit", "500"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or "")
        sys.exit(e.returncode or 1)

    try:
        issues = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"fetch-queue: gh emitted invalid JSON: {e}\n")
        sys.exit(1)

    issues.sort(key=sort_key)
    json.dump(issues, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
