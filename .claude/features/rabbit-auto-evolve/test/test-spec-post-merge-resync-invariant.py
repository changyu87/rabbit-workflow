#!/usr/bin/env python3
"""test-spec-post-merge-resync-invariant.py — rabbit-auto-evolve post-merge
re-sync invariant (Inv 47 / issue #516).

Asserts the invariant text is present in the feature spec (docs/spec.md).

The invariant states that `run-tick-phases.py run_post_dispatch` re-syncs the
local working tree to origin/dev (via `sync-tree.py`, `git pull --ff-only`)
AFTER the Phase-6 remote merge and BEFORE the phases 7-9 post-merge / release
drain, so `release-bump.py` computes its tag against fresh (not stale) local
state and succeeds on the FIRST in-loop release attempt rather than relying on
the #512 next-tick retry. With zero merges the re-sync is a harmless no-op.
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


spec_text = SPEC_MD.read_text()
spec_lower = re.sub(r"\s+", " ", spec_text.lower())

REQUIRED_SPEC = [
    # The re-sync mechanism reuses sync-tree.py.
    "sync-tree.py",
    # It runs in the post-dispatch / post-merge phase walk.
    "run_post_dispatch",
    # It is ordered after the merge and before the release/post-merge drain.
    "release-bump.py",
    # The defect being closed: stale local dev after the remote merge.
    "origin/dev",
    # Issue reference.
    "#516",
]
missing = [s for s in REQUIRED_SPEC if s not in spec_lower]
if missing:
    fail(f"spec.md missing post-merge re-sync invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the post-merge re-sync invariant (Inv 47)")

# The invariant must be numbered 47 (next monotonic number in this feature).
if re.search(r"(?m)^\s*47\.\s", spec_text):
    ok("spec.md numbers the new invariant as 47 (next monotonic)")
else:
    fail("spec.md does not carry a list item numbered 47")

sys.exit(FAIL)
