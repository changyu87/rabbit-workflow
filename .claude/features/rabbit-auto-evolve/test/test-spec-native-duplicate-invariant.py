#!/usr/bin/env python3
"""test-spec-native-duplicate-invariant.py — rabbit-auto-evolve Inv 60.

Asserts the native-duplicate-authoritative resolution invariant text is
present in the feature spec (docs/spec.md, dual-read with specs/ then legacy
docs/spec/ fallback). The invariant states:
  - the GitHub-native duplicate state (`state_reason=duplicate`) is the
    AUTHORITATIVE resolution of a detected duplicate;
  - DETECTION (the title-substring heuristic with its confidence gate) is
    UNCHANGED — only RESOLUTION changes;
  - the close is a terminal convergence (Inv 25), never a
    label-strip-while-open de-queue;
  - the reinvented `duplicate` label is a DEPRECATING coexistence mirror
    honored only on read;
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
    # Native duplicate state is the authoritative resolution.
    "github-native duplicate state is the authoritative resolution",
    # The exact native write marker.
    "state_reason=duplicate",
    # Detection is unchanged / confidence gate preserved.
    "detection is unchanged",
    "confidence gate",
    # The resolution script.
    "resolve-duplicate.py",
    # The reinvented label is a deprecating coexistence mirror.
    "deprecating coexistence mirror",
    # A deprecation criterion is named.
    "deprecation criterion",
    # Terminal convergence, never a de-queue.
    "label-strip-while-open de-queue",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing native-duplicate-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the native-duplicate-authoritative resolution "
       "invariant (Inv 60)")

# The invariant is numbered 60 and present as a list item.
if not re.search(r"(?m)^60\.\s+\*\*", text):
    fail("spec.md does not carry a numbered Inv 60 list item")
else:
    ok("spec.md carries the numbered Inv 60 list item")

sys.exit(FAIL)
