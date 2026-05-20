#!/usr/bin/env python3
# E2E test for TDD-SUBAGENT-BACKLOG-6.
#
# BACKLOG-6: feature.json schema reference declared in spec; the contract
#            schema enum lists `spec-update`.
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "tdd-subagent")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
SCHEMA = os.path.join(
    REPO_ROOT, ".claude", "features", "contract", "schemas", "feature.json.schema.json"
)

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


# BACKLOG-6: spec invariant references the contract schema; spec also names
# the flat fields used by tdd-subagent.
# Note: the contract-owned schema enum gap (missing `spec-update`) is
# explicitly out of scope and filed via a follow-up backlog under
# rabbit/features/contract/backlogs/ — this test does not cover it.
def b6():
    with open(SPEC_MD) as f:
        spec = f.read()
    if "feature.json.schema.json" not in spec:
        ko("b6: spec does not reference feature.json.schema.json")
        return
    # After the slim-after-extraction renumber (spec v2.0.0), survivors are
    # numbered 1..20; the schema-reference invariant is now Inv 18. (History:
    # Inv 33 → Inv 29 (v1.19.0) → Inv 25 (v1.20.0) → Inv 18 (v2.0.0).) Accept
    # either explicit "Inv 18" reference or any numbered line referencing the
    # schema file.
    schema_inv_match = re.search(
        r"^(\d+)\.\s.*feature\.json\.schema\.json",
        spec, re.MULTILINE | re.DOTALL,
    )
    if schema_inv_match:
        ok(f"b6a: spec declares feature.json schema reference (Inv {schema_inv_match.group(1)})")
    else:
        ko("b6a: spec missing numbered invariant referencing feature.json.schema.json")
        return
    # b6b: spec names the flat-shape fields the tdd-subagent depends on.
    for needed in ("deprecation_criterion", "tdd_state", "surface", "owner"):
        if needed not in spec:
            ko(f"b6b: spec missing reference to flat field '{needed}'")
            return
    if not os.path.isfile(SCHEMA):
        ko(f"b6: schema file missing: {SCHEMA}")
        return
    ok("b6b: spec names flat-shape fields tdd-subagent depends on")


b6()

print()
if FAIL == 0:
    print(f"backlog-6: {PASS} passed.")
    sys.exit(0)
print(f"backlog-6: {FAIL} failure(s), {PASS} passed.")
sys.exit(1)
