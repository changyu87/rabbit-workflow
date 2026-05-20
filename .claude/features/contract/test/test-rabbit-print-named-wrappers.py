#!/usr/bin/env python3
"""test-rabbit-print-named-wrappers.py — e2e tests for the named wrapper API.

Verifies Inv 35(d): rabbit_print.py exposes 10 named wrappers, one per
message-id, each thinly delegating to rabbit_print(<id>, **kwargs). Each
wrapper signature exposes exactly the kwargs its message-id requires.
tdd_transition and tdd_forced upcase their state-name placeholders.
Also asserts that the previously-required r1_branch wrapper is absent
(removed alongside rabbit-cage Inv 61).
"""

import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
MODULE_PATH = os.path.join(FEATURE_DIR, "scripts", "rabbit_print.py")

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def fail(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


spec = importlib.util.spec_from_file_location("rabbit_print", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Wrappers with zero kwargs
ZERO_ARG = [
    ("welcome", "welcome"),
    ("policy_drift", "policy-drift"),
    ("scope_guard_off", "scope-guard-off"),
    ("scope_guard_bypassed", "scope-guard-bypassed"),
    ("human_approval_bypass", "human-approval-bypass"),
    ("bypass_permissions_active", "bypass-permissions-active"),
    ("dispatch_bypass_note", "dispatch-bypass-note"),
    ("policy_refreshed", "policy-refreshed"),
]

for wrapper_name, mid in ZERO_ARG:
    fn = getattr(mod, wrapper_name, None)
    if not callable(fn):
        fail(f"wrapper {wrapper_name} not callable")
        continue
    got = fn()
    exp = mod.rabbit_print(mid)
    if got == exp:
        ok(f"{wrapper_name}() == rabbit_print({mid!r})")
    else:
        fail(f"{wrapper_name}() mismatch\n  exp: {exp!r}\n  got: {got!r}")

# r1_branch removed (Inv 35(d)): wrapper MUST NOT exist and MUST NOT appear
# in __all__.
if getattr(mod, "r1_branch", None) is None:
    ok("r1_branch wrapper absent from module")
else:
    fail("r1_branch wrapper still present (should be removed per Inv 35(d))")

if "r1_branch" in getattr(mod, "__all__", []):
    fail("r1_branch still listed in __all__ (should be removed per Inv 35(d))")
else:
    ok("r1_branch absent from __all__")

# surface_drift(files) — Inv 35(d), BACKLOG-21: required files kwarg,
# rendered text ends with the files list followed by bar + icon + reset.
fn = getattr(mod, "surface_drift", None)
if callable(fn):
    got = fn(files="hooks/sync-check.py")
    exp = mod.rabbit_print("surface-drift", files="hooks/sync-check.py")
    if got == exp:
        ok("surface_drift(files=...) == rabbit_print('surface-drift', files=...)")
    else:
        fail(f"surface_drift mismatch\n  exp: {exp!r}\n  got: {got!r}")

    # Reach into the registry to compose the expected trailing decoration
    # (bar + icon + reset) deterministically.
    reg = mod._load()
    bar = reg["bar"]
    icon = reg["messages"]["surface-drift"]["icon"]
    reset = reg["colors"][reg["messages"]["surface-drift"]["color"]]["reset"]
    tail = " " + "hooks/sync-check.py" + " " + bar + " " + icon + reset
    if got.endswith(tail):
        ok(f"surface_drift output ends with files + bar + icon + reset: {tail!r}")
    else:
        fail(f"surface_drift output tail mismatch\n  exp tail: {tail!r}\n  got: {got!r}")

    # Without the files kwarg, the str.format inside rabbit_print MUST raise
    # KeyError (or TypeError if signature enforces it positionally).
    try:
        fn()
        fail("surface_drift() with no args did not raise")
    except (TypeError, KeyError):
        ok("surface_drift() with no args raises TypeError/KeyError")
else:
    fail("surface_drift not callable")

# skills_updated(names)
fn = getattr(mod, "skills_updated", None)
if callable(fn):
    got = fn("rabbit-config, rabbit-feature-touch")
    exp = mod.rabbit_print("skills-updated", names="rabbit-config, rabbit-feature-touch")
    if got == exp:
        ok("skills_updated(names=...) == rabbit_print('skills-updated', names=...)")
    else:
        fail(f"skills_updated mismatch\n  exp: {exp!r}\n  got: {got!r}")
else:
    fail("skills_updated not callable")

# tdd_transition: upcases state-name placeholders
fn = getattr(mod, "tdd_transition", None)
if callable(fn):
    got = fn("spec-update", "test-red")
    exp = mod.rabbit_print("tdd-transition", from_state="SPEC-UPDATE", to_state="TEST-RED")
    if got == exp:
        ok("tdd_transition lowercases input upcased == rabbit_print(...)")
    else:
        fail(f"tdd_transition mismatch\n  exp: {exp!r}\n  got: {got!r}")
    if "SPEC-UPDATE" in got and "TEST-RED" in got:
        ok("tdd_transition output contains upcased SPEC-UPDATE and TEST-RED")
    else:
        fail(f"tdd_transition output missing upcased forms: {got!r}")
    if "spec-update" in got or "test-red" in got:
        fail(f"tdd_transition output contains lowercase forms: {got!r}")
    else:
        ok("tdd_transition output has no lowercase state names")
else:
    fail("tdd_transition not callable")

# tdd_forced: same upcasing behavior
fn = getattr(mod, "tdd_forced", None)
if callable(fn):
    got = fn("spec-update", "test-red")
    exp = mod.rabbit_print("tdd-forced", from_state="SPEC-UPDATE", to_state="TEST-RED")
    if got == exp:
        ok("tdd_forced lowercases input upcased == rabbit_print(...)")
    else:
        fail(f"tdd_forced mismatch\n  exp: {exp!r}\n  got: {got!r}")
    if "SPEC-UPDATE" in got and "TEST-RED" in got:
        ok("tdd_forced output contains upcased SPEC-UPDATE and TEST-RED")
    else:
        fail(f"tdd_forced output missing upcased forms: {got!r}")
else:
    fail("tdd_forced not callable")

# dispatch_bypass_note canonical-text check (Inv 35, BACKLOG-29): the wrapper
# output MUST embed the canonical preamble body so the dispatch prompt remains
# grep-stable.
EXPECTED_DISPATCH_TEXT = (
    "NOTE: human-approval bypass marker is active "
    "(.rabbit-human-approval-bypass). Step 4 HUMAN-APPROVAL will be skipped "
    "for this dispatch. Revoke via `/rabbit-config human-approval true`."
)
fn = getattr(mod, "dispatch_bypass_note", None)
if callable(fn):
    got = fn()
    if EXPECTED_DISPATCH_TEXT in got:
        ok("dispatch_bypass_note output embeds canonical preamble text")
    else:
        fail(f"dispatch_bypass_note output missing canonical text\n  got: {got!r}")
else:
    fail("dispatch_bypass_note not callable")

if FAIL != 0:
    print("test-rabbit-print-named-wrappers: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-rabbit-print-named-wrappers: all checks passed.")
