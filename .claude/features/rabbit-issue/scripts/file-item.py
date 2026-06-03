#!/usr/bin/env python3
"""rabbit-issue: file a new bug or enhancement on GitHub Issues.

Prints JSON {number, url, type} to stdout on success.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gh import ensure_labels, repo_slug, require_auth  # noqa: E402

VALID_TYPES = ("bug", "enhancement")
VALID_PRIORITIES = ("low", "medium", "high", "critical")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, choices=VALID_TYPES)
    p.add_argument("--feature", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--priority", required=True, choices=VALID_PRIORITIES)
    p.add_argument("--description", required=True)
    args = p.parse_args()

    require_auth()
    labels = [
        args.type,
        "rabbit-managed",
        "feature:{}".format(args.feature),
        "priority:{}".format(args.priority),
    ]
    ensure_labels(labels)

    slug = repo_slug()
    url = subprocess.check_output(
        ["gh", "issue", "create", "-R", slug,
         "--title", args.title,
         "--body", args.description,
         "--label", ",".join(labels)],
        text=True,
    ).strip()
    number = int(url.rsplit("/", 1)[-1])
    print(json.dumps({"number": number, "url": url, "type": args.type}))


if __name__ == "__main__":
    main()
