#!/usr/bin/env python3
"""test-runtime-check-marker-alert.py — exercises check_marker_alert: emits
a print result if the marker file exists (optionally content-matched),
otherwise returns ok.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_marker_alert  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


ALERT = {"text": "SCOPE OVERRIDE ACTIVE", "icon": "unlock", "color": "red"}

# t1: marker absent -> ok_result
with tempfile.TemporaryDirectory() as td:
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: missing marker returns ok_result")
    else:
        fail(f"t1: expected ok, got {r!r}")

# t2: marker present, no content filter -> print_result built from alert
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("anything")
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "print", "text": "SCOPE OVERRIDE ACTIVE",
             "icon": "unlock", "color": "red"}:
        ok("t2: present marker without content filter returns print_result")
    else:
        fail(f"t2: unexpected result {r!r}")

# t3: marker present, content matches filter -> print_result
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    r = check_marker_alert(".rabbit-scope-override", "session", ALERT, repo_root=td)
    if r.get("type") == "print":
        ok("t3: content match returns print_result")
    else:
        fail(f"t3: expected print, got {r!r}")

# t4: marker present but content does NOT match filter -> ok_result
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("permanent")
    r = check_marker_alert(".rabbit-scope-override", "session", ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t4: content mismatch returns ok_result")
    else:
        fail(f"t4: expected ok, got {r!r}")

# t5: marker is a directory (not a regular file) -> treated as absent
with tempfile.TemporaryDirectory() as td:
    os.makedirs(os.path.join(td, ".rabbit-scope-override"))
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t5: directory at marker path treated as absent")
    else:
        fail(f"t5: expected ok, got {r!r}")

if FAIL:
    print("test-runtime-check-marker-alert: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-marker-alert: all checks passed.")
