#!/usr/bin/env python3
"""test-spec-housekeeping-681-dead-prose-removed.py — issue #681 (round 2 of #677, under #639).

End-to-end content regression that rabbit-auto-evolve's live docs/spec.md no longer
carries the specific dead / historical-burden prose removed by the #681 measured
line-removal pass. rabbit-auto-evolve is THE WHALE (its spec is ~half of all spec
content); round 1 reworded instead of removing, so this pass DELETES proven-dead
narration and proves it stays gone.

Each banned phrase below was verified DEAD by a deterministic #639 check at removal
time — pre-implementation narration of a feature that is now fully built, or a
"will happen / used to happen" cross-feature refactor narration whose follow-up has
already landed. The surface describes the CURRENT design; this narration belongs in
the CHANGELOG and commit history, not the spec body.

The phrases removed and the #639 check that proved each dead:

  1. "## Open questions (to resolve during Phases C-E)" (whole section)
     — behavior check: the feature is fully implemented; the pre-implementation
       open questions are resolved (the RESOLVED ones are tagged so) or moot. The
       resolved facts live in the relevant invariants and in the scripts'
       docstrings ("resolved Open Question N").

  2. "These were surfaced by the spec-creator subagent and require dispatcher /
     owner decisions during component implementation." (Open-questions preamble)
     — same: component implementation is done.

  3. "**Ownership migration:** As of v0.7.5 the line-2 text variants" (Inv 22)
     and "this invariant will be revised to defer line-2 ownership to Inv 22"
     (Inv 14) — cross-feature inspection: contract.lib.runtime.emit_auto_evolve_banner
       NOW delegates to scripts/banner-status.py (the "follow-up cycle" the prose
       said had NOT yet landed). The "still inlines / does NOT yet call / until
       that follow-up lands" narration is dead; the current normative contract
       (banner-status.py owns line-2) survives.

  4. "The current target is `0.4.0` (set during Phase E" (Inv 15)
     — symbol check: the live version is 0.48.3, not 0.4.0; the "current target"
       sentence is stale historical narration. The normative rule (all four
       version fields agree) survives.

  5. "steps that the in-session `start` sequence used to run before invoking
     the walk are removed" (Inv 42) — historical-edit narration of a past
     refactor. The current normative statement ("start-loop.py does NOT write
     the running marker; the walk owns the guard->mark sequence") precedes it.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim dead phrases that MUST be absent from the live spec body.
BANNED_PHRASES = [
    "## Open questions (to resolve during Phases",
    "These were surfaced by the spec-creator subagent",
    "As of v0.7.5 the line-2 text variants",
    "this invariant will be revised to defer",
    "The current target is `0.4.0`",
    "used to run before invoking\n       the walk are removed",
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
    print("test-spec-housekeeping-681-dead-prose-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-681-dead-prose-removed: all checks passed.")
sys.exit(0)
