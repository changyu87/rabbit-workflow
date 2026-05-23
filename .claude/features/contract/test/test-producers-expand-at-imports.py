#!/usr/bin/env python3
"""test-producers-expand-at-imports.py — exercises the expand-at-imports
producer: reads `file`, expands each line of the form `@<path>` (one path
per line, no whitespace inside the path) into the contents of <path>.
Expansion is one level only — imported content is not recursively
re-scanned. Mirrors Claude Code's @-import semantics.
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


# t1: single @-import line is replaced with referenced file contents
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    inner = os.path.join(feat, "inner.txt")
    with open(inner, "w") as f:
        f.write("INNER\n")
    outer = os.path.join(feat, "outer.txt")
    with open(outer, "w") as f:
        f.write("@inner.txt\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "outer.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "INNER\n":
        fail(f"t1: single-import expansion mismatch: {out!r}")
    else:
        ok("t1: single @-import line is replaced with imported file contents")

# t2: non-import lines pass through unchanged; mixed content composes correctly
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "a.md"), "w") as f:
        f.write("A-content\n")
    with open(os.path.join(feat, "b.md"), "w") as f:
        f.write("B-content\n")
    with open(os.path.join(feat, "doc.md"), "w") as f:
        f.write("# Title\n\n@a.md\n\nMiddle prose.\n\n@b.md\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "doc.md"},
        feature_dir=feat, repo_root=root,
    )
    expected = "# Title\n\nA-content\n\nMiddle prose.\n\nB-content\n"
    if out != expected:
        fail(f"t2: mixed content output mismatch.\nexpected={expected!r}\nactual={out!r}")
    else:
        ok("t2: non-import lines pass through; imports interpolated in place")

# t3: expansion is one level only — imported file's own @-imports are NOT expanded
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "leaf.txt"), "w") as f:
        f.write("LEAF\n")
    with open(os.path.join(feat, "mid.txt"), "w") as f:
        f.write("@leaf.txt\n")  # contains a nested import
    with open(os.path.join(feat, "top.txt"), "w") as f:
        f.write("@mid.txt\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "top.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "@leaf.txt\n":
        fail(f"t3: expected one-level expansion, got: {out!r}")
    else:
        ok("t3: expansion is one level only — nested @-imports stay literal")

# t4: lines that look @-like but contain whitespace are NOT treated as imports
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "doc.txt"), "w") as f:
        f.write("See @some/path for details.\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "doc.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "See @some/path for details.\n":
        fail(f"t4: line with embedded @ should be unchanged, got: {out!r}")
    else:
        ok("t4: in-prose @-references are not expanded (require bare @path line)")

# t5: imported file without trailing newline is normalized (appends \n)
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    with open(os.path.join(feat, "noeol.txt"), "w") as f:
        f.write("no-trailing-newline")  # no \n
    with open(os.path.join(feat, "top.txt"), "w") as f:
        f.write("@noeol.txt\nafter\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "top.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "no-trailing-newline\nafter\n":
        fail(f"t5: trailing newline not normalized: {out!r}")
    else:
        ok("t5: imported file without trailing newline gets one appended")

# t6: import path with .claude/ prefix resolves repo-root-relative
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    rooted = os.path.join(root, ".claude", "shared.md")
    os.makedirs(os.path.dirname(rooted))
    with open(rooted, "w") as f:
        f.write("SHARED\n")
    with open(os.path.join(feat, "doc.txt"), "w") as f:
        f.write("@.claude/shared.md\n")
    out = producers.call_producer(
        "expand-at-imports", {"file": "doc.txt"},
        feature_dir=feat, repo_root=root,
    )
    if out != "SHARED\n":
        fail(f"t6: .claude/ import did not resolve repo-root: {out!r}")
    else:
        ok("t6: @-import with '.claude/' prefix resolves repo-root-relative")

if FAIL:
    print("test-producers-expand-at-imports: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-producers-expand-at-imports: all checks passed.")
