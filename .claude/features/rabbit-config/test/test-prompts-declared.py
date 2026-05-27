#!/usr/bin/env python3
"""test-prompts-declared.py — Inv 19.

Validates that rabbit-config feature.json declares EXACTLY one prompts entry
for the rabbit-config skill with the required id, kind, inject, and slots.

  t1: prompts is a list of length 1
  t2: entry id == 'rabbit-config'
  t3: entry kind == 'skill'
  t4: entry inject == ['.claude/features/policy/philosophy.md',
                       '.claude/features/policy/coding-rules.md']
  t5: entry slots == ['args']
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

EXPECTED_INJECT = [
    ".claude/features/policy/philosophy.md",
    ".claude/features/policy/coding-rules.md",
]
EXPECTED_SLOTS = ["args"]

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


if not os.path.isfile(FEATURE_JSON):
    fail(0, f"feature.json not found at {FEATURE_JSON}")
    sys.exit(1)

with open(FEATURE_JSON) as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        fail(0, f"feature.json is not valid JSON: {e}")
        sys.exit(1)

prompts = data.get("prompts")

# t1: prompts is a list of length 1
if not isinstance(prompts, list) or len(prompts) != 1:
    fail(1, f"prompts must be a list of exactly 1 entry, got: {prompts!r}")
    print("test-prompts-declared: FAIL", file=sys.stderr)
    sys.exit(1)
ok(1, "prompts is a list of length 1")

entry = prompts[0]

# t2: id
if entry.get("id") != "rabbit-config":
    fail(2, f"prompts[0].id must be 'rabbit-config', got {entry.get('id')!r}")
else:
    ok(2, "prompts[0].id is 'rabbit-config'")

# t3: kind
if entry.get("kind") != "skill":
    fail(3, f"prompts[0].kind must be 'skill', got {entry.get('kind')!r}")
else:
    ok(3, "prompts[0].kind is 'skill'")

# t4: inject
if entry.get("inject") != EXPECTED_INJECT:
    fail(4, f"prompts[0].inject must be {EXPECTED_INJECT!r}, got {entry.get('inject')!r}")
else:
    ok(4, f"prompts[0].inject is {EXPECTED_INJECT!r}")

# t5: slots
if entry.get("slots") != EXPECTED_SLOTS:
    fail(5, f"prompts[0].slots must be {EXPECTED_SLOTS!r}, got {entry.get('slots')!r}")
else:
    ok(5, f"prompts[0].slots is {EXPECTED_SLOTS!r}")

if FAIL:
    print("test-prompts-declared: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-prompts-declared: all checks passed.")
