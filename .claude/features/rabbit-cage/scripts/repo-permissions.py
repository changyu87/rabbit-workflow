#!/usr/bin/env python3
# repo-permissions.py — lock or unlock owner write permission on archive/ and test/.
#
# Usage:
#   repo-permissions.py lock    — remove write permission (run after git clone)
#   repo-permissions.py unlock  — restore write permission (run before edits)
#
# Honors ARCHIVE_DIR and TEST_DIR env vars for testing.
# Skips symlinks.

import os
import stat
import sys


def _chmod_tree(directory, add_write):
    if not os.path.isdir(directory):
        return
    for root, dirs, files in os.walk(directory):
        for name in files + dirs:
            path = os.path.join(root, name)
            if os.path.islink(path):
                continue
            mode = os.stat(path).st_mode
            os.chmod(path, mode | stat.S_IWUSR if add_write else mode & ~stat.S_IWUSR)
        if not os.path.islink(root):
            mode = os.stat(root).st_mode
            os.chmod(root, mode | stat.S_IWUSR if add_write else mode & ~stat.S_IWUSR)
    label = "writable" if add_write else "read-only"
    print(f"{label}: {directory}/")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("lock", "unlock"):
        sys.stderr.write("usage: repo-permissions.py lock|unlock\n")
        sys.exit(2)

    add_write = sys.argv[1] == "unlock"
    archive_dir = os.environ.get("ARCHIVE_DIR", "archive")
    test_dir = os.environ.get("TEST_DIR", "test")
    _chmod_tree(archive_dir, add_write)
    _chmod_tree(test_dir, add_write)


if __name__ == "__main__":
    main()
