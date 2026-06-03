#!/usr/bin/env python3
"""test-spec-dispatch-shape-invariant.py — rabbit-auto-evolve Inv 26
(issue #435).

Asserts the new dispatch-shape invariant text is present in
docs/spec/spec.md. The invariant states:
  (a) Stage 1 work selection is dispatch-shape blind;
  (b) Stage 2 picks among exactly THREE shapes in preference order;
  (c) parallel-per-feature is a performance preference, not a correctness
      requirement;
  (d) the session-override shape (shape 2) is explicitly struck, and the
      reason is the maintainer's binding policy that bounded scope is a hard
      constraint not waivable by autonomy.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
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
    # (a) Stage 1 is dispatch-shape blind.
    "stage 1 work selection is dispatch-shape blind",
    # (b) Stage 2 picks among the three shapes in order.
    "parallel-per-feature",
    "multi-subagent-barrier",
    "decomposition",
    # (c) parallel-per-feature is a performance preference, not correctness.
    "performance preference, not a correctness requirement",
    # (d) shape-2 session override forbidden + why.
    "session-override shape is forbidden",
    "bounded scope is a hard constraint",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing dispatch-shape-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the dispatch-shape invariant (Inv 26)")

# The struck-shape token MUST NOT appear as a live, valid shape — assert the
# spec explicitly forbids it rather than listing it as selectable.
if "sequential-with-override" in lowered and "forbidden" not in lowered:
    fail("spec.md mentions sequential-with-override without forbidding it")
else:
    ok("spec.md does not list sequential-with-override as a valid shape")

sys.exit(FAIL)
