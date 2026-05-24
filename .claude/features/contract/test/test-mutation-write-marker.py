#!/usr/bin/env python3
"""test-mutation-write-marker.py — exercises write_marker: idempotent
creation of a marker file (path relative to repo_root) with given content.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.mutation import write_marker  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: create marker with content (fresh)
with tempfile.TemporaryDirectory() as root:
    r = write_marker(".my-marker", "session", repo_root=root)
    dest = os.path.join(root, ".my-marker")
    if not r.passed:
        fail(f"t1: write_marker failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: marker file not created")
    elif open(dest).read() != "session":
        fail(f"t1: marker content mismatch: {open(dest).read()!r}")
    else:
        ok("t1: write_marker creates marker file with given content")

# t2: idempotent — second call with same content is no-op
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "x", repo_root=root)
    r = write_marker(".m", "x", repo_root=root)
    if not r.passed:
        fail(f"t2: second call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: second call should report 'no-op', got: {r.messages}")
    else:
        ok("t2: idempotent — same content returns no-op")

# t3: content change — second call with different content overwrites
with tempfile.TemporaryDirectory() as root:
    write_marker(".m", "old", repo_root=root)
    r = write_marker(".m", "new", repo_root=root)
    dest = os.path.join(root, ".m")
    if not r.passed:
        fail(f"t3: overwrite failed: {r.messages}")
    elif open(dest).read() != "new":
        fail(f"t3: overwrite did not update content: {open(dest).read()!r}")
    else:
        ok("t3: changed content overwrites marker")

# t4: nested path — parent dirs created automatically
with tempfile.TemporaryDirectory() as root:
    r = write_marker("a/b/.deep-marker", "y", repo_root=root)
    dest = os.path.join(root, "a", "b", ".deep-marker")
    if not r.passed:
        fail(f"t4: nested path failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t4: nested marker not created")
    else:
        ok("t4: parent directories created automatically")

# t5: empty content allowed
with tempfile.TemporaryDirectory() as root:
    r = write_marker(".empty", "", repo_root=root)
    dest = os.path.join(root, ".empty")
    if not r.passed:
        fail(f"t5: empty content failed: {r.messages}")
    elif open(dest).read() != "":
        fail(f"t5: empty marker has content: {open(dest).read()!r}")
    else:
        ok("t5: empty content allowed")

if FAIL:
    print("test-mutation-write-marker: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-mutation-write-marker: all checks passed.")
