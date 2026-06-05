#!/usr/bin/env python3
"""test-spec-housekeeping-817-dead-prose-removed.py — issue #817 (final child of #794).

End-to-end content regression that tdd-subagent's live docs/spec.md no longer
carries the redundant restatement, restated rationale, and decorative
parentheticals removed by the #817 measured reduction wave. Each banned phrase
below was verified REDUNDANT or DECORATIVE at removal time: a section-intro
restating an invariant body, a "Rationale:"/"de facto" meta-clause whose rule is
already stated, a cross-feature informational aside that constrains no
tdd-subagent behavior, or an illustrative figure naming a retired feature. The
surface describes the CURRENT design; rationale and history belong in the
CHANGELOG, not the spec body.

Each removed phrase and why it was dead/redundant:

  1. "builds a slot dict and delegates prompt" (## Invariants preamble) —
     restated Inv 44's slot/build-prompt mechanics plus an Inv 23/24 restatement
     of where the bypass note APPEARS. The CURRENT facts live in Inv 44 / 23 / 24.

  2. "in practice `0o755` or `0o775`" (Inv 37) — decorative parenthetical; the
     load-bearing rule is `mode & 0o100`.

  3. "Distinct semantics → distinct verbs → distinct audit trail." (Inv 50) —
     restates the preceding abort-vs-force sentence.

  4. "Rationale: abort is" (Inv 51) — restated rationale; the accepted/rejected
     state rule is stated fully above it.

  5. "Typical scoped prompts are 20-30KB" (Inv 49e) — decorative figures naming
     the retired rabbit-config feature; the load-bearing claim is the size-win
     direction plus the "no worse when omitted" guarantee.

  6. "The same precedence ladder is shared with other" (Inv 47) — cross-feature
     informational aside constraining no tdd-subagent behavior.

  7. "This invariant documents the de facto behavior" (Inv 54) — meta-preamble;
     the HANDOFF-only rule that follows it stands on its own.

  8. "even though the dispatcher no longer emits item-close" (Inv 21) — past-state
     narration; the forward-compatibility retention fact (per Inv 22) stands.

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Verbatim redundant/decorative phrases that MUST be absent from the live spec body.
BANNED_PHRASES = [
    "builds a slot dict and delegates prompt",
    "in practice `0o755` or `0o775`",
    "Distinct semantics → distinct verbs → distinct audit trail.",
    "Rationale: abort is",
    "Typical scoped prompts are 20-30KB",
    "The same precedence ladder is shared with other",
    "This invariant documents the de facto behavior",
    "even though the dispatcher no longer emits item-close",
]

# Measured line-removal ceiling: the #689 pass left spec.md at 798 lines. The
# #817 wave MUST cut real lines, not reword. Assert a ceiling below the #689
# floor so a future reword cannot re-inflate the body.
SPEC_LINE_CEILING = 790

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
             "the #817 wave must REMOVE lines, not reword")
    else:
        ok("line-floor", f"docs/spec.md is {n_lines} lines (<= {SPEC_LINE_CEILING})")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-housekeeping-817-dead-prose-removed: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-housekeeping-817-dead-prose-removed: all checks passed.")
sys.exit(0)
