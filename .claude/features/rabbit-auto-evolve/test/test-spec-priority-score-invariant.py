#!/usr/bin/env python3
"""test-spec-priority-score-invariant.py — rabbit-auto-evolve Inv 46
(issue #441).

Asserts the loop-computed-priority-score invariant text is present in the
feature spec (specs/spec.md, dual-read with docs/spec/ fallback per issue
#399). The invariant states:
  - the loop computes its OWN priority score from observable signals;
  - the filer-set priority: label is ONE input among several, no longer
    the sole determinant;
  - the score is the PRIMARY dispatch-ordering key, with the contract-touch
    barrier preserved as the SECONDARY tiebreak (refining issue #479) and
    issue number as the final tiebreak;
  - the score is computed deterministically in a script (not by LLM
    inference) and is emitted for transparency.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Dual-read (issue #399): prefer the flat docs/spec.md layout, fall back to
# specs/spec.md, then legacy docs/spec/spec.md.
SPEC_MD = (FEATURE_DIR / "docs" / "spec.md")
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
    # The loop computes its own score.
    "loop computes its own priority score",
    # Filer label is one input among several.
    "filer label is one input among several",
    # Observable signals named.
    "blocking-fanout",
    # Computed score is the primary ordering key.
    "computed score is the primary",
    # The contract-touch barrier remains the secondary tiebreak (refines #479).
    "contract-touch barrier",
    # Determinism / script-tier.
    "computed in a script",
    # Transparency requirement.
    "computed_scores",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing priority-score-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the loop-computed-priority-score invariant (Inv 46)")

# The invariant MUST reconcile with #479 explicitly (not silently override it).
if "479" not in lowered:
    fail("spec.md priority-score invariant must reference issue #479 "
         "(the composite key it refines)")
else:
    ok("spec.md priority-score invariant reconciles with issue #479")

sys.exit(FAIL)
