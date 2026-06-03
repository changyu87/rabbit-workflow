#!/usr/bin/env python3
"""test-spec-scripted-phase-walk-invariant.py — rabbit-auto-evolve scripted
phase-walk convergence invariant (Inv 40 / issue #513).

Asserts the invariant text is present in the feature spec (specs/spec.md) AND
that the source SKILL.md describes the in-session tick as running the shared
scripted phase-walk (the dispatcher supplies only Phase 5), not a prose
sequence the LLM bridges by hand.

The invariant states:
  (a) ONE shared deterministic phase-walk implementation
      (`run-tick-phases.py`) that BOTH the headless and in-session paths
      invoke;
  (b) the in-session path differs ONLY by inserting Phase 5 (dispatch);
  (c) Phase 10 persist re-reads on-disk state, drops the transient
      `merge_ready`, and pipes through `update-state.py` — the dispatcher
      NEVER reads update-state.py source or the schema to hand-assemble state;
  (d) no in-session phase handoff requires the dispatcher to hand-assemble a
      data structure — every handoff is script-to-script.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
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
    # (a) one shared scripted phase-walk both paths invoke.
    "run-tick-phases.py",
    "scripted phase-walk",
    # (b) in-session differs only by Phase 5 (dispatch).
    "phase 5",
    # (c) persist re-reads from disk, drops merge_ready, pipes through update-state.
    "merge_ready",
    "update-state.py",
    # (d) script-to-script handoffs, no LLM hand-assembly.
    "hand-assemble",
]
missing = [s for s in REQUIRED_SPEC if s not in spec_lower]
if missing:
    fail(f"spec.md missing scripted-phase-walk invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the scripted-phase-walk convergence invariant (Inv 40)")

# The invariant must be numbered 40 (next monotonic number in this feature).
if re.search(r"(?m)^\s*40\.\s", SPEC_MD.read_text()):
    ok("spec.md numbers the new invariant as 40 (next monotonic)")
else:
    fail("spec.md does not carry a list item numbered 40")

# SKILL.md describes the in-session tick via the shared scripted phase-walk.
skill_lower = re.sub(r"\s+", " ", SKILL_MD.read_text().lower())
REQUIRED_SKILL = [
    "run-tick-phases.py",
    "phase 5",
]
missing_skill = [s for s in REQUIRED_SKILL if s not in skill_lower]
if missing_skill:
    fail(f"SKILL.md missing scripted-phase-walk phrase(s): {missing_skill!r}")
else:
    ok("SKILL.md describes the in-session tick via run-tick-phases.py + Phase 5")

# SKILL.md must affirmatively forbid the #513 anti-pattern: reading
# update-state.py source / the schema to hand-assemble the new-state object.
# Match the prohibition as a negated clause ("does not read ... update-state.py
# source or ... schema to assemble state"); any non-negated instruction to do
# so is the anti-pattern.
PROHIBITION = re.compile(
    r"not read [^.]{0,40}update-state\.py`? source or the state schema")
INSTRUCTION = re.compile(
    r"(?<!not )read [^.]{0,30}update-state\.py`? source or the (state )?schema "
    r"to (assemble|build|construct)")
if INSTRUCTION.search(skill_lower):
    fail("SKILL.md instructs reading update-state.py source/schema to build state")
elif PROHIBITION.search(skill_lower):
    ok("SKILL.md affirmatively forbids hand-assembling state from update-state.py source")
else:
    fail("SKILL.md neither forbids nor mentions the update-state.py source anti-pattern")

sys.exit(FAIL)
