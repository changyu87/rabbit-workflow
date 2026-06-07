#!/usr/bin/env python3
"""Inv 7, 8, 9 — scope marker convention, 8-step banners in order, E2E
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

# Inv 8: eight step banners present in declared order, numbered STEP 1..STEP 8.
steps = [
    "LOCK",
    "TEST-WRITE",
    "TEST-RED",
    "IMPLEMENT",
    "SYNC-DEPLOYED",
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
    ok("inv8: eight step banners present in declared order")
elif len(valid_positions) == len(steps):
    ko("inv8: step banners present but out of order")

# Inv 8 (negative): the retired SPEC-READ and HUMAN-APPROVAL step banners
# must not appear in the assembled prompt. Check the banner form
# `STEP N — <name>` only — the strings may still appear inside the embedded
# spec body (which legitimately describes the retired branches) and in the
# bypass-marker preamble note (which references the dispatcher's Step 4
# HUMAN-APPROVAL gate, not a subagent step).
import re as _re
if not _re.search(r"STEP \d+ — SPEC-READ", prompt):
    ok("inv8: retired SPEC-READ step banner absent from prompt")
else:
    ko("inv8: retired SPEC-READ step banner still present in prompt")
if not _re.search(r"STEP \d+ — HUMAN-APPROVAL", prompt):
    ok("inv8: retired HUMAN-APPROVAL step banner absent from prompt")
else:
    ko("inv8: retired HUMAN-APPROVAL step banner still present in prompt")

# Inv 8 (count): exactly eight STEP N banners, numbered 1..8 — no STEP 9/10.
if "STEP 9 —" not in prompt and "STEP 10 —" not in prompt:
    ok("inv8: no STEP 9/10 banners remain after 8-step promotion")
else:
    ko("inv8: stray STEP 9 or STEP 10 banner present")

# Inv 9: E2E test rule mentioned in prompt.
if "E2E TEST RULE" in prompt and "Unit tests alone are insufficient" in prompt:
    ok("inv9: E2E TEST RULE present in prompt")
else:
    ko("inv9: E2E TEST RULE missing or incomplete")

report(passed, failed)
