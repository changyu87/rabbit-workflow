#!/usr/bin/env python3
"""Inv 10 — SCOPE BOUNDARY red flag with blocked HANDOFF schema."""
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

# Inv 10: scope boundary red flag section + blocked HANDOFF schema.
required_substrings = [
    "SCOPE BOUNDARY",
    "MUST NOT create any .rabbit-scope-active-<X>",
    "tdd_state: blocked",
    "test_result: not_run",
    "cross_feature_dependency:",
    "unwritten_paths:",
    "notes:",
]
for needle in required_substrings:
    if needle in prompt:
        ok(f"inv10: contains '{needle[:50]}'")
    else:
        ko(f"inv10: missing '{needle[:50]}'")

report(passed, failed)
