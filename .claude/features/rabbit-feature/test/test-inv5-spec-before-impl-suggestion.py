#!/usr/bin/env python3
"""E2E test for rabbit-spec Invariant 5 (spec updated before impl-suggestion).

Invariant 5 requires that rabbit-spec updates docs/spec/spec.md in the target
feature directory before writing the impl-suggestion file. This test parses
the deployed (built) SKILL.md and asserts the "Update the Spec" step heading
appears textually before the "Write impl-suggestion File" step heading.

End-to-end scope: the test operates on the built/deployed SKILL.md that real
callers invoke, not just the source under .claude/features/.
"""
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BUILT_SKILL = os.path.join(REPO_ROOT, ".claude", "skills", "rabbit-spec", "SKILL.md")


def _read(path):
    with open(path) as f:
        return f.read()


def test_built_skill_exists():
    assert os.path.isfile(BUILT_SKILL), f"Built SKILL.md missing at {BUILT_SKILL}"


def test_update_spec_heading_present():
    text = _read(BUILT_SKILL)
    assert re.search(r"^##\s+Step\s+4\s+.*Update the Spec", text, re.MULTILINE), \
        "SKILL.md must contain a 'Step 4 — Update the Spec' heading"


def test_write_impl_suggestion_heading_present():
    text = _read(BUILT_SKILL)
    assert re.search(r"^##\s+Step\s+5\s+.*Write impl-suggestion File", text, re.MULTILINE), \
        "SKILL.md must contain a 'Step 5 — Write impl-suggestion File' heading"


def test_update_spec_appears_before_write_impl_suggestion():
    """Inv 5: 'Update the Spec' step heading MUST appear textually before
    'Write impl-suggestion File' step heading."""
    text = _read(BUILT_SKILL)
    m4 = re.search(r"^##\s+Step\s+4\s+.*Update the Spec", text, re.MULTILINE)
    m5 = re.search(r"^##\s+Step\s+5\s+.*Write impl-suggestion File", text, re.MULTILINE)
    assert m4 is not None, "Step 4 'Update the Spec' heading not found"
    assert m5 is not None, "Step 5 'Write impl-suggestion File' heading not found"
    assert m4.start() < m5.start(), \
        f"'Update the Spec' (offset {m4.start()}) must appear before " \
        f"'Write impl-suggestion File' (offset {m5.start()})"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
