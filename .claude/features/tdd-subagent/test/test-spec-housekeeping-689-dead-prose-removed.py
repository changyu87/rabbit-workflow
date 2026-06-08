#!/usr/bin/env python3
"""test-spec-housekeeping-689-dead-prose-removed.py — issue #689 (round 2 of #677).

End-to-end content regression that tdd-subagent's live docs/spec.md no longer
carries the dead / historical / redundant prose removed by the #689 measured
line-removal pass. Each banned phrase below was verified DEAD or REDUNDANT by a
deterministic #639 check at removal time (past-defect narration, a one-time
implementation directive whose work is already committed, a version-pinned
historical note, or a verbose restatement of a test's internal scenarios). The
surface describes the CURRENT design; this narration belongs in the CHANGELOG,
not the spec body.

The phrases removed and the #639 check that proved each dead/redundant:

  1. "As of the CONTRACT-BACKLOG-1" (## Invariants preamble) — historical
     migration narration. The CURRENT fact (template-based assembly via
     build-prompt.py) is fully stated in Inv 44. grep: no test asserts the
     migration note's presence.

  2. "Before this invariant was made mode-aware" (Inv 12) — past-defect
     narration of the inert-plugin-marker bug. The CURRENT two-mode rule is
     fully stated above it.

  3. "`_policy_block` helper function and its call site" (Inv 44) — one-time
     migration directive. grep of dispatch-tdd-subagent.py: `_policy_block`
     and `policy-block.py` have zero matches (proven dead/done).

  4. "Mirroring constraint: this matches the resolution pattern already in"
     (Inv 47) — cross-feature narration carrying a rotting line-number pin
     (`lines ~60-70`). The fallback ladder is the authoritative constraint.

  5. "The observed effect was direct `Write`/`Edit` on" (Inv 57) — past-defect
     narration. The CURRENT constraint (tools list MUST include Skill) stands.

  6. "**Why.** Previously these slots were absolute paths rooted at the MAIN"
     (Inv 58) — past-defect narration. The cwd-relative rule is fully stated.

  7. "Pre-v4.0.0 this entry lived on" (Inv 29 manifest) — historical
     provenance of the tdd-step.py publish_file entry.

  8. "The `sync-deployed` state was added in v5.1.0" (Inv 31) — version-pinned
     historical note. The CURRENT fact (sync-deployed lands STEP 5) stands.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim dead/redundant phrases that MUST be absent from the live spec body.
BANNED_PHRASES = [
    "As of the CONTRACT-BACKLOG-1",
    "Before this invariant was made mode-aware",
    "`_policy_block` helper function and its call site",
    "Mirroring constraint: this matches the resolution pattern already in",
    "The observed effect was direct `Write`/`Edit` on",
    "**Why.** Previously these slots were absolute paths rooted at the MAIN",
    "Pre-v4.0.0 this entry lived on",
    "The `sync-deployed` state was added in v5.1.0",
]

# Measured line-removal floor: round-1 left spec.md at 906 lines. The #689 pass
# MUST cut real lines, not reword. Assert a hard ceiling well below the starting
# count so a future reword that re-inflates the body fails the gate.
# Bumped in lockstep with genuine new invariants (Inv 63, Inv 64).
SPEC_LINE_CEILING = 838

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

    n_lines = body.count("\n") + (0 if body.endswith("\n") else 1)
    if n_lines > SPEC_LINE_CEILING:
        fail("line-floor",
             f"docs/spec.md is {n_lines} lines (> ceiling {SPEC_LINE_CEILING}); "
             "the #689 pass must REMOVE lines, not reword")
    else:
        ok("line-floor", f"docs/spec.md is {n_lines} lines (<= {SPEC_LINE_CEILING})")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-689-dead-prose-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-689-dead-prose-removed: all checks passed.")
sys.exit(0)
