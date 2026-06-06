#!/usr/bin/env python3
"""test-spec-integration-target-invariant.py — rabbit-auto-evolve
integration-target abstraction + dev<->main coexistence invariant (Inv 61).

Asserts the invariant text is present in the feature spec (docs/spec.md).

The invariant states that the loop integrates merged work into a single
resolved "integration target" branch; during the dev<->main coexistence
window BOTH dev and main are accepted (a PR whose base is neither is refused);
the resolved target defaults to dev and is overridable via
RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET; and the manual close-after-merge runs
only while the target is NOT the default branch (kept for target=dev, skipped
for target=main where GitHub's native keyword auto-close fires).
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
    # The resolved abstraction is named.
    "integration target",
    # The override env var.
    "rabbit_auto_evolve_integration_target",
    # The coexistence window honors both branches.
    "coexistence",
    # The default-branch native auto-close conditionality.
    "native",
    # The manual close path.
    "close-after-merge",
]
missing = [s for s in REQUIRED_SPEC if s not in spec_lower]
if missing:
    fail(f"spec.md missing integration-target invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the integration-target / coexistence invariant")

# The invariant's title is present as a numbered list item (number not pinned).
# The title may wrap across lines, so match the numbered-bullet opener followed
# by the "integrat..." stem (the rest of the phrase may continue on a wrap).
if re.search(r"(?m)^\s*\d+\.\s+\*\*[^\n]*[Ii]ntegrat", spec_text):
    ok("spec.md carries the integration-target invariant as a numbered item")
else:
    fail("spec.md does not carry a numbered integration-target invariant")

sys.exit(FAIL)
