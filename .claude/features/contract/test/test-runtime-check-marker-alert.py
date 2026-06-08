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

# t6 (#789): marker active + .rabbit-auto-evolve-active ABSENT -> alert FIRES.
#     Confirms the suppression hook is marker-gated (regression-safe baseline).
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    r = check_marker_alert(".rabbit-scope-override", "session", ALERT, repo_root=td)
    if r.get("type") == "print":
        ok("t6: marker active + auto-evolve ABSENT -> alert FIRES")
    else:
        fail(f"t6: expected print, got {r!r}")

# t7 (#789): marker active + .rabbit-auto-evolve-active PRESENT -> SILENT.
#     Re-homes the Inv 54 suppression into the live per-feature path: the
#     auto-evolve composite banner is the single replacement surface.
with tempfile.TemporaryDirectory() as td:
    with open(os.path.join(td, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    open(os.path.join(td, ".rabbit-auto-evolve-active"), "w").close()
    r = check_marker_alert(".rabbit-scope-override", "session", ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t7: marker active + auto-evolve PRESENT -> suppressed (ok_result)")
    else:
        fail(f"t7: expected ok_result (suppressed), got {r!r}")

# t8 (#789): marker inactive + .rabbit-auto-evolve-active PRESENT -> SILENT.
#     Suppression does not change the absent-marker no-op outcome.
with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, ".rabbit-auto-evolve-active"), "w").close()
    r = check_marker_alert(".rabbit-scope-override", None, ALERT, repo_root=td)
    if r == {"type": "ok"}:
        ok("t8: marker absent + auto-evolve PRESENT -> silent (ok_result)")
    else:
        fail(f"t8: expected ok_result, got {r!r}")

# --- VENDORED layout (Inv 68 / #1113) -------------------------------------
# check_marker_alert backs the rabbit-feature Stop/SessionStart
# .rabbit-tdd-autonomous alert (Inv 59). In a VENDORED install the dispatcher
# passes repo_root = RABBIT_ROOT = <git-toplevel>/.rabbit, but the marker is
# written at the GIT TOPLEVEL (Inv 68 / #1048). So the READ root must be
# resolved via _repo_markers_root(repo_root) (= dirname when vendored), not raw
# repo_root, or the alert never fires.

TDD_ALERT = {"text": "TDD-AUTONOMOUS MODE ACTIVE",
             "icon": "\U0001f511", "color": "red"}

# t9 (#1113): vendored, marker PRESENT at the git toplevel -> alert FIRES.
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    os.makedirs(rabbit_root)
    os.makedirs(os.path.join(td, "src"))  # sibling so the host reads vendored
    with open(os.path.join(td, ".rabbit-tdd-autonomous"), "w") as f:
        f.write("session")
    r = check_marker_alert(".rabbit-tdd-autonomous", None, TDD_ALERT,
                           repo_root=rabbit_root)
    if r.get("type") == "print" and r.get("text") == "TDD-AUTONOMOUS MODE ACTIVE":
        ok("t9: vendored marker at git toplevel -> alert FIRES")
    else:
        fail(f"t9: expected print_result (marker read at toplevel), got {r!r}")

# t10 (#1113): vendored, a stale marker ONE .rabbit too deep must NOT fire —
#     the git-toplevel location is the sole read site for a repo-root marker.
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    os.makedirs(rabbit_root)
    os.makedirs(os.path.join(td, "src"))
    with open(os.path.join(rabbit_root, ".rabbit-tdd-autonomous"), "w") as f:
        f.write("session")
    r = check_marker_alert(".rabbit-tdd-autonomous", None, TDD_ALERT,
                           repo_root=rabbit_root)
    if r == {"type": "ok"}:
        ok("t10: vendored, marker only inside .rabbit (wrong site) -> silent")
    else:
        fail(f"t10: expected ok_result (stale-inside-.rabbit ignored), got {r!r}")

# t11 (#1113): vendored, NO marker anywhere -> silent (ok_result).
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    os.makedirs(rabbit_root)
    os.makedirs(os.path.join(td, "src"))
    r = check_marker_alert(".rabbit-tdd-autonomous", None, TDD_ALERT,
                           repo_root=rabbit_root)
    if r == {"type": "ok"}:
        ok("t11: vendored, no marker -> silent (ok_result)")
    else:
        fail(f"t11: expected ok_result, got {r!r}")

# t12 (#1113): vendored, an explicit `.rabbit/<marker>` declaration (the
#     rabbit-cage inside-.rabbit scope-override entry) resolves INSIDE .rabbit,
#     i.e. join(toplevel, ".rabbit/<marker>") == <repo_root>/<marker>.
with tempfile.TemporaryDirectory() as td:
    rabbit_root = os.path.join(td, ".rabbit")
    os.makedirs(rabbit_root)
    os.makedirs(os.path.join(td, "src"))
    with open(os.path.join(rabbit_root, ".rabbit-scope-override"), "w") as f:
        f.write("session")
    r = check_marker_alert(".rabbit/.rabbit-scope-override", "session", ALERT,
                           repo_root=rabbit_root)
    if r.get("type") == "print":
        ok("t12: vendored, `.rabbit/<marker>` entry resolves inside .rabbit -> FIRES")
    else:
        fail(f"t12: expected print_result (inside-.rabbit entry), got {r!r}")

if FAIL:
    print("test-runtime-check-marker-alert: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-marker-alert: all checks passed.")
