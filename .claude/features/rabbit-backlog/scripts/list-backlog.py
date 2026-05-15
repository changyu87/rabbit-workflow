#!/usr/bin/env python3
# list-backlog.py -- list backlog items from centralized .claude/backlogs/ storage.
#
# Usage:
#   list-backlog.py                                # all items, JSON array
#   list-backlog.py --status open|in-progress|implemented|refused|reopened
#   list-backlog.py --feature NAME[,NAME2]         # only named features
#   list-backlog.py --text                         # human-readable: NAME  [STATUS]  [PRIORITY]  TITLE per line
#   list-backlog.py -h|--help
#
# Algorithm:
#   1. Find REPO_ROOT (RABBIT_ROOT or git)
#   2. Find all subdirectories under $REPO_ROOT/.claude/backlogs/ (one level deep)
#   3. Each subdir is a feature bucket; collect all item.json files from each
#   4. Apply --feature filter by matching subdir name
#   5. Apply --status filter
#   6. Output JSON array or text
#
# Exit: 0 on success, 2 on usage error.

import sys
import os
import json
import subprocess


USAGE = """\
usage:
  list-backlog.py                                # all items, JSON array
  list-backlog.py --status open|in-progress|implemented|refused|reopened
  list-backlog.py --feature NAME[,NAME2]         # only named features
  list-backlog.py --text                         # human-readable output
  list-backlog.py -h|--help
"""


def git_toplevel():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def main():
    rabbit_root = os.environ.get("RABBIT_ROOT", "")
    if rabbit_root:
        repo_root = rabbit_root
    else:
        repo_root = git_toplevel()
        if not repo_root:
            print("error: cannot determine repo root", file=sys.stderr)
            sys.exit(1)

    mode = "json"
    filter_status = ""
    filter_features = []

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--status":
            if i + 1 >= len(args):
                print("error: --status requires a value", file=sys.stderr)
                sys.exit(2)
            filter_status = args[i + 1]
            i += 2
        elif args[i] == "--feature":
            if i + 1 >= len(args):
                print("error: --feature requires a value", file=sys.stderr)
                sys.exit(2)
            filter_features = [f.strip() for f in args[i + 1].split(",") if f.strip()]
            i += 2
        elif args[i] == "--text":
            mode = "text"
            i += 1
        elif args[i] in ("-h", "--help"):
            print(USAGE, end="")
            sys.exit(0)
        else:
            print(f"unknown arg: {args[i]}", file=sys.stderr)
            sys.exit(2)

    backlogs_root = os.path.join(repo_root, ".claude", "backlogs")

    # Collect all item.json paths
    item_paths = []
    if os.path.isdir(backlogs_root):
        for bucket_name in sorted(os.listdir(backlogs_root)):
            bucket_dir = os.path.join(backlogs_root, bucket_name)
            if not os.path.isdir(bucket_dir):
                continue
            if filter_features and bucket_name not in filter_features:
                continue
            for item_name in sorted(os.listdir(bucket_dir)):
                item_dir = os.path.join(bucket_dir, item_name)
                item_json = os.path.join(item_dir, "item.json")
                if os.path.isfile(item_json):
                    item_paths.append(item_json)

    if not item_paths:
        if mode == "text":
            print("(no items)")
        else:
            print("[]")
        sys.exit(0)

    # Load and optionally filter items
    items = []
    for path in item_paths:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        if filter_status and data.get("status") != filter_status:
            continue
        items.append(data)

    if not items:
        if mode == "text":
            print("(no items match)")
        else:
            print("[]")
        sys.exit(0)

    if mode == "text":
        for item in items:
            name = item.get("name", "")
            status = item.get("status", "")
            priority = item.get("priority", "")
            title = item.get("title", "")
            print(f"{name}  [{status}]  [{priority}]  {title}")
    else:
        print(json.dumps(items, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
