#!/usr/bin/env python3
"""Tests that SKILL.md exists and contains all required sections."""
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
SKILL = FEATURE_DIR / "skills" / "rabbit-file" / "SKILL.md"

pass_ = 0
fail = 0

def assert_pass(msg):
    global pass_
    print(f"PASS: {msg}")
    pass_ += 1

def assert_fail(msg, reason):
    global fail
    print(f"FAIL: {msg} — {reason}")
    fail += 1

# t1: SKILL.md exists
if SKILL.is_file():
    assert_pass("SKILL.md exists")
    skill_text = SKILL.read_text()
else:
    assert_fail("SKILL.md exists", f"missing at {SKILL}")
    skill_text = ""

# t2-t6: Required sections
for section in [
    "## Overview",
    "## File Protocol",
    "## Work Protocol",
    "## List Protocol",
    "## branch_ops.py Lifecycle",
]:
    if section in skill_text:
        assert_pass(f"contains '{section}'")
    else:
        assert_fail(f"contains '{section}'", "section not found in SKILL.md")

def assert_contains(needle, msg):
    if needle in skill_text:
        assert_pass(msg)
    else:
        assert_fail(msg, f"missing substring: {needle!r}")


def assert_not_contains(needle, msg):
    if needle in skill_text:
        assert_fail(msg, f"forbidden substring present: {needle!r}")
    else:
        assert_pass(msg)


# BACKLOG-2: impl-suggestion must mention test gap analysis in Work Protocol.
assert_contains("test gap", "Work Protocol mentions test-gap analysis (BACKLOG-2)")

# BACKLOG-6: legacy slash commands /rabbit-file file|work|list must NOT appear
# as harness invocations (the table header is fine but the canonical
# invocations must use the python3 script paths).
assert_not_contains(
    "$TDD_REPORT_PATH",
    "no undefined $TDD_REPORT_PATH variable in SKILL.md (BACKLOG-6)",
)
# Snippet that resolves the tdd_report_path from the handoff payload —
# replaces the previous undefined-shell-variable form.
assert_contains(
    "tdd_report_path",
    "SKILL.md references tdd_report_path from handoff payload (BACKLOG-6)",
)

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
