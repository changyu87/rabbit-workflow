#!/usr/bin/env python3
"""test-spec-self-observed-error-capture-invariant.py — rabbit-auto-evolve
Inv 67 (issue #1091).

Asserts the self-observed-error-capture invariant text is present in the
feature spec (docs/spec.md, dual-read with specs/ and legacy docs/spec/
fallback). The invariant states:

  - WHEN the orchestrator must capture a self-observed error: a non-zero
    bash/script exit, unexpected stderr/output, or an anomaly mid-tick;
  - the analysis runs in an ISOLATED subagent (context isolation) — NOT inline
    in the dispatcher's own accumulating context (the session-reuse /
    croncreate path accumulates context across ticks);
  - the isolated analysis subagent returns a STRUCTURED verdict; the
    orchestrator then files a well-formed issue via rabbit-issue file-item.py
    with the right feature: + priority: labels for a LATER tick;
  - the deterministic prompt-assembly + file-item argv live in the script
    `capture-observed-error.py` (Tool-Choice Tier: script > spec > prompt);
  - the capture dispatch is a MAIN-SESSION / level-1 Agent() dispatch (exactly
    like the Phase-6 TDD dispatch), NOT nested inside another subagent — no
    illegal two-level nesting (spec-rules §4);
  - it is BOUNDED: it does NOT halt the loop for routine errors (distinct from
    the safety-abort path) and does NOT recurse (an error WHILE capturing an
    error must not re-trigger capture).

Also asserts the SKILL.md documents the orchestrator's irreducible Agent()
trigger step for the capture-analysis dispatch.

Non-interactive. Exits non-zero on any failure.
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

SKILL_MD = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


spec = re.sub(r"\s+", " ", SPEC_MD.read_text().lower())

REQUIRED_SPEC = [
    # The owning script.
    "capture-observed-error.py",
    # The triggering conditions.
    "non-zero",
    "anomaly",
    # Context isolation — the KEY design ask.
    "isolated",
    "context",
    # The session-reuse / croncreate accumulation rationale.
    "session-reuse",
    # Structured verdict handoff.
    "verdict",
    # The well-formed filed issue for a later tick.
    "file-item.py",
    "later tick",
    # Level-1 / main-session dispatch, like Phase 6, no nesting.
    "level-1",
    "phase 6",
    # Bounded: no halt for routine errors; distinct from the abort path.
    "routine",
    "abort",
    # Recursion guard.
    "recurse",
    # The enforcing unit test.
    "test-capture-observed-error.py",
]

missing = [s for s in REQUIRED_SPEC if s not in spec]
if missing:
    fail(f"spec.md missing self-observed-error-capture phrase(s): {missing!r}")
else:
    ok("spec.md carries the self-observed-error-capture invariant (Inv 67)")

# SKILL.md documents the orchestrator's irreducible Agent() trigger step.
skill = re.sub(r"\s+", " ", SKILL_MD.read_text().lower())
REQUIRED_SKILL = [
    "capture-observed-error.py",
    "isolated",
]
missing_skill = [s for s in REQUIRED_SKILL if s not in skill]
if missing_skill:
    fail(f"SKILL.md missing capture trigger phrase(s): {missing_skill!r}")
else:
    ok("SKILL.md documents the capture-analysis Agent() trigger step")

sys.exit(FAIL)
