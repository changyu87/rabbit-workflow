#!/usr/bin/env python3
# list-bugs.py -- list bugs from centralized .claude/bugs/ storage.
#
# Usage:
#   list-bugs.py                         # all bugs, JSON array
#   list-bugs.py --status open|closed|reopened|refused
#   list-bugs.py --feature NAME[,NAME2]  # only named features
#   list-bugs.py --text                  # human-readable: NAME  [STATUS]  TITLE per line
#   list-bugs.py -h|--help
#
# Algorithm:
#   1. Find REPO_ROOT (git or RABBIT_ROOT)
#   2. Find all subdirectories under $REPO_ROOT/.claude/bugs/ (one level deep)
#   3. Each subdir is a feature bucket; collect all bug.json files from each
#   4. Apply --feature filter by matching subdir name
#   5. Apply --status filter
#   6. Output JSON array or text
#
# Exit: 0 on success.

import json
import os
import subprocess
import sys
from pathlib import Path


def get_repo_root():
    rabbit_root = os.environ.get("RABBIT_ROOT", "")
    if rabbit_root:
        return rabbit_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("error: cannot determine repo root", file=sys.stderr)
        sys.exit(1)


def main():
    args = sys.argv[1:]

    mode = "json"
    filter_status = ""
    filter_features = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--status":
            if i + 1 >= len(args):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            filter_status = args[i + 1]; i += 2
        elif a == "--feature":
            if i + 1 >= len(args):
                print(f"unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
            parts = args[i + 1].split(",")
            filter_features.extend(p for p in parts if p)
            i += 2
        elif a == "--text":
            mode = "text"; i += 1
        elif a in ("-h", "--help"):
            # Print usage comment block (lines 4-15)
            lines = [
                "Usage:",
                "  list-bugs.py                         # all bugs, JSON array",
                "  list-bugs.py --status open|closed|reopened|refused",
                "  list-bugs.py --feature NAME[,NAME2]  # only named features",
                "  list-bugs.py --text                  # human-readable: NAME  [STATUS]  TITLE per line",
                "  list-bugs.py -h|--help",
            ]
            print("\n".join(lines))
            sys.exit(0)
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            sys.exit(2)

    repo_root = get_repo_root()
    bugs_root = Path(repo_root) / ".claude" / "bugs"

    bug_files = []
    if bugs_root.is_dir():
        for bucket_dir in sorted(bugs_root.iterdir()):
            if not bucket_dir.is_dir():
                continue
            bucket_name = bucket_dir.name
            if filter_features and bucket_name not in filter_features:
                continue
            for d in sorted(bucket_dir.iterdir()):
                bug_json = d / "bug.json"
                if bug_json.is_file():
                    bug_files.append(bug_json)

    if not bug_files:
        if mode == "text":
            print("(no bugs)")
        else:
            print("[]")
        sys.exit(0)

    bugs = []
    for f in bug_files:
        try:
            data = json.loads(f.read_text())
            bugs.append(data)
        except Exception:
            pass

    if filter_status:
        bugs = [b for b in bugs if b.get("status") == filter_status]

    if mode == "text":
        if not bugs:
            print("(no bugs match)")
        else:
            for b in bugs:
                name = b.get("name", "")
                status = b.get("status", "")
                severity = b.get("severity", "")
                title = b.get("title", "")
                print(f"{name}  [{status}]  [{severity}]  {title}")
    else:
        print(json.dumps(bugs, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
