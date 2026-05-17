#!/usr/bin/env python3
"""Tests for repo-permissions.py lock/unlock subcommands."""
import os
import stat
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPT_DIR, "..", "scripts", "repo-permissions.py")


def run(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, SCRIPT] + args,
                          capture_output=True, text=True, env=e)


def test_no_args_exits_2():
    r = run([])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_invalid_subcommand_exits_2():
    r = run(["freeze"])
    assert r.returncode == 2, f"Expected 2, got {r.returncode}"


def test_lock_removes_write():
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "file.txt")
        open(f, "w").close()
        os.chmod(f, 0o644)
        r = run(["lock"], env={"ARCHIVE_DIR": tmp, "TEST_DIR": "/nonexistent"})
        assert r.returncode == 0, f"lock failed: {r.stderr}"
        mode = os.stat(f).st_mode
        # Restore write so tempfile cleanup succeeds
        run(["unlock"], env={"ARCHIVE_DIR": tmp, "TEST_DIR": "/nonexistent"})
        assert not (mode & stat.S_IWUSR), "Write bit should be removed after lock"


def test_unlock_restores_write():
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "file.txt")
        open(f, "w").close()
        os.chmod(f, 0o444)
        r = run(["unlock"], env={"ARCHIVE_DIR": tmp, "TEST_DIR": "/nonexistent"})
        assert r.returncode == 0, f"unlock failed: {r.stderr}"
        mode = os.stat(f).st_mode
        assert mode & stat.S_IWUSR, "Write bit should be restored after unlock"


def test_missing_dir_is_noop():
    r = run(["lock"], env={"ARCHIVE_DIR": "/nonexistent", "TEST_DIR": "/nonexistent"})
    assert r.returncode == 0, f"Missing dir should be noop, got {r.returncode}"


def test_symlinks_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "real.txt")
        link = os.path.join(tmp, "link.txt")
        open(target, "w").close()
        os.symlink(target, link)
        r = run(["lock"], env={"ARCHIVE_DIR": tmp, "TEST_DIR": "/nonexistent"})
        assert r.returncode == 0
        # symlink itself should not have been chmod'd (no error)
        # Restore write so tempfile cleanup succeeds
        run(["unlock"], env={"ARCHIVE_DIR": tmp, "TEST_DIR": "/nonexistent"})


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
