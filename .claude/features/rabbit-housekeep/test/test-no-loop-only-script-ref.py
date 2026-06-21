#!/usr/bin/env python3
"""test-no-loop-only-script-ref.py — guard that the deployed-surface
rabbit-housekeep SKILL.md carries NO live reference to a loop-only,
non-shipped backing script (issue #1182).

rabbit-housekeep's SKILL.md is part of rabbit-cage's vendored install closure
(#1181). rabbit-auto-evolve — the self-driving loop feature — is deliberately
ABSENT from that closure. A literal
`.claude/features/rabbit-auto-evolve/scripts/<script>.py` path in the SKILL.md
body is treated as a "referenced backing script" by BOTH rabbit-cage gates:

  - test-feature-includes-scripts-closure.py (Inv 24), and
  - test-install-ships-skill-referenced-scripts.py (#897/#1035 e2e),

each of which scans deployed SKILL/command bodies with the regex below and
demands the referenced script ship on disk. Because record-decomposition.py is
loop-only and never shipped, such a reference is a referenced-but-missing
script that fails both gates in a vendored install.

This test mirrors the rabbit-cage scanner's exact detection regex against the
SOURCE SKILL.md body and asserts ZERO rabbit-auto-evolve script references
survive in it. The decomposition-recording is loop-only machinery handled
automatically by the auto-evolve loop, NOT a step a user runs in the
user-facing housekeep wave — so it must not appear as a live invocation on the
deployed surface.

The cross-feature INVOKE declaration in docs/contract.md is the proper machine
home for the loop's reuse and is NOT scanned by the rabbit-cage gates (they
scan only shipped SKILL/command bodies); this test therefore targets the
SKILL.md body alone.

Non-interactive. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-housekeep is retired.
"""
import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SKILL_MD = os.path.join(
    FEATURE_DIR, "skills", "rabbit-housekeep", "SKILL.md"
)

# IDENTICAL to rabbit-cage's SCRIPT_REF_RE in
# test-feature-includes-scripts-closure.py and
# test-install-ships-skill-referenced-scripts.py: a literal path under
# .claude/features/<feature>/scripts/<script>.py OR the skill-local form
# .claude/features/<feature>/skills/<skill>/scripts/<script>.py.
# Group 1 is the owning feature; group 2 the feature-relative script path.
SCRIPT_REF_RE = re.compile(
    r"\.claude/features/([\w-]+)/((?:skills/[\w-]+/)?scripts/[\w.-]+\.py)"
)

# Features deliberately ABSENT from rabbit-cage's vendored install closure.
# A deployed-surface body MUST NOT reference a backing script owned by one of
# these — the script will never ship, so the reference is referenced-but-missing.
NON_SHIPPED_FEATURES = {"rabbit-auto-evolve"}

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


if not os.path.isfile(SKILL_MD):
    fail("t0", f"missing: {SKILL_MD}")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "SKILL.md exists")

with open(SKILL_MD, encoding="utf-8") as f:
    body = f.read()

refs = SCRIPT_REF_RE.findall(body)
offending = sorted(
    f".claude/features/{feat}/{rel}"
    for feat, rel in refs
    if feat in NON_SHIPPED_FEATURES
)

# t1: no deployed-surface reference to any non-shipped (loop-only) script.
if not offending:
    ok("t1", "SKILL.md has no deployed-surface reference to a non-shipped "
             "loop-only script")
else:
    fail("t1", "SKILL.md carries deployed-surface reference(s) to non-shipped "
               "loop-only script(s) — fails rabbit-cage Inv 24 / install e2e "
               f"(#1182): {offending}")

# t2: specifically, the loop-only record-decomposition.py is gone from the body.
if "rabbit-auto-evolve/scripts/record-decomposition.py" not in body:
    ok("t2", "record-decomposition.py loop-only path absent from SKILL.md body")
else:
    fail("t2", "record-decomposition.py loop-only path still present in "
               "SKILL.md body (#1182)")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
