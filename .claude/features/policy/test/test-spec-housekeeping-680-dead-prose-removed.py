#!/usr/bin/env python3
"""test-spec-housekeeping-680-dead-prose-removed.py — issue #680 (round 2 of #677).

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when a cross-feature harness lints spec bodies against
their authoritative content-file source, making this per-feature redundancy
assertion subsumed.

End-to-end content regression that policy's live docs/spec.md no longer carries
the cross-surface-redundant prose collapsed by the #680 measured line-removal
pass, while STILL carrying the normative skeleton of every affected invariant.

Round 1 (#618) made the doc surfaces history-free; #680 is the measured REMOVAL
pass under #639 prove-it-dead-or-flag. The removed prose was not "historical
tags" — it was a third verbatim copy of rules that already live authoritatively
in the session-injected content files (`coding-rules.md` Section 6,
`spec-rules.md` Section 4) AND are enforced phrase-by-phrase by
`test/test-rule-files-content.py`. Per #677 rule 3 ("collapse cross-surface
redundancy to one authoritative statement") the spec invariant keeps only the
normative skeleton (what must exist + which test enforces it); the full rule
text stays in its one authoritative home.

The phrases removed and the #639 check that proved each redundant/dead:

  1. Inv 6 provenance — "propagates the lesson of rabbit-feature's spec-edit
     Read-before-Edit obligation" / "remains stable across rabbit-feature
     renumbers". Cross-feature provenance narration. The normative directive
     (the named principle must state (a)/(b)/(c) and be named-not-numbered)
     survives; the "why it mirrors rabbit-feature" rationale is CHANGELOG
     material.

  2. Inv 12 body — the full re-description of the four #639 check kinds, the
     three-row action table, and the annotate-and-continue discipline. Verified
     redundant: every distinctive phrase is asserted against `coding-rules.md`
     by `test/test-rule-files-content.py` (grep) and the authoritative rule text
     lives in `coding-rules.md` Section 6 (injected every session). The spec
     keeps the presence requirement + the enforcing-test pointer.

  3. Inv 13 body — the full re-description of the no-nesting rule (illegal
     two-level nesting, dispatch underlying subagent at level 1, named
     subagent-dispatching skills). Verified redundant: the distinctive phrases
     are asserted against `spec-rules.md` by `test/test-rule-files-content.py`
     and the authoritative rule text lives in `spec-rules.md` Section 4. The
     spec keeps the presence requirement + the enforcing-test pointer.

This test asserts BOTH directions: the banned phrases are absent AND the
surviving normative anchors are still present (so a future over-zealous pass
cannot delete the invariant skeleton and stay green here).

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim redundant phrases that MUST be absent from the live spec body.
BANNED_PHRASES = [
    "propagates the lesson of rabbit-feature's spec-edit",
    "remains stable across rabbit-feature renumbers",
    "a path reference is\n    `find`-ed across the repo",
    "a described behavior must have a reachable code path",
    "annotate-and-continue discipline: an unverifiable sentence is flagged",
    "creates illegal two-level nesting (`main → Agent level 1 → subagent",
    "parallelization of such a skill be done by dispatching the underlying",
]

# Normative anchors that MUST remain (the skeleton of each collapsed invariant).
REQUIRED_PHRASES = [
    # Inv 6 — the named-not-numbered directive survives.
    "named, not numbered",
    # Inv 12 — presence requirement + enforcing-test pointer survive.
    "Prove-it-dead-or-flag cleanup methodology present.",
    "test/test-rule-files-content.py",
    # Inv 13 — presence requirement + enforcing-test pointer survive.
    "No subagent-dispatching skill inside",
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
            fail("dead-prose", f"redundant phrase still present in docs/spec.md: {phrase!r}")
        else:
            ok("dead-prose", f"absent: {phrase!r}")
    for phrase in REQUIRED_PHRASES:
        if phrase in body:
            ok("anchor", f"present: {phrase!r}")
        else:
            fail("anchor", f"normative anchor missing from docs/spec.md: {phrase!r}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-680-dead-prose-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-680-dead-prose-removed: all checks passed.")
sys.exit(0)
