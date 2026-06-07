#!/usr/bin/env python3
"""Pin the `filed-by:` provenance label as a justified native-first exception.

The binding GitHub-native-first design rule (from the issue-mechanism
redesign) permits a custom label only when no native primitive covers the
need, and then only with an inline justification plus a deprecation
criterion. On THIS repo the autonomous loop and the human file under the
SAME GitHub identity, so the native issue author cannot distinguish
loop-filed from human-filed work; the custom `filed-by:` label is the only
provenance signal. rabbit-issue therefore retains `filed-by:` as a
documented, justified exception with a deprecation criterion.

This guard pins three things so a future doc edit cannot silently erode the
exception or let code and spec drift apart:

  1. spec.md §Provenance label records the native-first justification — that
     the native author is insufficient on a single-identity repo — and a
     deprecation criterion (when the loop and human file under distinct
     identities, provenance moves to the native author).
  2. The human-provenance convention is stated POSITIVELY and the code
     agrees with it: a human filing carries NO `filed-by:` label (absence
     is the human signal), and a bot/loop filing carries
     `filed-by:autonomous-evolve` (or `filed-by:rabbit`).
  3. `file-item.py`'s `VALID_FILED_BY` enum exactly matches the documented
     provenance enum `{rabbit, autonomous-evolve}` — code and spec do not
     drift.

Static checks; runtime label behaviour is exercised by test-file-item.py.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when rabbit-issue is retired
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
FILE_ITEM = FEATURE_DIR / "scripts" / "file-item.py"

# Documented provenance enum — human is the untagged default, so only the
# two non-human values are members.
DOCUMENTED_FILED_BY = ("rabbit", "autonomous-evolve")


def _load_valid_filed_by() -> tuple:
    """Import VALID_FILED_BY from file-item.py without running main()."""
    spec = importlib.util.spec_from_file_location("rabbit_issue_file_item", FILE_ITEM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return tuple(mod.VALID_FILED_BY)


def check_native_first_justification() -> list[str]:
    """spec.md must record the native-first justification + deprecation
    criterion for retaining the custom `filed-by:` label."""
    fails = []
    text = SPEC_MD.read_text().lower()
    # Names the native-first rule it is an exception to.
    if "native-first" not in text:
        fails.append("spec.md §Provenance does not cite the native-first design rule")
    # States WHY native author is insufficient: single shared GitHub identity.
    if ("single identity" not in text and "same identity" not in text
            and "single github identity" not in text):
        fails.append(
            "spec.md does not justify the exception (single shared GitHub "
            "identity makes native author insufficient)"
        )
    # Carries a deprecation criterion for the exception (Designed Deprecation).
    if "deprecation criterion" not in text:
        fails.append("spec.md §Provenance lacks a deprecation criterion for filed-by:")
    # The deprecation criterion names the native-author migration trigger:
    # distinct identities/apps for loop vs human.
    if "distinct" not in text and "separate identit" not in text:
        fails.append(
            "spec.md deprecation criterion does not name the distinct-identity "
            "migration trigger"
        )
    return fails


def check_human_absence_convention() -> list[str]:
    """The human-provenance convention is stated POSITIVELY: a human filing
    carries no filed-by: label; the loop/bot filing carries filed-by:."""
    fails = []
    text = SPEC_MD.read_text().lower()
    # Positive statement of absence-as-human.
    if "untagged default" not in text:
        fails.append("spec.md does not state human is the untagged default")
    if ("no `filed-by:` label" not in text
            and "no filed-by: label" not in text
            and "carries no `filed-by:`" not in text):
        fails.append(
            "spec.md does not positively state a human filing carries no "
            "filed-by: label"
        )
    return fails


def check_code_spec_enum_agree() -> list[str]:
    """file-item.py VALID_FILED_BY must equal the documented enum."""
    fails = []
    actual = _load_valid_filed_by()
    if actual != DOCUMENTED_FILED_BY:
        fails.append(
            f"file-item.py VALID_FILED_BY={actual!r} != documented enum "
            f"{DOCUMENTED_FILED_BY!r}"
        )
    return fails


def main() -> int:
    all_fails: list[str] = []
    all_fails.extend(check_native_first_justification())
    all_fails.extend(check_human_absence_convention())
    all_fails.extend(check_code_spec_enum_agree())
    if all_fails:
        for msg in all_fails:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1
    print("PASS test-filed-by-native-exception")
    return 0


if __name__ == "__main__":
    sys.exit(main())
