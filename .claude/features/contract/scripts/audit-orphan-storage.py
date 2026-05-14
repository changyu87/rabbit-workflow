#!/usr/bin/env python3
# audit-orphan-storage.py — scan .claude/bugs/ and .claude/backlogs/ for
# subdirectory names not present in registry.json features; alert on orphans.
#
# Usage (invoked by audit-orphan-storage.sh):
#   python3 audit-orphan-storage.py <registry> <bugs-root> <backlogs-root>
#
# Exit codes:
#   0  no orphans found
#   1  one or more orphans found
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when feature registry lookup is natively provided.

import json
import os
import sys


def main():
    if len(sys.argv) != 4:
        print("usage: audit-orphan-storage.py <registry> <bugs-root> <backlogs-root>", file=sys.stderr)
        sys.exit(2)

    registry_path = sys.argv[1]
    bugs_root = sys.argv[2]
    backlogs_root = sys.argv[3]

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
