#!/usr/bin/env python3
"""test-runtime-check-release-update.py — exercises Inv 47's
check_release_update runtime API.

check_release_update(*, repo_root) subprocesses scripts/check-release-update.py
and translates its JSON output into a print_result or ok_result:
  - {newer: true, ...}  -> print_result(text, "📦", "yellow") via rabbit_block
                           with 3 lines: update headline, install.py --update
                           command (or fresh-install fallback when
                           self_update_available is false), claude --resume hint.
  - {newer: false}      -> ok_result()
  - malformed / non-0   -> ok_result() (silent — NEVER blocks the user)
"""

import os
import sys
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


# t1: {newer: true, self_update_available: true} -> print_result with 📦/yellow,
#      text contains update headline + install.py --update + claude --resume.
with mock.patch("lib.runtime.subprocess.run",
                return_value=make_completed(
                    stdout='{"newer": true, "channel": "dev", "current": "abc", "new": "def", "self_update_available": true}\n',
                )) as m:
    r = check_release_update(repo_root=REPO_ROOT)
if not isinstance(r, dict):
    fail(f"t1: expected dict, got {type(r).__name__}: {r!r}")
elif r.get("type") != "print":
    fail(f"t1: expected print_result, got {r!r}")
elif r.get("icon") != "📦":
    fail(f"t1: expected icon 📦, got {r.get('icon')!r}")
elif r.get("color") != "yellow":
    fail(f"t1: expected color yellow, got {r.get('color')!r}")
else:
    text = r.get("text", "")
    if "update available" not in text:
        fail(f"t1: missing 'update available' headline: {text!r}")
    elif ".rabbit/install.py --update" not in text:
        fail(f"t1: missing install.py --update command: {text!r}")
    elif "claude --resume" not in text:
        fail(f"t1: missing claude --resume hint: {text!r}")
    elif not text.startswith("\n"):
        # rabbit_block leading newline contract (Inv 48c).
        fail(f"t1: text does not start with rabbit_block leading newline: {text!r}")
    else:
        ok("t1: newer + self_update_available=true -> print_result with all three lines")

# t2: {newer: true, self_update_available: false} -> fresh-install fallback
with mock.patch("lib.runtime.subprocess.run",
                return_value=make_completed(
                    stdout='{"newer": true, "channel": "dev", "current": "abc", "new": "def", "self_update_available": false}\n',
                )):
    r = check_release_update(repo_root=REPO_ROOT)
if not isinstance(r, dict) or r.get("type") != "print":
    fail(f"t2: expected print_result, got {r!r}")
else:
    text = r.get("text", "")
    if ".rabbit/install.py --update" in text:
        fail(f"t2: install.py --update command must NOT appear when self_update_available=false: {text!r}")
    elif "claude --resume" not in text:
        fail(f"t2: missing claude --resume hint: {text!r}")
    else:
        ok("t2: newer + self_update_available=false -> fresh-install fallback text (no install.py --update line)")

# t3: {newer: false} -> ok_result()
with mock.patch("lib.runtime.subprocess.run",
                return_value=make_completed(stdout='{"newer": false}\n')):
    r = check_release_update(repo_root=REPO_ROOT)
if r == {"type": "ok"}:
    ok("t3: {newer: false} -> ok_result")
else:
    fail(f"t3: expected ok_result, got {r!r}")

# t4: non-zero exit -> ok_result silent
with mock.patch("lib.runtime.subprocess.run",
                return_value=make_completed(stdout="", returncode=1)):
    r = check_release_update(repo_root=REPO_ROOT)
if r == {"type": "ok"}:
    ok("t4: non-zero exit -> silent ok_result")
else:
    fail(f"t4: expected silent ok_result on non-zero exit, got {r!r}")

# t5: empty stdout -> ok_result silent
with mock.patch("lib.runtime.subprocess.run",
                return_value=make_completed(stdout="")):
    r = check_release_update(repo_root=REPO_ROOT)
if r == {"type": "ok"}:
    ok("t5: empty stdout -> silent ok_result")
else:
    fail(f"t5: expected silent ok_result on empty stdout, got {r!r}")

# t6: malformed JSON -> ok_result silent
with mock.patch("lib.runtime.subprocess.run",
                return_value=make_completed(stdout="not-json-at-all\n")):
    r = check_release_update(repo_root=REPO_ROOT)
if r == {"type": "ok"}:
    ok("t6: malformed JSON -> silent ok_result")
else:
    fail(f"t6: expected silent ok_result on malformed JSON, got {r!r}")

# t7: subprocess raises -> ok_result silent (NEVER blocks the user)
with mock.patch("lib.runtime.subprocess.run", side_effect=OSError("boom")):
    r = check_release_update(repo_root=REPO_ROOT)
if r == {"type": "ok"}:
    ok("t7: subprocess raises -> silent ok_result")
else:
    fail(f"t7: expected silent ok_result on subprocess exception, got {r!r}")


if FAIL:
    print("test-runtime-check-release-update: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-check-release-update: all checks passed.")
