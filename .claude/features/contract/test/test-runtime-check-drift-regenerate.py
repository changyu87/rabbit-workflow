#!/usr/bin/env python3
"""test-runtime-check-drift-regenerate.py — exercises
check_drift_regenerate: invokes a content producer, compares to target on
disk, regenerates + emits print+inject on drift, returns ok on match.

lib.producers is stubbed via sys.modules BEFORE importing lib.runtime so
the lazy import inside check_drift_regenerate resolves to the stub.
"""

import os
import sys
import tempfile
import types

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

_producers_stub = types.ModuleType("lib.producers")
_producers_stub.call_producer = lambda name, args, feature_dir, repo_root: (
    "PRODUCED-BY-" + name + "\n"
)
sys.modules["lib.producers"] = _producers_stub

from lib.runtime import check_drift_regenerate  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "CLAUDE.md regenerated", "icon": "warn", "color": "red"}

# t1: target missing -> regenerate, return [print, inject]
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    if (isinstance(r, list) and len(r) == 2
            and r[0]["type"] == "print" and r[1]["type"] == "inject"):
        target = os.path.join(root, "CLAUDE.md")
        if open(target).read() == "PRODUCED-BY-generate-claude-md\n":
            ok("t1: missing target regenerated + [print, inject] returned")
        else:
            fail(f"t1: target content wrong: {open(target).read()!r}")
    else:
        fail(f"t1: expected [print, inject] list, got {r!r}")

# t2: target matches producer output -> ok_result, no write
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(root, "CLAUDE.md")
    with open(target, "w") as f:
        f.write("PRODUCED-BY-generate-claude-md\n")
    mtime_before = os.stat(target).st_mtime_ns
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    mtime_after = os.stat(target).st_mtime_ns
    if r == {"type": "ok"} and mtime_before == mtime_after:
        ok("t2: match returns ok_result without rewriting target")
    else:
        fail(f"t2: result={r!r}, mtime_changed={mtime_before != mtime_after}")

# t3: target drifted -> regenerate, return [print, inject], target updated
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    target = os.path.join(root, "CLAUDE.md")
    with open(target, "w") as f:
        f.write("STALE\n")
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    if (isinstance(r, list) and r[0]["text"] == "CLAUDE.md regenerated"
            and open(target).read() == "PRODUCED-BY-generate-claude-md\n"):
        ok("t3: drift detected: target overwritten + alert returned")
    else:
        fail(f"t3: unexpected: result={r!r}, target={open(target).read()!r}")

# t4: print result uses alert text/icon/color verbatim
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    p = r[0]
    if (p["text"] == ALERT["text"] and p["icon"] == ALERT["icon"]
            and p["color"] == ALERT["color"]):
        ok("t4: print result uses alert text/icon/color verbatim")
    else:
        fail(f"t4: print result {p!r} != alert {ALERT!r}")

# t5: producer failure -> error_result
def _boom(name, args, feature_dir, repo_root):
    raise RuntimeError("producer exploded")


_producers_stub.call_producer = _boom
with tempfile.TemporaryDirectory() as td:
    feat = os.path.join(td, "feature")
    root = os.path.join(td, "repo")
    os.makedirs(feat)
    os.makedirs(root)
    r = check_drift_regenerate("CLAUDE.md", "generate-claude-md", ALERT,
                                feature_dir=feat, repo_root=root)
    if isinstance(r, dict) and r.get("type") == "error":
        ok("t5: producer exception caught and returned as error_result")
    else:
        fail(f"t5: expected error dict, got {r!r}")

# Restore stub for any later code (none here, but defensive).
_producers_stub.call_producer = lambda name, args, feature_dir, repo_root: (
    "PRODUCED-BY-" + name + "\n"
)

if FAIL:
    print("test-runtime-check-drift-regenerate: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-drift-regenerate: all checks passed.")
