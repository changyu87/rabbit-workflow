#!/usr/bin/env python3
"""test-spec-native-deps-blocked-invariant.py — rabbit-auto-evolve Inv 59
(issue #942).

Asserts the native-dependency-authoritative blocked-state invariant text is
present in the feature spec (docs/spec.md, dual-read with specs/ then legacy
docs/spec/ fallback per issue #399). The invariant states:
  - the GitHub-native dependency relationship is the AUTHORITATIVE source of an
    issue's blocked state (read via
    `gh api repos/{slug}/issues/<n>/dependencies/blocked_by`);
  - an OPEN native blocker defers `blocked`; all-closed/absent is not blocked;
  - the body `blocked-by:` text declaration / legacy label is a DEPRECATING
    coexistence mirror consulted only when the native source reports no open
    blocker;
  - a deprecation criterion is named.

Mirrors the spec-invariant test pattern (substring presence over the
whitespace-normalized lowered spec text).
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


text = SPEC_MD.read_text()
lowered = re.sub(r"\s+", " ", text.lower())

REQUIRED = [
    # Native graph is the authoritative blocked-state source.
    "github-native dependency relationship is the authoritative source",
    # The exact native read endpoint.
    "dependencies/blocked_by",
    # Open native blocker -> defer blocked.
    "open native blocker",
    # Body text / label is a deprecating coexistence mirror.
    "deprecating coexistence mirror",
    # A deprecation criterion is named for the body parser + legacy label.
    "deprecation criterion",
    # The write path prefers creating the native relationship.
    "--method post",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing native-deps-blocked-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the native-dependency-authoritative blocked-state "
       "invariant (Inv 59)")

# The invariant is numbered 59 and present as a list item.
if not re.search(r"(?m)^59\.\s+\*\*", text):
    fail("spec.md does not carry a numbered Inv 59 list item")
else:
    ok("spec.md carries the numbered Inv 59 list item")

sys.exit(FAIL)
