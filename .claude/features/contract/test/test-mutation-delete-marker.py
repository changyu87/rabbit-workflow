#!/usr/bin/env python3
"""test-mutation-delete-marker.py — exercises delete_marker: idempotent
removal of a marker file (no-op if already absent).
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import delete_marker, write_marker  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: delete existing marker
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "x", repo_root=root)
    r = delete_marker(".m", repo_root=root)
    if not r.passed:
        fail(f"t1: delete failed: {r.messages}")
    elif os.path.exists(os.path.join(root, ".m")):
        fail("t1: marker still exists after delete")
    else:
        ok("t1: existing marker is removed")

# t2: idempotent — delete absent marker is no-op
with tempfile.TemporaryDirectory() as root:
    r = delete_marker(".never-existed", repo_root=root)
    if not r.passed:
        fail(f"t2: absent delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: absent delete should report 'no-op', got: {r.messages}")
    else:
        ok("t2: idempotent — delete of absent marker is no-op")

# t3: two deletes in a row — second is no-op
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "x", repo_root=root)
    delete_marker(".m", repo_root=root)
    r = delete_marker(".m", repo_root=root)
    if not r.passed:
        fail(f"t3: second delete failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t3: second delete should report 'no-op', got: {r.messages}")
    else:
        ok("t3: second consecutive delete is no-op")

# t4: nested path delete works
with tempfile.TemporaryDirectory() as root:
    write_marker("a/b/.m", "x", repo_root=root)
    r = delete_marker("a/b/.m", repo_root=root)
    if not r.passed:
        fail(f"t4: nested delete failed: {r.messages}")
    elif os.path.exists(os.path.join(root, "a", "b", ".m")):
        fail("t4: nested marker still exists")
    else:
        ok("t4: nested-path delete works")

if FAIL:
    print("test-mutation-delete-marker: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-delete-marker: all checks passed.")
