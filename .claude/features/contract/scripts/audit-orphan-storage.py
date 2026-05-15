#!/usr/bin/env python3
# audit-orphan-storage.py — scan .claude/bugs/ and .claude/backlogs/ for
# subdirectory names not present in registry.json features; alert on orphans.
#
# Usage:
#   audit-orphan-storage.py --registry <path> --bugs-root <path> --backlogs-root <path>
#   audit-orphan-storage.py <registry> <bugs-root> <backlogs-root>   (legacy positional)
#
# Exit codes:
#   0  no orphans found
#   1  one or more orphans found
#
# Version: 1.1.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when feature registry lookup is natively provided.

import json
import os
import sys


def main():
    args = sys.argv[1:]

    # Flag-based interface
    if args and args[0].startswith("--"):
        registry_path = ""
        bugs_root = ""
        backlogs_root = ""
        while args:
            a = args[0]
            if a == "--registry":
                registry_path = args[1] if len(args) > 1 else ""
                args = args[2:]
            elif a == "--bugs-root":
                bugs_root = args[1] if len(args) > 1 else ""
                args = args[2:]
            elif a == "--backlogs-root":
                backlogs_root = args[1] if len(args) > 1 else ""
                args = args[2:]
            else:
                print(f"ERROR: unknown arg: {a}", file=sys.stderr)
                sys.exit(2)
        if not registry_path:
            print("ERROR: --registry required", file=sys.stderr)
            sys.exit(2)
    else:
        # Legacy positional form
        if len(args) != 3:
            print("usage: audit-orphan-storage.py --registry <path> --bugs-root <path> --backlogs-root <path>", file=sys.stderr)
            sys.exit(2)
        registry_path = args[0]
        bugs_root = args[1]
        backlogs_root = args[2]

    with open(registry_path) as f:
        r = json.load(f)
    known_features = set(r.get('features', {}).keys())

    orphan_found = False

    def check_dir(root, label):
        nonlocal orphan_found
        if not os.path.isdir(root):
            print(f"INFO  {label}/ (directory does not exist)")
            return
        for name in sorted(os.listdir(root)):
            subdir = os.path.join(root, name)
            if not os.path.isdir(subdir):
                continue
            if name not in known_features:
                print(f"ORPHAN  {label}/{name}/")
                orphan_found = True

    check_dir(bugs_root, "bugs")
    check_dir(backlogs_root, "backlogs")

    # Report known features with no bugs subdir
    for feature in sorted(known_features):
        if not os.path.isdir(os.path.join(bugs_root, feature)):
            print(f"INFO  bugs/{feature}/ (never filed)")

    sys.exit(1 if orphan_found else 0)


if __name__ == '__main__':
    main()
