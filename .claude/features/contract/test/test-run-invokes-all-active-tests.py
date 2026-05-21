#!/usr/bin/env python3
"""test-run-invokes-all-active-tests.py — BUG-26 / Inv 17

End-to-end test that test/run.py invokes every active test-*.py file in the
test directory. Active = filename matches test-*.py and does not begin with
an underscore (_test-...py).

t1: every active test-*.py file (excluding this runner itself) appears in
    run.py as a run_test("...") invocation.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_PY = os.path.join(TEST_DIR, "run.py")

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS t{n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    FAIL += 1


with open(RUN_PY) as f:
    run_src = f.read()

invoked = set(re.findall(r'run_test\("([^"]+)"\)', run_src))

# Active test files: test-*.py, NOT _test-*.py
active = set()
for fname in os.listdir(TEST_DIR):
    if not fname.endswith(".py"):
        continue
    if not fname.startswith("test-"):
        continue
    active.add(fname)

missing = sorted(active - invoked)
if not missing:
    ok(1, f"all {len(active)} active test files invoked by run.py")
else:
    fail_t(1, f"active test files NOT invoked by run.py: {missing}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
