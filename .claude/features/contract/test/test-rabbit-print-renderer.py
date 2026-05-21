#!/usr/bin/env python3
"""test-rabbit-print-renderer.py — end-to-end tests for rabbit_print.py.

Imports the rabbit_print module from
.claude/features/contract/scripts/rabbit_print.py and exercises both public
functions (rabbit_print, rabbit_subline) against every required message-id
declared in Inv 27. Asserts exact rendered strings, KeyError semantics, and
the no-side-effects requirement of Inv 28.
"""

import os
import sys
import io
import json
import importlib.util
import contextlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
MODULE_PATH = os.path.join(FEATURE_DIR, "scripts", "rabbit_print.py")
MESSAGES_FILE = os.path.join(FEATURE_DIR, "schemas", "rabbit-print-messages.json")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


# t1: module file exists
if not os.path.isfile(MODULE_PATH):
    fail(f"t1: rabbit_print.py missing at {MODULE_PATH}")
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)
ok("t1: rabbit_print.py exists on disk")

# t2: importable as a module
spec = importlib.util.spec_from_file_location("rabbit_print", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    ok("t2: rabbit_print module imports cleanly")
except Exception as e:
    fail(f"t2: import failed: {e}")
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)

# t3: __all__ is exactly the 15 names declared in Inv 28 (r1_branch removed
# alongside rabbit-cage Inv 41; bypass_permissions_active added alongside
# rabbit-cage Inv 61 banner upgrade; dispatch_bypass_note added in BACKLOG-29
# alongside the tdd-subagent BUG-57 fix).
expected_all = {
    "rabbit_print", "rabbit_subline", "rabbit_block",
    "welcome", "policy_drift", "surface_drift",
    "scope_guard_off", "scope_guard_bypassed", "human_approval_bypass",
    "bypass_permissions_active", "dispatch_bypass_note",
    "skills_updated", "policy_refreshed", "tdd_transition", "tdd_forced",
}
actual_all = set(getattr(mod, "__all__", []))
if actual_all == expected_all:
    ok(f"t3: __all__ is exactly the {len(expected_all)} declared names")
else:
    fail(f"t3: __all__ mismatch: expected {expected_all}, got {actual_all}")

# t4: functions exist and are callable
if callable(getattr(mod, "rabbit_print", None)):
    ok("t4: rabbit_print is callable")
else:
    fail("t4: rabbit_print is not callable")
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)

if callable(getattr(mod, "rabbit_subline", None)):
    ok("t4b: rabbit_subline is callable")
else:
    fail("t4b: rabbit_subline is not callable")
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)

# Load the registry directly for golden assertions
with open(MESSAGES_FILE) as f:
    REG = json.load(f)

BRAND = REG["brand"]
BAR = REG["bar"]
GREEN_A = REG["colors"]["green"]["ansi"]
GREEN_R = REG["colors"]["green"]["reset"]
RED_A = REG["colors"]["red"]["ansi"]
RED_R = REG["colors"]["red"]["reset"]


def expected_main(mid, **kwargs):
    m = REG["messages"][mid]
    c = REG["colors"][m["color"]]
    body = m["text"].format(**kwargs)
    return f"{c['ansi']}{BRAND} {m['icon']} {BAR} {body} {BAR} {m['icon']}{c['reset']}"


# t5: rabbit_print produces the exact expected string for a parameterized id.
# (r1-branch was the previous fixture here; it is removed per Inv 27/28(d), so
# surface-drift — which also takes a placeholder kwarg — is used instead.)
captured_out = io.StringIO()
captured_err = io.StringIO()
with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
    got = mod.rabbit_print("surface-drift", files="hooks/sync-check.py")
exp = expected_main("surface-drift", files="hooks/sync-check.py")
if got == exp:
    ok("t5: rabbit_print('surface-drift', files=...) returns exact expected string")
else:
    fail(f"t5: rabbit_print('surface-drift') mismatch\n  exp: {exp!r}\n  got: {got!r}")

# Capture also: must be empty
if captured_out.getvalue() == "" and captured_err.getvalue() == "":
    ok("t5b: rabbit_print produces no stdout/stderr side effects")
else:
    fail(f"t5b: rabbit_print produced side effects: stdout={captured_out.getvalue()!r}, stderr={captured_err.getvalue()!r}")

# t6: exercise every required message-id with appropriate kwargs
KWARGS = {
    "welcome": {},
    "policy-drift": {},
    "surface-drift": {"files": "hooks/sync-check.py"},
    "scope-guard-off": {},
    "scope-guard-bypassed": {},
    "human-approval-bypass": {},
    "bypass-permissions-active": {},
    "dispatch-bypass-note": {},
    "skills-updated": {"names": "rabbit-config, rabbit-feature-touch"},
    "policy-refreshed": {},
    "tdd-transition": {"from_state": "spec-read", "to_state": "test-write"},
    "tdd-forced": {"from_state": "test-red", "to_state": "test-green"},
}
for mid, kw in KWARGS.items():
    cap_o, cap_e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(cap_o), contextlib.redirect_stderr(cap_e):
        got = mod.rabbit_print(mid, **kw)
    exp = expected_main(mid, **kw)
    if got == exp:
        ok(f"t6: rabbit_print({mid!r}) matches expected")
    else:
        fail(f"t6: rabbit_print({mid!r}) mismatch\n  exp: {exp!r}\n  got: {got!r}")
    if cap_o.getvalue() or cap_e.getvalue():
        fail(f"t6b: rabbit_print({mid!r}) emitted side effects")

# t7: KeyError on unknown message-id
try:
    mod.rabbit_print("does-not-exist")
    fail("t7: unknown message-id did not raise KeyError")
except KeyError:
    ok("t7: unknown message-id raises KeyError")
except Exception as e:
    fail(f"t7: unknown message-id raised {type(e).__name__} not KeyError")

# t8: KeyError on missing required placeholder
try:
    mod.rabbit_print("surface-drift")  # missing 'files' kwarg
    fail("t8: missing placeholder did not raise KeyError")
except KeyError:
    ok("t8: missing placeholder raises KeyError")
except Exception as e:
    fail(f"t8: missing placeholder raised {type(e).__name__} not KeyError")

# t9: rabbit_subline default (green)
cap_o, cap_e = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(cap_o), contextlib.redirect_stderr(cap_e):
    got = mod.rabbit_subline("test text")
exp = f"{GREEN_A}{BRAND} test text{GREEN_R}"
if got == exp:
    ok("t9: rabbit_subline default returns exact green-wrapped string")
else:
    fail(f"t9: rabbit_subline default mismatch\n  exp: {exp!r}\n  got: {got!r}")
if cap_o.getvalue() or cap_e.getvalue():
    fail("t9b: rabbit_subline default emitted side effects")

# t10: rabbit_subline with color='red'
cap_o, cap_e = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(cap_o), contextlib.redirect_stderr(cap_e):
    got = mod.rabbit_subline("alert", color="red")
exp = f"{RED_A}{BRAND} alert{RED_R}"
if got == exp:
    ok("t10: rabbit_subline color='red' returns exact red-wrapped string")
else:
    fail(f"t10: rabbit_subline red mismatch\n  exp: {exp!r}\n  got: {got!r}")
if cap_o.getvalue() or cap_e.getvalue():
    fail("t10b: rabbit_subline red emitted side effects")

if FAIL != 0:
    print("test-rabbit-print-renderer: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-rabbit-print-renderer: all checks passed.")
