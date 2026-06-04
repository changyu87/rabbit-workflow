#!/usr/bin/env python3
"""test-spec-housekeeping-695-current-behaviour-preamble-removed.py — issue #695 (follow-up of #681, under #639).

End-to-end content regression that rabbit-auto-evolve's live docs/spec.md no longer
carries the stale pre-implementation "Current behaviour" preamble removed by the #695
housekeeping pass. #681 could not remove it (the contract historical-tags ALLOWLIST
was line-number-pinned, so the 5-line removal shifted a 'retired' status-enum row and
reddened the gate); #696 fixed that allowlist to be content-keyed, so the removal is
now safe.

#639 VERIFICATION that proved the preamble DEAD at removal time:
  - The preamble claimed "The feature directory was scaffolded in Phase B of the plan.
    No scripts, no SKILL.md, and no tests exist yet ... become verifiable once Phase C
    through Phase E merges complete."
  - behavior check: the feature is fully implemented — 36+ scripts under scripts/, a
    deployed SKILL.md, and 70+ tests under test/ all exist and pass (test/run.py GREEN).
    "Known gaps" already states "All implementation phases complete." The claim is
    false historical narration; it belongs in the CHANGELOG, not the spec body.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim dead phrases that MUST be absent from the live spec body.
# NOTE: the "## Current behaviour" header itself is a LIVE section title for the
# behaviour bullets that follow; only the false pre-implementation scaffolding
# paragraph beneath it is dead and removed here.
BANNED_PHRASES = [
    "The feature directory was scaffolded in Phase B of the plan",
    "No scripts,\nno SKILL.md, and no tests exist yet",
    "become verifiable once Phase C through\nPhase E merges complete",
    "they become verifiable once",
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
            fail("dead-preamble", f"dead phrase still present in docs/spec.md: {phrase!r}")
        else:
            ok("dead-preamble", f"absent: {phrase!r}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-695-current-behaviour-preamble-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-695-current-behaviour-preamble-removed: all checks passed.")
sys.exit(0)
