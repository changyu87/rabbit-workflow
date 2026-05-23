#!/usr/bin/env python3
"""Inv 7, 8, 9 — scope marker convention, 9-step banners in order, E2E
test rule mentioned."""
from _helpers import run_dispatch, report

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ok   {msg}")


def ko(msg):
    global failed
    failed += 1
    print(f"  FAIL {msg}")


res = run_dispatch()
if res.returncode != 0:
    print(f"FATAL: dispatch failed rc={res.returncode}: {res.stderr}")
    raise SystemExit(1)
prompt = res.stdout

# Inv 7: per-feature scope marker convention.
if ".rabbit-scope-active-tdd-subagent" in prompt:
    ok("inv7: per-feature scope marker .rabbit-scope-active-<feature> mentioned")
else:
    ko("inv7: per-feature scope marker not mentioned")

# Inv 8: nine step banners present in declared order.
steps = [
    "SPEC-READ",
    "HUMAN-APPROVAL",
    "LOCK",
    "TEST-WRITE",
    "TEST-RED",
    "IMPLEMENT",
    "CODE-REVIEW",
    "TEST-GREEN",
    "UNLOCK",
]
positions = []
for s in steps:
    needle = f"STEP {len(positions) + 1} — {s}"
    idx = prompt.find(needle)
    if idx == -1:
        ko(f"inv8: banner missing: '{needle}'")
        positions.append(None)
    else:
        positions.append(idx)

valid_positions = [p for p in positions if p is not None]
if len(valid_positions) == len(steps) and valid_positions == sorted(valid_positions):
    ok("inv8: nine step banners present in declared order")
elif len(valid_positions) == len(steps):
    ko("inv8: step banners present but out of order")

# Inv 9: E2E test rule mentioned in prompt.
if "E2E TEST RULE" in prompt and "Unit tests alone are insufficient" in prompt:
    ok("inv9: E2E TEST RULE present in prompt")
else:
    ko("inv9: E2E TEST RULE missing or incomplete")

report(passed, failed)
