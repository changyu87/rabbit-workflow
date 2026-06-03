"""Shared helpers for rabbit-issue runtime scripts.

Provides repo discovery, label bootstrap, issue fetch, and the
`rabbit-managed` safety guard. All `gh` invocations go through subprocess
so the test suite can swap `gh` for a PATH-resident shim.

Repo slug resolves to $RABBIT_ISSUE_REPO env var when set, else the
module-level const RABBIT_REPO_DEFAULT. No git remote consultation —
bugs about rabbit always go to rabbit's repo, regardless of the cwd.

Version: 1.2.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
import json
import os
import subprocess
import sys
from typing import List


RABBIT_REPO_DEFAULT = "changyu87/rabbit-workflow"


def repo_slug() -> str:
    """Return the target 'owner/repo' for all rabbit-issue gh calls.

    Resolution order (Fixes #264):
      1. RABBIT_ISSUE_REPO env var when set (fork / testing override).
      2. RABBIT_REPO_DEFAULT const declared above.

    Never consults `git remote get-url origin` — in plugin installs the
    cwd is the user's project, which silently directed bugs to the wrong
    target.
    """
    return os.environ.get("RABBIT_ISSUE_REPO") or RABBIT_REPO_DEFAULT


def ensure_labels(labels: List[str]) -> None:
    """Idempotently create labels on the active repo.

    `gh label create` exits non-zero on duplicates; that is expected and
    intentionally ignored so callers can call this on every file.
    """
    slug = repo_slug()
    for label in labels:
        subprocess.run(
            ["gh", "label", "create", label, "-R", slug],
            capture_output=True, text=True,
        )
        # Ignore non-zero — duplicate-label is the common case.


def gh_issue_view(number: int, fields: str = "number,title,state,labels,body") -> dict:
    """Return parsed issue JSON for issue #number via `gh issue view`."""
    out = subprocess.check_output(
        ["gh", "issue", "view", str(number), "-R", repo_slug(),
         "--json", fields],
        text=True,
    )
    return json.loads(out)


def gh_issue_comments(number: int) -> list:
    """Return the parsed list of comment objects for issue #number.

    Reads via `gh issue view <N> --json comments` (issue #522). The
    human-readable `gh issue view <N> --comments` view is NOT used: it
    triggers a deprecated Projects-classic `projectCards` GraphQL field
    that FAILS and returns an EMPTY body on this repo, so comments read
    as absent even when present — a silent correctness trap. The
    `--json comments` path does not touch that field.

    Returns the inner list of comment objects (each carrying at least a
    `body`), unwrapping gh's `{"comments": [...]}` envelope.
    """
    out = subprocess.check_output(
        ["gh", "issue", "view", str(number), "-R", repo_slug(),
         "--json", "comments"],
        text=True,
    )
    return json.loads(out).get("comments", [])


def require_managed(number: int) -> None:
    """Exit non-zero if issue #number lacks the `rabbit-managed` label.

    Enforces the safety invariant: rabbit's close/reopen flows refuse to
    touch human-filed issues unless explicitly opted in via the label.
    """
    issue = gh_issue_view(number, "number,labels")
    labels = {lbl["name"] for lbl in issue.get("labels", [])}
    if "rabbit-managed" not in labels:
        sys.exit(
            "rabbit-issue: #{} lacks `rabbit-managed` label; refusing to act"
            .format(number)
        )


def require_auth() -> None:
    """Exit non-zero if `gh auth status` is not green."""
    r = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if r.returncode != 0:
        sys.exit("rabbit-issue: `gh auth status` failed — run `gh auth login`")
