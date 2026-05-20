#!/usr/bin/env python3
"""list-items.py — list items from origin/bug-backlog-files.

Version: 0.3.0
Owner: rabbit-workflow team
Deprecation criterion: when a unified tracking system replaces file-based bug and backlog management
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import branch_ops

VALID_TYPES = {"bug", "backlog", "all"}
VALID_STATUSES = {"open", "close"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", dest="type_", default="all", choices=sorted(VALID_TYPES))
    p.add_argument("--feature")
    p.add_argument("--status", choices=sorted(VALID_STATUSES))
    args = p.parse_args()

    type_filter = None if args.type_ == "all" else args.type_

    # BUG-28: distinguish 'branch does not exist' from 'branch exists but
    # no items match filters' — they are operationally distinct conditions.
    try:
        if not branch_ops.branch_exists():
            print(
                "No items filed yet (origin/bug-backlog-files does not exist). "
                "Run python3 .claude/features/rabbit-file/scripts/file-item.py "
                "to file the first item."
            )
            return
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        items = branch_ops.read_branch(
            feature=args.feature,
            type_=type_filter,
            status=args.status,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not items:
        print("No items found.")
        return

    # BUG-30: deterministic order — sort by name (ID string).
    items_sorted = sorted(items, key=lambda i: i.get("name", ""))
    for item in items_sorted:
        name = item.get("name", "?")
        type_ = item.get("type", "?")
        status = item.get("status", "?")
        priority = item.get("priority", "?")
        title = item.get("title", "?")
        print(f"{name}  [{type_}]  [{status}]  [{priority}]  {title}")


if __name__ == "__main__":
    main()
