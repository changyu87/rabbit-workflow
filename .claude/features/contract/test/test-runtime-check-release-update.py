#!/usr/bin/env python3
"""test-runtime-check-release-update.py — exercises Inv 39's
check_release_update runtime API.

check_release_update(*, repo_root) subprocesses scripts/check-release-update.py
and translates its JSON output into a LIST of per-line print_result entries (so
every line of the notification carries the [🐇 rabbit 🐇] brand prefix + color
when the dispatcher renders each entry), or ok_result:
  - {newer: true, ...}  -> list of print_result(text, "📦", "yellow"), one per
                           notification line: update headline, the /rabbit-update
                           recommended action (or fresh-install fallback when
                           self_update_available is false), claude --resume hint.
                           When .rabbit-update-restart-needed marker is present,
                           an extra restart-alert print_result line is appended
                           and the marker is consumed.
  - {newer: false}      -> ok_result()
  - malformed / non-0   -> ok_result() (silent — NEVER blocks the user)
"""

import os
import sys
import tempfile
import types
from unittest import mock

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import check_release_update  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def make_completed(stdout="", returncode=0):
    return types.SimpleNamespace(stdout=stdout, returncode=returncode, stderr="")


def as_print_lines(result):
    """Return the list of print_result dicts (assert list-of-print shape)."""
    if not isinstance(result, list):
        return None
    if not all(isinstance(x, dict) and x.get("type") == "print" for x in result):
        return None
    return result


NEWER_SELF = ('{"newer": true, "channel": "dev", "current": "abc", '
              '"new": "def", "self_update_available": true}\n')
NEWER_FRESH = ('{"newer": true, "channel": "dev", "current": "abc", '
               '"new": "def", "self_update_available": false}\n')

# t1: {newer: true, self_update_available: true} -> LIST of print_result lines,
#      each with 📦/yellow; every line is its own prefixed entry (Fix #1).
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout=NEWER_SELF)):
        r = check_release_update(repo_root=td)
    lines = as_print_lines(r)
    if lines is None:
        fail(f"t1: expected list of print_result dicts, got {r!r}")
    elif len(lines) < 3:
        fail(f"t1: expected >=3 per-line print entries, got {len(lines)}: {r!r}")
    elif any(x.get("icon") != "📦" for x in lines):
        fail(f"t1: every line must carry icon 📦: {r!r}")
    elif any(x.get("color") != "yellow" for x in lines):
        fail(f"t1: every line must carry color yellow: {r!r}")
    else:
        joined = " ".join(x.get("text", "") for x in lines)
        if "update available" not in joined:
            fail(f"t1: missing 'update available' headline: {joined!r}")
        elif "claude --resume" not in joined:
            fail(f"t1: missing claude --resume hint: {joined!r}")
        else:
            ok("t1: newer -> list of per-line 📦/yellow print_result entries")

# t2: Fix #2 — recommended action is the /rabbit-update skill, NOT the
#     install.py shell command (the shell command must be gone).
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout=NEWER_SELF)):
        r = check_release_update(repo_root=td)
    lines = as_print_lines(r) or []
    joined = " ".join(x.get("text", "") for x in lines)
    if "install.py --update" in joined or "install.py" in joined:
        fail(f"t2: install.py shell command must be gone: {joined!r}")
    elif "/rabbit-update" not in joined:
        fail(f"t2: recommended action must mention /rabbit-update: {joined!r}")
    else:
        ok("t2: recommended action is /rabbit-update; install.py command gone")

# t3: {newer: false} -> ok_result()
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout='{"newer": false}\n')):
        r = check_release_update(repo_root=td)
    if r == {"type": "ok"}:
        ok("t3: {newer: false} -> ok_result")
    else:
        fail(f"t3: expected ok_result, got {r!r}")

# t4: non-zero exit -> ok_result silent
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout="", returncode=1)):
        r = check_release_update(repo_root=td)
    if r == {"type": "ok"}:
        ok("t4: non-zero exit -> silent ok_result")
    else:
        fail(f"t4: expected silent ok_result on non-zero exit, got {r!r}")

# t5: empty stdout -> ok_result silent
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout="")):
        r = check_release_update(repo_root=td)
    if r == {"type": "ok"}:
        ok("t5: empty stdout -> silent ok_result")
    else:
        fail(f"t5: expected silent ok_result on empty stdout, got {r!r}")

# t6: malformed JSON -> ok_result silent
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout="not-json-at-all\n")):
        r = check_release_update(repo_root=td)
    if r == {"type": "ok"}:
        ok("t6: malformed JSON -> silent ok_result")
    else:
        fail(f"t6: expected silent ok_result on malformed JSON, got {r!r}")

# t7: subprocess raises -> ok_result silent (NEVER blocks the user)
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run", side_effect=OSError("boom")):
        r = check_release_update(repo_root=td)
    if r == {"type": "ok"}:
        ok("t7: subprocess raises -> silent ok_result")
    else:
        fail(f"t7: expected silent ok_result on subprocess exception, got {r!r}")

# t8: Fix #3 — restart-needed marker present -> an extra restart-alert line is
#     appended to the notification, AND the marker is consumed (deleted).
with tempfile.TemporaryDirectory() as td:
    marker = os.path.join(td, ".rabbit-update-restart-needed")
    with open(marker, "w") as f:
        f.write("")
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout=NEWER_SELF)):
        r = check_release_update(repo_root=td)
    lines = as_print_lines(r) or []
    joined = " ".join(x.get("text", "").lower() for x in lines)
    if "restart" not in joined:
        fail(f"t8: restart-needed marker present but no restart alert: {r!r}")
    elif os.path.exists(marker):
        fail("t8: restart-needed marker not consumed after alert")
    elif any(x.get("icon") != "📦" or x.get("color") != "yellow" for x in lines):
        fail(f"t8: restart alert line must keep 📦/yellow branding: {r!r}")
    else:
        ok("t8: restart-needed marker -> restart alert appended + consumed")

# t9: restart-needed marker absent -> NO restart alert line (no false alarm).
with tempfile.TemporaryDirectory() as td:
    with mock.patch("lib.runtime.subprocess.run",
                    return_value=make_completed(stdout=NEWER_SELF)):
        r = check_release_update(repo_root=td)
    lines = as_print_lines(r) or []
    joined = " ".join(x.get("text", "").lower() for x in lines)
    if "restart" in joined:
        fail(f"t9: no marker but restart alert leaked: {r!r}")
    else:
        ok("t9: no restart marker -> no restart alert line")


if FAIL:
    print("test-runtime-check-release-update: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-release-update: all checks passed.")
