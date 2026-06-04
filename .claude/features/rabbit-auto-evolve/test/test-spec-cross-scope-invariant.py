#!/usr/bin/env python3
"""test-spec-cross-scope-invariant.py — rabbit-auto-evolve Inv 56 (issue #433).

Asserts the cross-scope detection + routing invariant text is present in the
feature spec (docs/spec.md, dual-read with specs/ and legacy docs/spec/
fallback). The invariant states:
  (a) triage-issue.py emits a `cross_scope` signal (and cross_scope_features);
  (b) plan-batch.py routes a cross_scope item away from parallel-per-feature
      to multi-subagent-barrier / decomposition;
  (c) cross_scope items are surfaced under cross_scope_items;
  and that bounded scope is NOT loosened (detection + routing only).
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
    # The invariant is numbered 56.
    "56. **cross-scope detection",
    # (a) triage emits the signal.
    "cross_scope",
    "cross_scope_features",
    # (b) routing: never parallel-per-feature; barrier / decomposition.
    "parallel-per-feature",
    "multi-subagent-barrier",
    "decomposition",
    # (c) surfaced distinctly.
    "cross_scope_items",
    # bounded scope is preserved (the fix is detection + routing).
    "bounded scope itself is unchanged",
    # (a.1) parent-reference exclusion (issue #667): a quoted parent phrase
    # on a parent-reference line must not set cross_scope.
    "parent-reference line",
    "sub-issue of",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing cross-scope-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the cross-scope invariant (Inv 56)")

# The invariant must explicitly forbid the parallel-per-feature shape for a
# cross_scope item (the core routing rule).
if "never `parallel-per-feature`" not in lowered.replace("—", "-"):
    # Tolerate the em-dash-normalized form; assert the routing phrase exists.
    if "never `parallel-per-feature`" not in lowered:
        fail("spec.md must state a cross_scope item is NEVER "
             "parallel-per-feature")
    else:
        ok("spec.md states cross_scope -> never parallel-per-feature")
else:
    ok("spec.md states cross_scope -> never parallel-per-feature")

sys.exit(FAIL)
