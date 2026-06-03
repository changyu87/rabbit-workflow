#!/usr/bin/env python3
"""test-spec-self-modifying-migration-invariant.py — rabbit-auto-evolve
self-modifying-migration invariant (the next monotonic invariant in this
feature's `## Invariants` section).

Asserts the invariant text is present in the feature spec (specs/spec.md).
The invariant states:
  (a) the self-modifying-migration category — work that changes something the
      loop itself depends on at runtime (a marker the tick driver reads, an
      agent type the loop dispatches, a path its scripts resolve, a schema /
      config key it loads);
  (b) the three safe-execution patterns: coexistence-window,
      last-tick-action, restart-safe;
  (c) the consumption-based decision rule (re-read-each-tick ->
      coexistence-window; self-contained -> last-tick-action; held in session
      memory -> restart-safe);
  (d) restart-required is SIGNALED via the restart-needed marker, NEVER a
      human stop — the loop never stops to ask a human for a self-modifying
      migration.
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
    # (a) the category.
    "self-modifying migration",
    # (b) the three patterns.
    "coexistence-window",
    "last-tick-action",
    "restart-safe",
    # (c) the consumption-based decision rule.
    "re-read from disk each tick",
    "held in session memory",
    # (d) restart signaled via marker, never a human stop.
    ".rabbit-auto-evolve-restart-needed",
    "never a human stop",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing self-modifying-migration invariant phrase(s): "
         f"{missing!r}")
else:
    ok("spec.md carries the self-modifying-migration invariant")

# The yield point is the restart-needed marker, never an a/b/c human question.
if "a/b/c" in lowered and "never" not in lowered:
    fail("spec.md mentions a/b/c human escalation without forbidding it")
else:
    ok("spec.md does not permit a/b/c human escalation for self-mod migration")

sys.exit(FAIL)
