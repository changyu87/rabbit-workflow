#!/usr/bin/env python3
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
    has_filters = bool(type_filter or args.feature or args.status)

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
        if has_filters:
            print("No items found.")
        else:
            print("No items filed yet. Use /rabbit-file file bug or /rabbit-file file backlog.")
        return

    for item in items:
        name = item.get("name", "?")
        type_ = item.get("type", "?")
        status = item.get("status", "?")
        priority = item.get("priority", "?")
        title = item.get("title", "?")
        print(f"{name}  [{type_}]  [{status}]  [{priority}]  {title}")


if __name__ == "__main__":
    main()
