#!/usr/bin/env python3
"""rabbit-issue: file a new bug or enhancement on GitHub Issues.

Prints JSON {number, url, type} to stdout on success.

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
from _gh import ensure_labels, repo_slug, require_auth  # noqa: E402

VALID_TYPES = ("bug", "enhancement")
VALID_PRIORITIES = ("low", "medium", "high", "critical")
# Provenance is a fixed enum (issue #759, coexistence step 2 of #753).
# Human is the UNTAGGED default — expressed by OMITTING --filed-by, never
# an explicit value. Only these two non-human values are accepted; any
# other value (legacy `loop`, literal `human`, or polluted/space-bearing
# strings) is rejected so malformed provenance labels can never recur.
VALID_FILED_BY = ("rabbit", "autonomous-evolve")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, choices=VALID_TYPES)
    p.add_argument("--feature", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--priority", required=True, choices=VALID_PRIORITIES)
    p.add_argument("--description", required=True)
    # Provenance (issue #759): omit for human (no label); pass `rabbit`
    # or `autonomous-evolve` for a non-human filer. Validated below so the
    # error message can name the enum.
    p.add_argument("--filed-by", default=None)
    args = p.parse_args()

    if args.filed_by is not None and args.filed_by not in VALID_FILED_BY:
        sys.exit(
            "rabbit-issue: --filed-by {!r} is not a valid provenance value; "
            "omit --filed-by for human-filed issues, or pass one of {}"
            .format(args.filed_by, " / ".join(VALID_FILED_BY))
        )

    require_auth()
    labels = [
        args.type,
        "rabbit-managed",
        "feature:{}".format(args.feature),
        "priority:{}".format(args.priority),
    ]
    if args.filed_by is not None:
        labels.append("filed-by:{}".format(args.filed_by))
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
