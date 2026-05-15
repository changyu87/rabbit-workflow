#!/usr/bin/env python3
"""Tests for make-readonly.sh and make-writable.sh. Run: python3 test/test-readonly-scripts.py"""

import os
import stat
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


# t1: make-readonly.py exists and is executable
def t1():
    path = os.path.join(REPO_ROOT, "make-readonly.py")
    if os.path.isfile(path) and os.access(path, os.X_OK):
        ok("t1: make-readonly.py exists and is executable")
    else:
        ko("t1: make-readonly.py missing or not executable")


# t2: make-writable.py exists and is executable
def t2():
    path = os.path.join(REPO_ROOT, "make-writable.py")
    if os.path.isfile(path) and os.access(path, os.X_OK):
        ok("t2: make-writable.py exists and is executable")
    else:
        ko("t2: make-writable.py missing or not executable")


# t3: make-readonly.sh removes write bit from both archive/ and test/
def t3():
    with tempfile.TemporaryDirectory() as tmp:
        archive_dir = os.path.join(tmp, "archive")
        test_dir = os.path.join(tmp, "test")
        os.makedirs(archive_dir)
        os.makedirs(test_dir)
        archive_file = os.path.join(archive_dir, "sample.txt")
        test_file = os.path.join(test_dir, "sample.sh")
        with open(archive_file, "w") as f:
            f.write("data")
        with open(test_file, "w") as f:
            f.write("data")

        env = os.environ.copy()
        env["ARCHIVE_DIR"] = archive_dir
        env["TEST_DIR"] = test_dir
        subprocess.run(
            ["python3", os.path.join(REPO_ROOT, "make-readonly.py")],
            capture_output=True,
            env=env,
        )

        archive_writable = os.access(archive_file, os.W_OK)
        test_writable = os.access(test_file, os.W_OK)

        # Restore write bits (files and dirs) before TemporaryDirectory cleanup
        for root, dirs, files in os.walk(tmp):
            for name in files + dirs:
                fp = os.path.join(root, name)
                if not os.path.islink(fp):
                    os.chmod(fp, os.stat(fp).st_mode | stat.S_IWRITE)
            if not os.path.islink(root):
                os.chmod(root, os.stat(root).st_mode | stat.S_IWRITE)

        if not archive_writable and not test_writable:
            ok("t3: make-readonly.sh removes write bit from archive/ and test/")
        else:
            ko(
                f"t3: write bit not removed "
                f"(archive writable={'yes' if archive_writable else 'no'} "
                f"test writable={'yes' if test_writable else 'no'})"
            )


# t4: make-writable.sh restores write bit
def t4():
    with tempfile.TemporaryDirectory() as tmp:
        archive_dir = os.path.join(tmp, "archive")
        test_dir = os.path.join(tmp, "test")
        os.makedirs(archive_dir)
        os.makedirs(test_dir)
        archive_file = os.path.join(archive_dir, "sample.txt")
        with open(archive_file, "w") as f:
            f.write("data")
        # Remove write bit
        os.chmod(archive_file, os.stat(archive_file).st_mode & ~stat.S_IWRITE)

        env = os.environ.copy()
        env["ARCHIVE_DIR"] = archive_dir
        env["TEST_DIR"] = test_dir
        subprocess.run(
            ["python3", os.path.join(REPO_ROOT, "make-writable.py")],
            capture_output=True,
            env=env,
        )

        if os.access(archive_file, os.W_OK):
            ok("t4: make-writable.sh restores write bit")
        else:
            ko("t4: archive/ still read-only after make-writable.sh")


print("running readonly-scripts tests")
t1()
t2()
t3()
t4()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
