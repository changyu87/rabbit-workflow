#!/usr/bin/env python3
"""test-spec-refire-liveness-guard-invariant.py — rabbit-auto-evolve Inv 65
(issue #1051).

Asserts the dropped-refire liveness-guard invariant text is present in the
feature spec (docs/spec.md, dual-read with specs/ and legacy docs/spec/
fallback per issue #399). The invariant states:
  - the immediate-refire CronCreate is a Claude-only action nothing verified;
  - schedule-decision.py's tick.log breadcrumb is the persisted decision;
  - at the next tick start, refire-guard.py reconciles the prior decision:
    a prior immediate-refire + a still-non-empty dispatchable plan + more than
    a heartbeat-interval elapsed (the refire clearly did not fire promptly) ->
    a LOUD tick.log warning + a refire_owed signal;
  - the guard DETECTS + SURFACES; the dispatcher still creates the CronCreate;
  - the pure, unit-testable reconcile() predicate;
  - run-tick-phases.py pre-dispatch invokes the guard at tick start.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
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
    # The guard script name.
    "refire-guard.py",
    # The persisted breadcrumb source.
    "tick.log",
    # The reconciliation key: a prior immediate-refire that never fired.
    "immediate-refire",
    # The owed signal.
    "refire_owed",
    # The guard only DETECTS + SURFACES; CronCreate stays a Claude action.
    "croncreate",
    # The pure predicate.
    "reconcile",
    # Invoked at tick start by the shared phase-walk.
    "run-tick-phases.py",
    # The enforcing test.
    "test-refire-guard.py",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing refire-liveness-guard phrase(s): {missing!r}")
else:
    ok("spec.md carries the dropped-refire liveness-guard invariant (Inv 65)")

sys.exit(FAIL)
