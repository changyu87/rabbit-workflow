#!/usr/bin/env python3
"""test-spec-housekeeping-679-dead-prose-removed.py — issue #679 (round 2 of #677).

End-to-end content regression that contract's live docs/spec.md no longer carries
the specific dead/historical-burden prose removed by the #679 measured line-removal
pass. Each banned phrase below was verified DEAD by a deterministic #639 check at
removal time (a reference to a deleted hook, a retired invariant, or pure
historical-edit narration) — the surface describes the CURRENT design, so this
narration belongs in commit messages and the CHANGELOG, not the spec body.

The phrases removed and the #639 check that proved each dead:

  1. "written by the PreToolUse `prompt-injector.py` hook from Inv 55" (Inv 39)
     — path/symbol check: `prompt-injector.py` is not git-tracked anywhere in the
       real surface and Inv 55 is RETIRED (CHANGELOG "Retired invariants" entry
       Inv 55). The dead cross-reference to a deleted hook + retired invariant is
       removed; the surviving function contract for
       `check_prompt_injection_failures` is preserved.

  2. "The previous behavior (3 inlined line-2 variants in this function) is
     REMOVED in v1.51.1." (Inv 55) — historical-edit narration of a past
     refactor. The CURRENT behavior (delegate to banner-status.py) is stated
     immediately above; the "what it used to do and when it changed" sentence is
     CHANGELOG material (recorded verbatim in CHANGELOG v1.51.1).

  3. "All future line-2 variants — including the running variant introduced by
     rabbit-auto-evolve v0.7.5 — are picked up automatically without any change
     to contract." (Inv 55) — version-pinned forward-looking narration; the
     delegation contract already establishes that contract owns the mechanism and
     rabbit-auto-evolve owns the content.

  4. "The Surface list and the \"Plain-text templates\" template-marker-convention
     bullet have both been updated to remove all references to the dead template."
     (Inv 48) — historical-edit narration. The CURRENT invariant ("the dead
     template MUST NOT exist") is the normative statement; the past editing action
     that achieved compliance is CHANGELOG material.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim dead phrases that MUST be absent from the live spec body.
BANNED_PHRASES = [
    "written by the PreToolUse `prompt-injector.py` hook from Inv 55",
    "The previous behavior (3 inlined line-2 variants in this",
    "is REMOVED in v1.51.1",
    "introduced by rabbit-auto-evolve v0.7.5",
    "have both been updated to remove all references to the dead",
]

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


if not os.path.isfile(SPEC):
    fail("exist", f"missing surface: {SPEC}")
else:
    with open(SPEC) as f:
        body = f.read()
    for phrase in BANNED_PHRASES:
        if phrase in body:
            fail("dead-prose", f"dead phrase still present in docs/spec.md: {phrase!r}")
        else:
            ok("dead-prose", f"absent: {phrase!r}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-679-dead-prose-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-679-dead-prose-removed: all checks passed.")
sys.exit(0)
