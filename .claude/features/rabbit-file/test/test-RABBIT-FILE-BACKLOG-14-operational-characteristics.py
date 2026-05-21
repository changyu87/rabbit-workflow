#!/usr/bin/env python3
"""Presence test for rabbit-file spec.md Operational characteristics (BACKLOG-14).

BACKLOG-14 adds an informational ## Operational characteristics section to
spec.md documenting the worst-case push-attempt budget (48 attempts) and
worst-case wall time (~30s) implied by the existing retry invariant.

This is a slim presence-of-section assertion: the section itself is the
artifact, so the test simply verifies the section header exists, the
BACKLOG-14 provenance anchor is present in the section body, and the
specific budget numbers (48 attempts, ~30s wall time) are documented.
"""
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

pass_ = 0
fail = 0


def assert_pass(msg):
    global pass_
    print(f"PASS: {msg}")
    pass_ += 1


def assert_fail(msg, reason):
    global fail
    print(f"FAIL: {msg} - {reason}")
    fail += 1


if not SPEC_MD.is_file():
    assert_fail("spec.md exists", f"missing at {SPEC_MD}")
else:
    txt = SPEC_MD.read_text()

    if "## Operational characteristics" in txt:
        assert_pass("spec.md has ## Operational characteristics section (BACKLOG-14)")
    else:
        assert_fail(
            "spec.md has ## Operational characteristics section (BACKLOG-14)",
            "section header not found",
        )

    if "BACKLOG-14" in txt:
        assert_pass("spec.md anchors the section to BACKLOG-14")
    else:
        assert_fail(
            "spec.md anchors the section to BACKLOG-14",
            "BACKLOG-14 provenance marker not found",
        )

    if "48 push attempts" in txt:
        assert_pass("spec.md documents 48 push-attempt worst case (BACKLOG-14)")
    else:
        assert_fail(
            "spec.md documents 48 push-attempt worst case (BACKLOG-14)",
            "'48 push attempts' string not found",
        )

    if "~30s" in txt:
        assert_pass("spec.md documents ~30s wall-time worst case (BACKLOG-14)")
    else:
        assert_fail(
            "spec.md documents ~30s wall-time worst case (BACKLOG-14)",
            "'~30s' string not found",
        )

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
