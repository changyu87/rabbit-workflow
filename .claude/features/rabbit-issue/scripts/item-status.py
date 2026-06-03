#!/usr/bin/env python3
"""rabbit-issue: show / close / reopen a GitHub issue.

Subcommands:
  show   <N>                              — print issue JSON
  close  <N> --reason {completed,not-planned} [--comment <c>]
  reopen <N> [--comment <c>]

`close` and `reopen` enforce the `rabbit-managed` safety guard before
issuing the gh command.

Version: 1.0.1
Owner: cyxu
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
    require_auth,
    require_managed,
)

VALID_REASONS = ("completed", "not-planned")
SHOW_FIELDS = "number,title,state,stateReason,labels,body,createdAt,closedAt"


def cmd_show(args: argparse.Namespace) -> None:
    issue = gh_issue_view(args.number, SHOW_FIELDS)
    print(json.dumps(issue, indent=2))


def cmd_close(args: argparse.Namespace) -> None:
    require_managed(args.number)
    # argparse accepts the hyphen form (Python/shell-friendly), but
    # `gh issue close --reason` only accepts "completed" or "not planned"
    # (with a space). Translate at the gh boundary (issue #419). Only
    # "not-planned" needs translation; "completed" is unchanged.
    reason = args.reason.replace("-", " ")
    cmd = ["gh", "issue", "close", str(args.number),
           "-R", repo_slug(), "--reason", reason]
    if args.comment:
        cmd += ["--comment", args.comment]
    subprocess.run(cmd, check=True)


def cmd_reopen(args: argparse.Namespace) -> None:
    require_managed(args.number)
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

    r = sub.add_parser("reopen")
    r.add_argument("number", type=int)
    r.add_argument("--comment", default="")

    args = p.parse_args()
    require_auth()
    {"show": cmd_show, "close": cmd_close, "reopen": cmd_reopen}[args.cmd](args)


if __name__ == "__main__":
    main()
