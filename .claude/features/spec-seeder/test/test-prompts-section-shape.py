#!/usr/bin/env python3
"""test-prompts-section-shape.py — spec-seeder Inv 3: feature.json prompts entry shape."""

import json
import os
import sys

FEATURE_JSON = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "feature.json",
))

PASS = 0
FAIL = 0


def ok(n, m):
    global PASS
    print(f"  PASS {n}: {m}")
    PASS += 1


def fail_t(n, m):
    global FAIL
    print(f"  FAIL {n}: {m}", file=sys.stderr)
    FAIL += 1


with open(FEATURE_JSON) as f:
    fj = json.load(f)

prompts = fj.get("prompts", [])
if len(prompts) == 1:
    ok("t1", "feature.json has exactly one prompts entry")
else:
    fail_t("t1", f"expected 1 prompts entry, got {len(prompts)}")
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    sys.exit(1)

entry = prompts[0]

if entry.get("id") == "spec-seeder":
    ok("t2", "id == spec-seeder")
else:
    fail_t("t2", f"id == {entry.get('id')!r} (expected 'spec-seeder')")

if entry.get("kind") == "subagent":
    ok("t3", "kind == subagent")
else:
    fail_t("t3", f"kind == {entry.get('kind')!r} (expected 'subagent')")

inject = entry.get("inject", [])
expected_inject = {
    ".claude/features/policy/philosophy.md",
    ".claude/features/policy/coding-rules.md",
}
if expected_inject.issubset(set(inject)):
    ok("t4", f"inject contains philosophy + coding-rules")
else:
    fail_t("t4", f"inject={inject!r} missing some of {expected_inject!r}")

slots = entry.get("slots", [])
if slots == ["feature_name", "paths_globs", "paths_resolved"]:
    ok("t5", "slots == [feature_name, paths_globs, paths_resolved]")
else:
    fail_t("t5", f"slots == {slots!r} (expected exact list)")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
