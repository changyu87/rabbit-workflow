#!/usr/bin/env python3
"""test-spec-forbid-dequeue-invariant.py — rabbit-auto-evolve (issue #731).

Asserts the de-queue-forbidding convergence fix is present:

  (a) The convergence guarantee (Inv 25 area) is label-INDEPENDENT: an open
      VALID issue must converge to a terminal-or-tracked state REGARDLESS of
      whether it still carries `rabbit-managed`, and removing the label while
      open is explicitly NOT a convergence outcome.

  (b) The Red-Flag de-queue ban is present in docs/spec.md as an explicit
      invariant: the dispatcher MUST NOT remove `rabbit-managed` from an OPEN
      issue as a parking / hand-back action.

  (c) The Red-Flag de-queue ban literal string is present in the SKILL.md
      `Red Flags — STOP` section, alongside the AskUserQuestion ban.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"

# The literal Red-Flag string that MUST appear verbatim in BOTH spec.md and
# SKILL.md (the spec records the literal SKILL string per the Inv 13 pattern).
DEQUEUE_LITERAL = (
    "the dispatcher MUST NOT remove `rabbit-managed` from an OPEN issue "
    "as a parking or hand-back action"
)

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


spec_text = SPEC_MD.read_text()
skill_text = SKILL_MD.read_text()
# Collapse whitespace so line-wrapped prose still matches the substrings.
spec_flat = re.sub(r"\s+", " ", spec_text)
spec_lower = spec_flat.lower()

# (a) label-independent convergence wording
LABEL_INDEP_PHRASES = [
    "regardless of whether it still carries `rabbit-managed`",
    "removing the label while an issue is open",
    "not a convergence outcome",
]
missing_a = [p for p in LABEL_INDEP_PHRASES if p.lower() not in spec_lower]
if missing_a:
    fail(f"spec.md missing label-independent convergence phrase(s): {missing_a!r}")
else:
    ok("(a) spec.md convergence guarantee is label-independent")

# (b) de-queue Red-Flag literal present in spec.md
if DEQUEUE_LITERAL not in spec_flat:
    fail(f"spec.md missing de-queue Red-Flag literal: {DEQUEUE_LITERAL!r}")
else:
    ok("(b) spec.md carries the de-queue Red-Flag literal")

# (c) de-queue Red-Flag literal present in SKILL.md Red Flags section
if "Red Flags — STOP" not in skill_text:
    fail("SKILL.md missing the 'Red Flags — STOP' section")
skill_flat = re.sub(r"\s+", " ", skill_text)
if DEQUEUE_LITERAL not in skill_flat:
    fail(f"SKILL.md missing de-queue Red-Flag literal: {DEQUEUE_LITERAL!r}")
else:
    ok("(c) SKILL.md Red Flags section carries the de-queue ban literal")

sys.exit(FAIL)
