#!/usr/bin/env python3
"""test-spec-integration-target-invariant.py — rabbit-auto-evolve
integration-target abstraction invariant (Inv 61).

Asserts the invariant text is present in the feature spec (docs/spec.md).

The dev->main cutover is complete and the coexistence window has CLOSED: `main`
is the SOLE accepted integration target. The invariant states that the loop
integrates merged work into a single resolved "integration target" branch which
is now constantly `main` (the default branch); a PR whose base is anything else
is refused; every merge uses an `--admin` override past `main`'s required
review; and issue closure rides entirely on GitHub's native keyword auto-close
(the manual close-after-merge path has been retired).
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
    # The sole accepted target is the default branch.
    "default branch",
    # Issue closure rides on GitHub's native keyword auto-close.
    "native",
]
missing = [s for s in REQUIRED_SPEC if s not in spec_lower]
if missing:
    fail(f"spec.md missing integration-target invariant phrase(s): {missing!r}")
else:
    ok("spec.md carries the main-sole integration-target invariant")

# Admin-override merge on the protected default branch (issue #973): a merge
# into `main` uses `gh pr merge --squash --admin` to bypass the required-review
# the bot cannot satisfy on its own PR.
if "--admin" not in spec_lower:
    fail("spec.md missing the admin-override merge flag (--admin) for the "
         "protected default-branch merge path (issue #973)")
else:
    ok("spec.md carries the --admin default-branch admin-override merge prose")

# The teardown is COMPLETE: the removed env override and the retired manual
# close-after-merge path must no longer be described as live mechanics in the
# invariant body.
REMOVED_PHRASES = [
    "rabbit_auto_evolve_integration_target",
    "close-after-merge",
]
present = [s for s in REMOVED_PHRASES if s in spec_lower]
if present:
    fail(f"spec.md still references retired integration-target mechanics: "
         f"{present!r} (the coexistence env override and the manual "
         f"close-after-merge path are removed)")
else:
    ok("spec.md no longer references the retired env override / manual close")

# The invariant's title is present as a numbered list item (number not pinned).
# The title may wrap across lines, so match the numbered-bullet opener followed
# by the "integrat..." stem (the rest of the phrase may continue on a wrap).
if re.search(r"(?m)^\s*\d+\.\s+\*\*[^\n]*[Ii]ntegrat", spec_text):
    ok("spec.md carries the integration-target invariant as a numbered item")
else:
    fail("spec.md does not carry a numbered integration-target invariant")

sys.exit(FAIL)
