#!/usr/bin/env python3
# make-writable.py — restore owner write permission to archive/ and test/.
# Skips symlinks. Honors ARCHIVE_DIR and TEST_DIR env vars for testing.

import os
import stat
import sys


def unlock(directory):
    if not os.path.isdir(directory):
        return
    for root, dirs, files in os.walk(directory):
        for name in files + dirs:
            path = os.path.join(root, name)
            if os.path.islink(path):
                continue
            current = os.stat(path).st_mode
            os.chmod(path, current | stat.S_IWUSR)
        if not os.path.islink(root):
            current = os.stat(root).st_mode
            os.chmod(root, current | stat.S_IWUSR)
    print(f"writable: {directory}/")


def main():
    archive_dir = os.environ.get("ARCHIVE_DIR", "archive")
    test_dir = os.environ.get("TEST_DIR", "test")
    unlock(archive_dir)
    unlock(test_dir)


if __name__ == "__main__":
    main()
