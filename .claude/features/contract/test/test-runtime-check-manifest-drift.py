#!/usr/bin/env python3
"""test-runtime-check-manifest-drift.py — exercises check_manifest_drift:
walks every feature's MANIFEST, re-runs publish APIs, returns a print_result
naming any feature that produced a non-no-op result (i.e., real write).

lib.publish is the real module here (no stub) — this test builds a fake
repo tree with a publish_file MANIFEST entry and verifies drift detection.
"""

import json
import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_manifest_drift  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "Surface drift detected — rebuilt: {names}",
         "icon": "rebuild", "color": "red"}


def make_feature(root, name, manifest, files):
    """Create .claude/features/<name>/feature.json with manifest +
    auxiliary source files (dict path -> content) under that feature dir."""
    fdir = os.path.join(root, ".claude", "features", name)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": name, "version": "1.0.0", "owner": "x",
                   "manifest": manifest}, f)
    for relpath, content in files.items():
        full = os.path.join(fdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)


# t1: no features -> ok_result
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".claude", "features"))
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: no features returns ok_result")
    else:
        fail(f"t1: expected ok, got {r!r}")

# t2: feature with manifest but destination matches source -> ok_result
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "feat-a",
                 [{"api": "publish_file",
                   "args": {"source": "src/foo.txt", "dest": "deployed/foo.txt"}}],
                 {"src/foo.txt": "hello\n"})
    # pre-deploy a matching file so the publish_file call is a no-op
    os.makedirs(os.path.join(td, "deployed"))
    with open(os.path.join(td, "deployed", "foo.txt"), "w") as f:
        f.write("hello\n")
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t2: all features no-op returns ok_result")
    else:
        fail(f"t2: expected ok, got {r!r}")

# t3: feature with manifest and missing destination -> print_result names feature
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "feat-a",
                 [{"api": "publish_file",
                   "args": {"source": "src/foo.txt", "dest": "deployed/foo.txt"}}],
                 {"src/foo.txt": "hello\n"})
    r = check_manifest_drift(ALERT, repo_root=td)
    if (r.get("type") == "print"
            and "feat-a" in r["text"]
            and r["text"].startswith("Surface drift detected — rebuilt:")):
        ok("t3: drift returns print_result with feature name substituted")
    else:
        fail(f"t3: unexpected: {r!r}")
    # verify destination was actually rebuilt
    if not os.path.isfile(os.path.join(td, "deployed", "foo.txt")):
        fail("t3: destination not rebuilt by re-publish")

# t4: multiple drifted features -> comma-joined alphabetical names
with tempfile.TemporaryDirectory() as td:
    make_feature(td, "b-feat",
                 [{"api": "publish_file",
                   "args": {"source": "src/a.txt", "dest": "out/b.txt"}}],
                 {"src/a.txt": "B\n"})
    make_feature(td, "a-feat",
                 [{"api": "publish_file",
                   "args": {"source": "src/a.txt", "dest": "out/a.txt"}}],
                 {"src/a.txt": "A\n"})
    r = check_manifest_drift(ALERT, repo_root=td)
    if r.get("type") == "print" and r["text"].endswith("a-feat, b-feat"):
        ok("t4: multiple drifted features comma-joined alphabetically")
    else:
        fail(f"t4: unexpected: {r!r}")

# t5: feature without manifest field -> skipped silently
with tempfile.TemporaryDirectory() as td:
    fdir = os.path.join(td, ".claude", "features", "no-manifest")
    os.makedirs(fdir)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        json.dump({"name": "no-manifest", "version": "1.0.0", "owner": "x"}, f)
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t5: feature without manifest section skipped")
    else:
        fail(f"t5: expected ok, got {r!r}")

# t6: malformed feature.json -> that feature skipped (not crash)
with tempfile.TemporaryDirectory() as td:
    fdir = os.path.join(td, ".claude", "features", "broken")
    os.makedirs(fdir)
    with open(os.path.join(fdir, "feature.json"), "w") as f:
        f.write("{ not json")
    r = check_manifest_drift(ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t6: malformed feature.json skipped (no crash)")
    else:
        fail(f"t6: expected ok, got {r!r}")

if FAIL:
    print("test-runtime-check-manifest-drift: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-manifest-drift: all checks passed.")
