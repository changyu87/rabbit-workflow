#!/usr/bin/env python3
# test-bug-surface-skills.py
# Asserts that surface.skills in feature.json is empty ([]).
# Skills are now managed via build-contract.json copy-file entries;
# the surface.skills declaration in feature.json is retired.
#
# t_skills1: surface.skills must be []
#
# Exit: 1 if any assertion fails.

import json
import os
import sys

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

passed = 0
failed = 0


def assert_pass(label):
    global passed
    print(f"PASS: {label}")
    passed += 1


def assert_fail(label, reason):
    global failed
    print(f"FAIL: {label} — {reason}")
    failed += 1


# ---------------------------------------------------------------------------
# t_skills1: surface.skills must be []
# ---------------------------------------------------------------------------
T_SKILLS1_LABEL = "t_skills1: surface.skills in feature.json must be []"

try:
    with open(FEATURE_JSON) as f:
        data = json.load(f)
    skills_val = data.get("surface", {}).get("skills", "MISSING")
    if skills_val == []:
        assert_pass(T_SKILLS1_LABEL)
    else:
        assert_fail(T_SKILLS1_LABEL, f"surface.skills={json.dumps(skills_val)} (expected [])")
except Exception as e:
    assert_fail(T_SKILLS1_LABEL, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("")
print(f"Results: {passed} passed, {failed} failed")

if failed > 0:
    sys.exit(1)
sys.exit(0)
