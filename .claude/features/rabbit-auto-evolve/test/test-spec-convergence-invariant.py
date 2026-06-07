#!/usr/bin/env python3
"""test-spec-convergence-invariant.py — rabbit-auto-evolve Part E (issue #423).

Asserts the new triage-convergence invariant text is present in the
feature spec (specs/spec.md, dual-read with docs/spec/ fallback per issue
#399). The invariant states that the triage classifier MUST
converge every valid issue to completion: it MAY defer dispatch (up to 3
consecutive deferrals per issue, after which dispatch is mandatory), MAY
close an issue as not-planned with a strong reason, MUST NOT close a valid
issue as completed as a substitute for dispatch, and MUST NOT escalate work
to human review as a non-dispatch action.
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
# Collapse all runs of whitespace (incl. the line-wrap newlines + Markdown
# indentation) to single spaces so wrapped prose still matches the
# substrings below.
lowered = re.sub(r"\s+", " ", text.lower())

# Required substrings of the convergence invariant. Matched case-insensitively
# so future copy-edits of capitalization don't break the test, but the
# load-bearing phrases must be present.
REQUIRED = [
    "must converge every valid issue to completion",
    "up to 3 consecutive deferrals per issue",
    "close an issue as not-planned",
    "must not close a valid issue as completed",
    "must not escalate work to human review",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing convergence-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the triage-convergence invariant (Part E)")

sys.exit(FAIL)
