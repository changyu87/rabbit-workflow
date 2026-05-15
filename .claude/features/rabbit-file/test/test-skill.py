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

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
