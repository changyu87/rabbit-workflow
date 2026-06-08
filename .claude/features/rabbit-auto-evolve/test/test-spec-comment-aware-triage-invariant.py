#!/usr/bin/env python3
"""test-spec-comment-aware-triage-invariant.py — rabbit-auto-evolve Inv 66.

Asserts the comment-aware-triage invariant text is present in the feature
spec (docs/spec.md, dual-read with specs/ then legacy docs/spec/ fallback).
The invariant states (issue #1081):
  - triage SURFACES a new human (non-bot) comment left since the loop last
    triaged the issue, so a maintainer decision left as a COMMENT is not
    silently dropped;
  - the three machine-readable triage signals are emitted on every record:
    `latest_comment_at`, `has_unactioned_human_comment`,
    `needs_human_decision_reflected`;
  - a structured decision-comment marker (`@rabbit-decision:`) is parsed
    deterministically — NO free-form LLM comment interpreter;
  - a per-issue watermark persisted in a DEDICATED owned artifact
    (`.rabbit/comment-watermarks.json`) makes "new since last triage"
    deterministic; triage-issue.py READS it, triage-batch.py ADVANCES it
    monotonically;
  - the watermark artifact names an owner and a deprecation criterion.

Mirrors the spec-invariant test pattern (substring presence over the
whitespace-normalized lowered spec text).
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
    # Comments are incorporated into triage so a maintainer decision is not
    # silently dropped.
    "silently dropped",
    # The three machine-readable signals.
    "has_unactioned_human_comment",
    "needs_human_decision_reflected",
    "latest_comment_at",
    # The structured decision marker convention.
    "@rabbit-decision:",
    # Deterministic, not a free-form LLM interpreter.
    "deterministic",
    # The dedicated watermark artifact.
    "comment-watermarks.json",
    "watermark",
    # Read/advance split between the two scripts.
    "triage-issue.py",
    "triage-batch.py",
    # Non-bot human filter.
    "non-bot",
    # Lifecycle: owner + deprecation criterion named for the watermark.
    "deprecation criterion",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing comment-aware-triage invariant phrase(s): "
         f"{missing!r}")
else:
    ok("spec.md carries the comment-aware-triage invariant (Inv 66)")

# The invariant is numbered 66 and present as a list item.
if not re.search(r"(?m)^66\.\s+\*\*", text):
    fail("spec.md does not carry a numbered Inv 66 list item")
else:
    ok("spec.md carries the numbered Inv 66 list item")

sys.exit(FAIL)
