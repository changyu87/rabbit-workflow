#!/usr/bin/env python3
"""test-producers-read-file.py — exercises the read-file producer:
returns the raw contents of the file pointed to by its `path` arg,
honoring the module-level path-resolution convention.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib import producers  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: read-file returns raw contents (feature-dir-relative path)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(feat, "blob.txt")
    with open(target, "w") as f:
        f.write("hello world\n")
    out = producers.call_producer(
        "read-file", {"path": "blob.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "hello world\n":
        fail(f"t1: read-file output mismatch: {out!r}")
    else:
        ok("t1: read-file returns raw contents for feature-dir-relative path")

# t2: read-file handles repo-root-relative path (".claude/" prefix)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    repo_target = os.path.join(root, ".claude", "shared.txt")
    os.makedirs(os.path.dirname(repo_target))
    with open(repo_target, "w") as f:
        f.write("repo-rooted\n")
    out = producers.call_producer(
        "read-file", {"path": ".claude/shared.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "repo-rooted\n":
        fail(f"t2: read-file repo-root-relative output mismatch: {out!r}")
    else:
        ok("t2: read-file resolves '.claude/'-prefixed path repo-root-relative")

# t3: missing file raises FileNotFoundError
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    try:
        producers.call_producer(
            "read-file", {"path": "missing.txt"},
            feature_dir=feat, repo_root=root,
        )
        fail("t3: expected FileNotFoundError, got success")
    except FileNotFoundError:
        ok("t3: read-file raises FileNotFoundError on missing path")

if FAIL:
    print("test-producers-read-file: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-read-file: all checks passed.")
