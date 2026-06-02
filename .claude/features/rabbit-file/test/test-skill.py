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

# BUG-34: SKILL.md must NOT reference any /rabbit-file slash-command
# invocation. The Overview declares "there are NO slash commands"; all
# other sections must be consistent.
assert_not_contains(
    "/rabbit-file ",
    "no /rabbit-file slash-command reference in SKILL.md (BUG-34)",
)

# BUG-34: List Protocol must document (a) deterministic sort-by-name and
# (b) the distinct branch-missing condition vs. filter-mismatch.
_list_start = skill_text.find("## List Protocol")
_list_end = skill_text.find("---", _list_start) if _list_start != -1 else -1
if _list_start == -1 or _list_end == -1:
    assert_fail(
        "List Protocol section located (BUG-34)",
        "could not find '## List Protocol' delimited section",
    )
else:
    _list_block = skill_text[_list_start:_list_end]
    _sort_terms = ("sort", "sorted", "deterministic", "ascending")
    if any(t in _list_block.lower() for t in _sort_terms):
        assert_pass("List Protocol documents deterministic sort-by-name (BUG-34)")
    else:
        assert_fail(
            "List Protocol documents deterministic sort-by-name (BUG-34)",
            f"none of {_sort_terms} found in List Protocol section",
        )
    # Branch-missing distinction: must mention branch + (does not exist | missing | absent | not been created)
    _missing_terms = ("does not exist", "missing", "absent", "not been created", "has not been")
    _block_lower = _list_block.lower()
    if "branch" in _block_lower and any(t in _block_lower for t in _missing_terms):
        # And separately, must distinguish from filter-mismatch condition.
        _distinct_terms = ("distinct", "different", "versus", "vs", "filter")
        if any(t in _block_lower for t in _distinct_terms):
            assert_pass(
                "List Protocol distinguishes branch-missing from filter-mismatch (BUG-34)"
            )
        else:
            assert_fail(
                "List Protocol distinguishes branch-missing from filter-mismatch (BUG-34)",
                "branch-missing wording present but no distinction from filter-mismatch found",
            )
    else:
        assert_fail(
            "List Protocol documents branch-missing condition (BUG-34)",
            f"branch + missing wording not found in List Protocol section",
        )

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
