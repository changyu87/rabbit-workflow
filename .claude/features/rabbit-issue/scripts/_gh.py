"""Shared helpers for rabbit-issue runtime scripts.

Provides repo discovery, label bootstrap, issue fetch, and the
`rabbit-managed` safety guard. All `gh` invocations go through subprocess
so the test suite can swap `gh` for a PATH-resident shim.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
import json
import re
import subprocess
import sys
from typing import List


_GITHUB_REMOTE_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)([^/]+)/(.+?)(?:\.git)?$"
)


def repo_slug() -> str:
    """Return 'owner/repo' parsed from `git remote get-url origin`.

    Exits with an actionable error if the remote is not a GitHub URL.
    """
    url = subprocess.check_output(
        ["git", "remote", "get-url", "origin"], text=True
    ).strip()
    m = _GITHUB_REMOTE_RE.match(url)
    if not m:
        sys.exit(
            "rabbit-issue: `origin` is not a GitHub URL: {}".format(url)
        )
    return "{}/{}".format(m.group(1), m.group(2))


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
