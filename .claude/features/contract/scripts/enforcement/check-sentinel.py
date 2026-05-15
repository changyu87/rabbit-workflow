#!/usr/bin/env python3
# check-sentinel.py — verify RABBIT-POLICY-BLOCK-v1 sentinel in dispatch scripts.
#
# Usage: check-sentinel.py <file-or-dir>
#
# If given a file: checks that file for the sentinel string.
# If given a directory: recursively finds all .py and .sh files and checks each.
# Exits 0 if all checked files contain the sentinel, 1 if any are missing it.
#
# Version: 1.0.0
# Owner: rabbit-workflow team (contract)
# Deprecation criterion: when sentinel enforcement is provided by a native linter.

import os
import sys


SENTINEL = "RABBIT-POLICY-BLOCK-v1"


def check_file(filepath):
    with open(filepath) as f:
        content = f.read()
    return SENTINEL in content


def main():
    if len(sys.argv) < 2:
        print("ERROR: usage: check-sentinel.py <file-or-dir>", file=sys.stderr)
        sys.exit(2)

    target = sys.argv[1]

    if not os.path.exists(target):
        print(f"ERROR: not a file or directory: {target}", file=sys.stderr)
        sys.exit(2)

    failed = 0

    if os.path.isfile(target):
        if not check_file(target):
            print(f"MISSING sentinel in: {target}", file=sys.stderr)
            failed = 1
    elif os.path.isdir(target):
        for dirpath, _, filenames in os.walk(target):
            for fname in filenames:
                if fname.endswith(".sh") or fname.endswith(".py"):
                    fpath = os.path.join(dirpath, fname)
                    if not check_file(fpath):
                        print(f"MISSING sentinel in: {fpath}", file=sys.stderr)
                        failed = 1
    else:
        print(f"ERROR: not a file or directory: {target}", file=sys.stderr)
        sys.exit(2)

    sys.exit(failed)


if __name__ == "__main__":
    main()
