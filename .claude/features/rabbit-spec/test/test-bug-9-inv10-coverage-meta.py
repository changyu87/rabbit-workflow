#!/usr/bin/env python3
"""Meta-test for rabbit-spec Invariant 10 (test coverage of every invariant).

Invariant 10 requires every numbered spec invariant to have at least one
corresponding test in `.claude/features/rabbit-spec/test/`. This meta-test
walks the Invariants section of spec.md, extracts every numbered invariant,
and asserts that for each invariant N at least one test file (other than
this meta-test and the run.py runner) contains 'Inv N' or 'Invariant N' in
its module docstring or source.

Closes RABBIT-SPEC-BACKLOG-9 test gap (c).
"""
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
TEST_DIR = os.path.join(FEATURE_DIR, "test")

# Files in TEST_DIR that don't count as invariant tests for this meta-test.
EXCLUDED_FILES = {
    "run.py",
    "test-bug-9-inv10-coverage-meta.py",  # this file (it cites every Inv)
}


def _extract_numbered_invariants(spec_text):
    """Return list of (int, str) for each numbered invariant in the
    Invariants section."""
    m = re.search(
        r"^##\s+Invariants\s*\n(.*?)(?=^##\s|\Z)",
        spec_text, re.MULTILINE | re.DOTALL,
    )
    assert m is not None, "spec.md must have an '## Invariants' section"
    section = m.group(1)
    # Match a line starting with "N. " (an ordered-list item) at column 0,
    # capturing N and the rest of the line.
    items = re.findall(r"^(\d+)\.\s+(.+)$", section, re.MULTILINE)
    return [(int(n), text) for n, text in items]


def _collect_test_sources():
    """Return {filename: source-text} for every test-*.py in TEST_DIR
    (excluding EXCLUDED_FILES)."""
    sources = {}
    for fname in sorted(os.listdir(TEST_DIR)):
        if not (fname.startswith("test-") and fname.endswith(".py")):
            continue
        if fname in EXCLUDED_FILES:
            continue
        with open(os.path.join(TEST_DIR, fname)) as f:
            sources[fname] = f.read()
    return sources


def _references_invariant(source_text, n):
    """True iff source_text mentions Inv N or Invariant N (case-insensitive)."""
    pattern = rf"\b(?:Inv|Invariant)\s+{n}\b"
    return re.search(pattern, source_text, re.IGNORECASE) is not None


def test_spec_has_numbered_invariants():
    with open(SPEC_MD) as f:
        invariants = _extract_numbered_invariants(f.read())
    assert len(invariants) >= 1, \
        "spec.md must have at least one numbered invariant for this test to be meaningful"


def test_every_invariant_has_corresponding_test():
    """Inv 10: every numbered invariant MUST have at least one test that
    cites it by 'Inv N' or 'Invariant N' in source or docstring."""
    with open(SPEC_MD) as f:
        invariants = _extract_numbered_invariants(f.read())
    sources = _collect_test_sources()
    assert sources, f"no test-*.py files found in {TEST_DIR}"

    missing = []
    for n, _summary in invariants:
        if not any(_references_invariant(src, n) for src in sources.values()):
            missing.append(n)
    assert not missing, (
        f"missing test coverage for invariant(s) {missing}: "
        f"no test-*.py file in {TEST_DIR} mentions 'Inv N' or 'Invariant N' "
        f"for these numbers"
    )


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
