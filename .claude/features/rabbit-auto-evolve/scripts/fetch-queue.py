#!/usr/bin/env python3
"""fetch-queue.py — emit a deterministic JSON array of open ACTIONABLE issues.

Usage:
  fetch-queue.py            # emit sorted JSON array on stdout
  fetch-queue.py --detect-leaks   # emit {"leaks": [...]} for de-queued issues

Per rabbit-auto-evolve spec.md Inv 2, invokes
  gh issue list --repo <repo> --state open
                --json number,title,labels,body,createdAt --limit 500
and selects the OPEN issues that carry BOTH a valid `feature:<name>` label
AND a valid `priority:<level>` label — the ACTIONABILITY basis. It emits a
deterministic JSON array on stdout, sorted by priority
(critical > high > medium > low) then createdAt ascending within each bucket.

Selection is ACTIONABILITY-based, not keyed on `rabbit-managed` (coexistence
step 1 of #753, which retires the label). The `rabbit-managed` label is still
TOLERATED — an actionable issue is selected whether or not it carries it — so
this switch is behavior-preserving today (per #753's finding, 0 open
feature-labeled issues lack `rabbit-managed`). This aligns the actual
selection with the already-LABEL-INDEPENDENT convergence guarantee (Inv 25).

`--detect-leaks` (Inv 59, issue #731) is the de-queue defense-in-depth
backstop: it queries ALL open issues and flags any that once entered the
rabbit pipeline (carry a `filed-by:*` provenance label) but have LOST the
`rabbit-managed` label without being closed — the forbidden "de-queue" leak.
It emits a deterministic JSON object {"leaks": [...]} so a leaked issue is
re-surfaced for re-convergence rather than silently stranded open-but-
untracked. The primary fix is forbidding the de-queue action (Red-Flag
Inv 59); this detector exists only as a backstop for pre-existing leaks.

Repo slug resolves via rabbit-issue/_gh.repo_slug — no `git remote get-url`
shellouts. The script never reads or writes anything other than the gh CLI
output stream (no git, no filesystem mutations).

Exit code: 0 on success; non-zero on gh-auth failure or any unexpected gh
error (stderr passthrough).

Version: 1.2.0
Owner: rabbit-workflow team (rabbit-auto-evolve)
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


def label_names(issue):
    return {lbl.get("name", "") for lbl in issue.get("labels", [])}


def is_actionable(issue):
    """An issue is ACTIONABLE (and thus belongs in the queue) when it carries
    BOTH a `feature:<name>` label AND a recognized `priority:<level>` label
    (one of critical/high/medium/low). This is the actionability selection
    basis (Inv 2 / #758, coexistence step 1 of #753) — it does NOT depend on
    the `rabbit-managed` label, which is merely tolerated during the #753
    coexistence window."""
    has_feature = any(
        n.startswith("feature:") and n.split(":", 1)[1]
        for n in label_names(issue)
    )
    return has_feature and priority_rank(issue) != NO_PRIORITY_RANK


def is_leak(issue):
    """An issue is a de-queue LEAK (Inv 59) when it is OPEN, once entered the
    rabbit pipeline (carries any `filed-by:*` provenance label, proving it was
    rabbit-managed at filing time), yet has LOST the `rabbit-managed` label
    without being closed. Removing the label while open is the forbidden
    "de-queue" action — such an issue would otherwise vanish from the queue."""
    names = label_names(issue)
    if "rabbit-managed" in names:
        return False
    return any(n.startswith("filed-by:") for n in names)


def _gh_issue_list(args):
    """Run `gh issue list` with the given trailing args; return parsed JSON.
    Exits the process on gh error or invalid JSON (stderr passthrough)."""
    repo = repo_slug()
    try:
        proc = subprocess.run(
            ["gh", "issue", "list", "--repo", repo] + args,
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or "")
        sys.exit(e.returncode or 1)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"fetch-queue: gh emitted invalid JSON: {e}\n")
        sys.exit(1)


def detect_leaks():
    """Surface OPEN de-queued issues (Inv 59) as {"leaks": [...]} on stdout."""
    issues = _gh_issue_list(
        ["--state", "open",
         "--json", "number,title,labels,createdAt",
         "--limit", "500"]
    )
    leaks = [i for i in issues if is_leak(i)]
    leaks.sort(key=lambda i: i.get("number", 0))
    json.dump({"leaks": leaks}, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="List open ACTIONABLE issues (valid feature: + priority: "
                    "label), sorted by priority then createdAt, as JSON on "
                    "stdout."
    )
    parser.add_argument(
        "--detect-leaks", action="store_true",
        help="Instead of the queue, emit {\"leaks\": [...]} listing OPEN "
             "issues that lost the rabbit-managed label without being closed "
             "(the forbidden de-queue leak, Inv 59).",
    )
    args = parser.parse_args()

    if args.detect_leaks:
        detect_leaks()
        return

    issues = _gh_issue_list(
        ["--state", "open",
         "--json", "number,title,labels,body,createdAt",
         "--limit", "500"]
    )

    # Actionability-based selection (Inv 2 / #758): keep OPEN issues with both
    # a valid feature: label and a valid priority: label. NOT keyed on
    # rabbit-managed — the label is tolerated, not required (coexistence step 1
    # of #753).
    queue = [i for i in issues if is_actionable(i)]
    queue.sort(key=sort_key)
    json.dump(queue, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
