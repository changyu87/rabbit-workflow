#!/usr/bin/env python3
"""test-spec-research-shape-invariant.py — rabbit-auto-evolve Inv 27
(issue #478).

Asserts the new research/investigation-shape invariant text is present in
the feature spec (specs/spec.md, dual-read with docs/spec/ fallback per
issue #399). The invariant states:
  (a) triage classifies research/investigation items as decision=research;
  (b) plan-batch routes them to dispatch_shape=research and a research_items
      output key, never into barrier_first/groups;
  (c) findings come from a read-only research subagent;
  (d) findings are committed as a doc under docs/findings/<issue-N>-<slug>.md;
  (e) valid research items are NEVER closed not-planned.
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
    # The 4th dispatch shape, named.
    "research/investigation shape",
    "4th dispatch shape",
    # (a) classification verbs surfaced.
    "study",
    "evaluate",
    "investigate",
    "recommend",
    # (b) routing: research_items key, excluded from barrier/groups.
    "research_items",
    # (c) read-only research subagent.
    "read-only research subagent",
    # (d) findings committed as a doc under docs/findings/.
    "docs/findings/",
    # (e) never closed not-planned.
    "never closed",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing research-shape-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the research-shape invariant (Inv 27)")

# Inv 27(d) refined (issue #835): disposition keyed to outcome SIZE.
#   SMALL -> findings as a comment on the request issue, then close finished.
#   BIG   -> committed findings DOC (docs/decisions/ or docs/research/, with
#            lifecycle frontmatter), then close finished WITH a link to it.
#   INVARIANT: the request issue ALWAYS ends closed/finished; never left open.
#   Follow-up actionable WORK is a SEPARATE work issue, distinct from findings.
SIZE_KEYED = [
    "small",
    "big",
    "comment",
    "docs/decisions/",
    "docs/research/",
    "--findings-comment-url",
    "lifecycle frontmatter",
]
size_missing = [s for s in SIZE_KEYED if s not in lowered]
if size_missing:
    fail(f"spec.md missing Inv 27(d) size-keyed disposition phrase(s): "
         f"{size_missing!r}")
else:
    ok("spec.md carries the Inv 27(d) size-keyed disposition rule")

# The always-closed invariant: the request issue never ends open.
if "always ends closed" not in lowered and "always end closed" not in lowered:
    fail("spec.md does not state the request issue ALWAYS ends closed")
else:
    ok("spec.md states the request issue always ends closed (small or big)")

# Findings disposition is distinct from actionable follow-up work, which is
# filed as its own separate work issue.
if "follow-up work" not in lowered or "separate" not in lowered:
    fail("spec.md does not state follow-up work is filed as a separate issue")
else:
    ok("spec.md separates follow-up work from the findings record")

# The research shape must be listed ALONGSIDE the three existing shapes as a
# valid, named shape (not struck like the session-override shape).
for shape in ("parallel-per-feature", "multi-subagent-barrier",
              "decomposition"):
    if shape not in lowered:
        fail(f"spec.md missing existing shape name {shape!r} in research "
             f"invariant context")
if "research" not in lowered:
    fail("spec.md does not mention the research shape at all")
else:
    ok("spec.md lists research alongside the three existing dispatch shapes")

sys.exit(FAIL)
