#!/usr/bin/env python3
"""test-spec-refire-dedup-invariant.py — rabbit-auto-evolve Inv 49 (issue #559).

Asserts the at-most-one-immediate-refire dedup invariant text is present in the
feature spec (docs/spec.md, dual-read with specs/ and legacy docs/spec/
fallback per issue #399). The invariant states:
  - at most ONE immediate-refire one-shot at a time; a prior pending refire is
    cancelled (CronDelete) before exactly one new refire is created;
  - the dedup targets refire one-shots ONLY and NEVER removes the recurring
    heartbeat;
  - refires are distinguishable from the heartbeat by a label signature
    (the #refire marker on the prompt);
  - a pure, unit-testable is_refire_oneshot predicate;
  - the decision JSON carries the explicit dispatcher instruction set
    (delete_refire_ids / preserve_heartbeat_ids / create_refire) computed from
    an injected CronList snapshot.
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
    # At most one refire at a time.
    "at most one immediate-refire one-shot",
    # Prior pending refire cancelled before a new one.
    "crondelete",
    # Dedup never removes the heartbeat.
    "never remove the recurring heartbeat",
    # Distinguishable via a label signature / marker.
    "#refire",
    # Pure, unit-testable predicate.
    "is_refire_oneshot",
    # Explicit dispatcher instruction set in the JSON.
    "dispatcher_actions",
    "delete_refire_ids",
    "preserve_heartbeat_ids",
    "create_refire",
    # The injected CronList snapshot env.
    "rabbit_auto_evolve_cron_list",
]

missing = [s for s in REQUIRED if s not in lowered]
if missing:
    fail(f"spec.md missing refire-dedup-invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the at-most-one-refire dedup invariant (Inv 49)")

sys.exit(FAIL)
