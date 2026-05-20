#!/usr/bin/env python3
# test-post-transition.py — verify post-transition hooks fire on test-green.
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
TDD_STEP = os.path.join(FEATURE_DIR, 'scripts', 'tdd-step.py')

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


# pt1: rebuild-registry.sh hook is NOT present in tdd-step.py (deleted in Task 5).
def pt1():
    with open(TDD_STEP) as f:
        content = f.read()
    if 'rebuild-registry.sh' in content:
        ko('pt1: rebuild-registry.sh reference still present in tdd-step.py')
    else:
        ok('pt1: rebuild-registry.sh hook correctly absent from tdd-step.py')


print(f"running post-transition hook tests against {TDD_STEP}")
pt1()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
