#!/usr/bin/env python3
"""rabbit-issue: list issues with type / feature / status filters.

Output is sorted by issue number ascending so downstream callers can
diff/grep deterministically.

Version: 1.0.0
Owner: cyxu
Deprecation criterion: when rabbit-issue is retired
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import repo_slug, require_auth  # noqa: E402

VALID_TYPES = ("bug", "enhancement", "all")
VALID_STATES = ("open", "closed", "all")


def _label_value(issue: dict, prefix: str) -> str:
    for lbl in issue.get("labels", []):
        if lbl["name"].startswith(prefix):
            return lbl["name"][len(prefix):]
    return ""


def _issue_type(issue: dict) -> str:
    names = {lbl["name"] for lbl in issue.get("labels", [])}
    if "bug" in names:
        return "bug"
    if "enhancement" in names:
        return "enhancement"
    return "?"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", default="all", choices=VALID_TYPES)
    p.add_argument("--feature", default="")
    p.add_argument("--status", default="open", choices=VALID_STATES)
    args = p.parse_args()

    require_auth()

    cmd = ["gh", "issue", "list", "-R", repo_slug(),
           "--label", "rabbit-managed",
           "--state", args.status,
           "--limit", "500",
           "--json", "number,title,state,labels"]
    if args.type != "all":
        cmd += ["--label", args.type]
    if args.feature:
        cmd += ["--label", "feature:{}".format(args.feature)]

    out = subprocess.check_output(cmd, text=True)
    issues = json.loads(out)
    issues.sort(key=lambda i: i["number"])
    for i in issues:
        feature = _label_value(i, "feature:")
        priority = _label_value(i, "priority:")
        print("#{}  [{}]  [{}]  [{}]  feature:{}  {}".format(
            i["number"], _issue_type(i), i["state"], priority, feature, i["title"]
        ))


if __name__ == "__main__":
    main()
