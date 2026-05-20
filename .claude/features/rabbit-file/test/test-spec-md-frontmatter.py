#!/usr/bin/env python3
"""Regression test for rabbit-file spec.md frontmatter (BUG-35).

Spec-rules §3 requires every spec to carry YAML frontmatter with
`feature`, `version`, `owner`, and `deprecation_criterion` at the top
of `docs/spec/spec.md`. The pre-BUG-35 spec.md was missing the entire
frontmatter block.
"""
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

REQUIRED_KEYS = ["feature", "version", "owner", "deprecation_criterion"]

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
    fm_match = re.match(r"^---\n(.*?)\n---\n", txt, re.DOTALL)
    if not fm_match:
        assert_fail(
            "spec.md has YAML frontmatter (BUG-35)",
            "no leading --- ... --- block found",
        )
    else:
        fm = fm_match.group(1)
        missing = [k for k in REQUIRED_KEYS if not re.search(rf"^{k}:", fm, re.MULTILINE)]
        if missing:
            assert_fail(
                "spec.md frontmatter has all required keys (BUG-35)",
                f"missing keys: {missing}",
            )
        else:
            assert_pass(
                "spec.md frontmatter has feature/version/owner/deprecation_criterion (BUG-35)"
            )

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
