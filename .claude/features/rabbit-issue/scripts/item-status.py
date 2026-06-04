#!/usr/bin/env python3
"""rabbit-issue: show / close / reopen a GitHub issue.

Subcommands:
  show   <N>                              — print issue JSON
  close  <N> --reason completed   --commit-sha <sha> [--comment <c>]
  close  <N> --reason not-planned --reason-text <text> [--comment <c>]
  reopen <N> [--comment <c>]

`close` and `reopen` enforce the actionability safety guard (the issue
must carry a valid `feature:` label) before issuing the gh command.

The two close reasons are gated so a closure asserts something real
(issue #423):
  - `completed` requires `--commit-sha <sha>` that resolves to a real
    commit in the local git repo — "completed" can only be claimed when
    work actually landed.
  - `not-planned` requires `--reason-text <text>` of at least 50 chars
    that is free of banned boilerplate phrases — a deliberate, specific
    justification, not a reflexive deferral.

Version: 1.2.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import (  # noqa: E402
    gh_issue_view,
    repo_slug,
    require_actionable,
    require_auth,
)

VALID_REASONS = ("completed", "not-planned")
SHOW_FIELDS = "number,title,state,stateReason,labels,body,createdAt,closedAt"

# Minimum length for a not-planned justification (issue #423 Part D).
REASON_MIN_LEN = 50

# Boilerplate that signals a reflexive deferral rather than a real
# justification. Matched case-insensitively as substrings of --reason-text.
BANNED_PHRASES = (
    "too risky",
    "out of scope",
    "out-of-scope",
    "declined autonomous dispatch",
    "not now",
    "later",
    "don't want",
    "do not want",
)


def cmd_show(args: argparse.Namespace) -> None:
    issue = gh_issue_view(args.number, SHOW_FIELDS)
    print(json.dumps(issue, indent=2))


def _validate_commit_sha(sha: str) -> None:
    """Exit non-zero unless `sha` resolves to a commit in the local repo."""
    r = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "{}^{{commit}}".format(sha)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(
            "rabbit-issue: --commit-sha {!r} does not resolve to a commit in "
            "the local git repo; `completed` requires a real landed commit"
            .format(sha)
        )


def _validate_reason_text(text: str) -> None:
    """Exit non-zero unless `text` is a specific, non-boilerplate reason."""
    if len(text) < REASON_MIN_LEN:
        sys.exit(
            "rabbit-issue: --reason-text must be at least {} characters "
            "(got {}); state a specific reason for not-planned closure"
            .format(REASON_MIN_LEN, len(text))
        )
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            sys.exit(
                "rabbit-issue: --reason-text contains banned boilerplate "
                "{!r}; give a specific, concrete justification".format(phrase)
            )


def cmd_close(args: argparse.Namespace) -> None:
    # Safety boundary first: refuse to act on non-actionable issues.
    require_actionable(args.number)

    # Then gate the close reason before the gh call (issue #423).
    if args.reason == "completed":
        if not args.commit_sha:
            sys.exit(
                "rabbit-issue: `--reason completed` requires --commit-sha "
                "<sha>; a completed closure must point at a real commit"
            )
        _validate_commit_sha(args.commit_sha)
    else:  # not-planned
        if not args.reason_text:
            sys.exit(
                "rabbit-issue: `--reason not-planned` requires --reason-text "
                "<text> (>= {} chars, no boilerplate)".format(REASON_MIN_LEN)
            )
        _validate_reason_text(args.reason_text)

    # Persist the validated not-planned justification as the close comment
    # (issue #476). The text was being validated then dropped, leaving the
    # closed issue with no audit trail. When --comment is also supplied the
    # reason-text leads, separated from the comment by a blank line.
    comment = args.comment
    if args.reason == "not-planned":
        comment = (
            "{}\n\n{}".format(args.reason_text, args.comment)
            if args.comment else args.reason_text
        )

    # argparse accepts the hyphen form (Python/shell-friendly), but
    # `gh issue close --reason` only accepts "completed" or "not planned"
    # (with a space). Translate at the gh boundary (issue #419). Only
    # "not-planned" needs translation; "completed" is unchanged.
    reason = args.reason.replace("-", " ")
    cmd = ["gh", "issue", "close", str(args.number),
           "-R", repo_slug(), "--reason", reason]
    if comment:
        cmd += ["--comment", comment]
    subprocess.run(cmd, check=True)


def cmd_reopen(args: argparse.Namespace) -> None:
    require_actionable(args.number)
    cmd = ["gh", "issue", "reopen", str(args.number), "-R", repo_slug()]
    if args.comment:
        cmd += ["--comment", args.comment]
    subprocess.run(cmd, check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show")
    s.add_argument("number", type=int)

    c = sub.add_parser("close")
    c.add_argument("number", type=int)
    c.add_argument("--reason", required=True, choices=VALID_REASONS)
    c.add_argument("--comment", default="")
    # Gating args (issue #423); required-ness is enforced per-reason in
    # cmd_close so the error message can name the reason it applies to.
    c.add_argument("--commit-sha", default="",
                   help="required with --reason completed; must be a real "
                        "commit in the local git repo")
    c.add_argument("--reason-text", default="",
                   help="required with --reason not-planned; >= {} chars, "
                        "no boilerplate".format(REASON_MIN_LEN))

    r = sub.add_parser("reopen")
    r.add_argument("number", type=int)
    r.add_argument("--comment", default="")

    args = p.parse_args()
    require_auth()
    {"show": cmd_show, "close": cmd_close, "reopen": cmd_reopen}[args.cmd](args)


if __name__ == "__main__":
    main()
