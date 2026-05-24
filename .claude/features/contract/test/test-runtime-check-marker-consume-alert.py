#!/usr/bin/env python3
"""test-runtime-check-marker-consume-alert.py — exercises
check_marker_consume_alert: deletes the marker after emitting a print
result; supports {marker-content} interpolation into alert text.
"""

import os
import sys
import tempfile

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_marker_consume_alert  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


PLAIN = {"text": "SCOPE BYPASSED", "icon": "unlock", "color": "red"}
INTERPOLATED = {"text": "Skills updated: {marker-content}",
                "icon": "sparkle", "color": "green"}

# t1: missing marker -> ok_result, no error
with tempfile.TemporaryDirectory() as td:
    r = check_marker_consume_alert(".rabbit-skills-updated", PLAIN, repo_root=td)
    if r == {"type": "ok"}:
        ok("t1: missing marker returns ok_result")
    else:
        fail(f"t1: expected ok, got {r!r}")

# t2: present marker -> print_result emitted AND marker is deleted
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, ".rabbit-scope-override-used")
    with open(p, "w") as f:
        f.write("anything")
    r = check_marker_consume_alert(".rabbit-scope-override-used", PLAIN, repo_root=td)
    if r != {"type": "print", "text": "SCOPE BYPASSED",
             "icon": "unlock", "color": "red"}:
        fail(f"t2: unexpected result {r!r}")
    elif os.path.exists(p):
        fail("t2: marker still present after consume")
    else:
        ok("t2: present marker emits print and is consumed")

# t3: {marker-content} substitution uses stripped file content
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, ".rabbit-skills-updated")
    with open(p, "w") as f:
        f.write("rabbit-foo, rabbit-bar\n")
    r = check_marker_consume_alert(".rabbit-skills-updated", INTERPOLATED, repo_root=td)
    if r.get("text") == "Skills updated: rabbit-foo, rabbit-bar":
        ok("t3: {marker-content} substitution uses stripped file content")
    else:
        fail(f"t3: unexpected text {r!r}")

# t4: alert dict is not mutated (caller reuses across invocations)
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, ".rabbit-skills-updated")
    with open(p, "w") as f:
        f.write("payload\n")
    alert_copy = dict(INTERPOLATED)
    check_marker_consume_alert(".rabbit-skills-updated", INTERPOLATED, repo_root=td)
    if INTERPOLATED == alert_copy:
        ok("t4: alert dict not mutated by call")
    else:
        fail(f"t4: alert dict mutated; now {INTERPOLATED!r}")

if FAIL:
    print("test-runtime-check-marker-consume-alert: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-marker-consume-alert: all checks passed.")
