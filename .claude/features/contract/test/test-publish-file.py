#!/usr/bin/env python3
"""test-publish-file.py — exercises publish_file: idempotent file copy from
feature-dir-relative source to repo-root-relative destination.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.publish import publish_file  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: basic copy — destination created, content matches source
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "scripts"))
    os.makedirs(root)
    src = os.path.join(feat, "scripts", "myscript.py")
    with open(src, "w") as f:
        f.write("# hello\n")
    r = publish_file("scripts/myscript.py", ".claude/hooks/myscript.py",
                     feature_dir=feat, repo_root=root)
    dest = os.path.join(root, ".claude", "hooks", "myscript.py")
    if not r.passed:
        fail(f"t1: publish_file failed: {r.messages}")
    elif not os.path.isfile(dest):
        fail("t1: destination file not created")
    elif open(dest).read() != "# hello\n":
        fail("t1: destination content mismatch")
    else:
        ok("t1: basic copy creates destination with correct content")

# t2: idempotent — same content returns 'no-op' in messages
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "src"))
    os.makedirs(os.path.join(root, ".claude"))
    src = os.path.join(feat, "src", "a.txt")
    dest = os.path.join(root, ".claude", "a.txt")
    with open(src, "w") as f:
        f.write("abc")
    with open(dest, "w") as f:
        f.write("abc")
    r = publish_file("src/a.txt", ".claude/a.txt", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t2: idempotent call failed: {r.messages}")
    elif not any("no-op" in m.lower() for m in r.messages):
        fail(f"t2: idempotent call should report 'no-op' in messages, got: {r.messages}")
    else:
        ok("t2: idempotent: same content returns no-op result")

# t3: drift — changed source overwrites destination
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "src"))
    os.makedirs(os.path.join(root, ".claude"))
    src = os.path.join(feat, "src", "a.txt")
    dest = os.path.join(root, ".claude", "a.txt")
    with open(src, "w") as f:
        f.write("new-content")
    with open(dest, "w") as f:
        f.write("old-content")
    r = publish_file("src/a.txt", ".claude/a.txt", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t3: drift copy failed: {r.messages}")
    elif open(dest).read() != "new-content":
        fail("t3: drift copy did not update destination")
    else:
        ok("t3: drift: changed source overwrites destination")

# t4: missing source → CheckResult(passed=False) with descriptive message
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = publish_file("nonexistent.txt", "out.txt", feature_dir=feat, repo_root=root)
    if r.passed:
        fail("t4: missing source should return passed=False")
    elif not any(
        word in " ".join(r.messages).lower()
        for word in ("source", "not found", "missing")
    ):
        fail(f"t4: error message doesn't mention source: {r.messages}")
    else:
        ok("t4: missing source returns passed=False with descriptive message")

# t5: destination parent directories created automatically
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(os.path.join(feat, "f"))
    os.makedirs(root)
    with open(os.path.join(feat, "f", "x.md"), "w") as f:
        f.write("hi")
    r = publish_file("f/x.md", "a/b/c/x.md", feature_dir=feat, repo_root=root)
    if not r.passed:
        fail(f"t5: deep destination failed: {r.messages}")
    elif not os.path.isfile(os.path.join(root, "a", "b", "c", "x.md")):
        fail("t5: deep destination not created")
    else:
        ok("t5: destination parent directories created automatically")

if FAIL:
    print("test-publish-file: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-publish-file: all checks passed.")
