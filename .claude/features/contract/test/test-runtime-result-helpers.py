#!/usr/bin/env python3
"""test-runtime-result-helpers.py — verifies the four result-factory helpers
(print_result, inject_result, ok_result, error_result) produce tagged dicts
matching the runtime API contract.
"""

import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, FEATURE_DIR)

from lib.runtime import print_result, inject_result, ok_result, error_result  # noqa: E402

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# t1: print_result returns the documented tagged dict
r = print_result("hello", "warn", "red")
if r == {"type": "print", "text": "hello", "icon": "warn", "color": "red"}:
    ok("t1: print_result returns tagged dict with text/icon/color")
else:
    fail(f"t1: unexpected print_result: {r!r}")

# t2: inject_result returns the documented tagged dict
r = inject_result("policy text\n")
if r == {"type": "inject", "content": "policy text\n"}:
    ok("t2: inject_result returns tagged dict with content")
else:
    fail(f"t2: unexpected inject_result: {r!r}")

# t3: ok_result returns the documented tagged dict
r = ok_result()
if r == {"type": "ok"}:
    ok("t3: ok_result returns tagged dict with only type")
else:
    fail(f"t3: unexpected ok_result: {r!r}")

# t4: error_result returns the documented tagged dict
r = error_result("something broke")
if r == {"type": "error", "message": "something broke"}:
    ok("t4: error_result returns tagged dict with message")
else:
    fail(f"t4: unexpected error_result: {r!r}")

if FAIL:
    print("test-runtime-result-helpers: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-runtime-result-helpers: all checks passed.")
