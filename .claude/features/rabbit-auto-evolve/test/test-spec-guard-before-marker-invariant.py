#!/usr/bin/env python3
"""test-spec-guard-before-marker-invariant.py — rabbit-auto-evolve
guard-before-marker invariant (Inv 42).

Asserts the invariant text is present in the feature spec (specs/spec.md) AND
that the source SKILL.md describes the corrected ordering: the explicit user
`start` runs cancel-stop + bootstrap (start-loop.py) then invokes the shared
phase-walk, and the shared phase-walk runs the running-guard FIRST and writes
the `.rabbit-auto-evolve-running` marker only after the guard returns proceed —
so neither path false-skips on a marker it itself wrote.

The invariant states:
  (a) the shared phase-walk (run-tick-phases.py pre-dispatch) runs the
      running-guard FIRST and writes the running marker ONLY on proceed;
  (b) start-loop.py (the explicit-start entry) runs cancel-stop + bootstrap and
      no longer writes the running marker;
  (c) a MACHINE tick invokes the walk directly with NO cancel-stop (Inv 41
      preserved); an explicit user start DOES cancel a pending stop (Inv 19).
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Resolve the feature spec dual-read (issue #399): prefer the flat
# docs/spec.md layout, fall back to specs/spec.md, then legacy docs/spec/.
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


spec_lower = re.sub(r"\s+", " ", SPEC_MD.read_text().lower())

REQUIRED_SPEC = [
    "run-tick-phases.py",
    "running-guard",
    ".rabbit-auto-evolve-running",
    "start-loop.py",
    "cancel",
]
missing = [s for s in REQUIRED_SPEC if s not in spec_lower]
if missing:
    fail(f"spec.md missing guard-before-marker phrase(s): {missing!r}")
else:
    ok("spec.md carries the guard-before-marker invariant phrases (Inv 42)")

# The invariant must be numbered 42 (next monotonic number in this feature).
if re.search(r"(?m)^\s*42\.\s", SPEC_MD.read_text()):
    ok("spec.md numbers the new invariant as 42 (next monotonic)")
else:
    fail("spec.md does not carry a list item numbered 42")

# SKILL.md describes the corrected ordering on both the start and tick paths.
skill_lower = re.sub(r"\s+", " ", SKILL_MD.read_text().lower())
REQUIRED_SKILL = [
    "run-tick-phases.py",
    "start-loop.py",
]
missing_skill = [s for s in REQUIRED_SKILL if s not in skill_lower]
if missing_skill:
    fail(f"SKILL.md missing guard-before-marker phrase(s): {missing_skill!r}")
else:
    ok("SKILL.md describes start-loop.py + the shared walk ordering")

sys.exit(FAIL)
