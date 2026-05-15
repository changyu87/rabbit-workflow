#!/usr/bin/env python3
# Test: surface.skills in tdd-state-machine/feature.json must be []
# Invariant 9: skills are managed via build-contract.json copy-file entries;
# the surface.skills field is retired and must be an empty array.
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../../..'))
FEATURE_JSON = os.path.join(REPO_ROOT, '.claude/features/tdd-state-machine/feature.json')

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


# t1: feature.json exists
def t1():
    if os.path.isfile(FEATURE_JSON):
        ok('t1: feature.json exists')
    else:
        ko(f"t1: feature.json not found at {FEATURE_JSON}")


# t2: surface.skills is exactly []
def t2():
    if not os.path.isfile(FEATURE_JSON):
        ko('t2: feature.json not found — cannot check surface.skills')
        return
    with open(FEATURE_JSON) as f:
        data = json.load(f)
    skills = data.get('surface', {}).get('skills', [])
    if skills == []:
        ok("t2: surface.skills is [] (retired)")
    else:
        ko(f"t2: surface.skills is not [] — got: {skills} (must be empty; skills managed via build-contract.json)")


print("running surface.skills retirement tests (tdd-state-machine)")
t1(); t2()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
