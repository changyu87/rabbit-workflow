#!/usr/bin/env python3
"""E2E test for RABBIT-FEATURE-BACKLOG-6: Invariants section must be in
strictly monotonic numeric order in document order.

Parses `docs/spec/spec.md`, locates the `## Invariants` H2, and extracts
top-level numbered items (`^(\\d+)\\.`) up to the next H2
(`## What this feature does NOT define`). Subsection headings
(`### Absorbed from ...`, `### rabbit-feature-new`, `### rabbit-feature-audit`)
do not break the numbering scope — invariant numbers run monotonically across
subsections.

Also verifies the citation target `Inv 35` is still findable in the spec, so
external cross-references in policy/spec.md and policy/test/ keep resolving.

Deprecation: retires when contract-wide enforcement (CONTRACT-BACKLOG-30,
cycle 5) covers the same assertion at a higher level.
"""
import re
import sys
from pathlib import Path

SPEC_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "spec" / "spec.md"
)

INVARIANTS_H2 = "## Invariants"
NEXT_H2 = "## What this feature does NOT define"

# Top-level numbered item at column 0: "<n>. ..."
NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s")


def _extract_invariant_numbers():
    text = SPEC_PATH.read_text()
    lines = text.splitlines()
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == INVARIANTS_H2 and start_idx is None:
            start_idx = i + 1
            continue
        if start_idx is not None and line.strip() == NEXT_H2:
            end_idx = i
            break
    assert start_idx is not None, (
        f"could not find '{INVARIANTS_H2}' H2 in {SPEC_PATH}"
    )
    assert end_idx is not None, (
        f"could not find '{NEXT_H2}' H2 after Invariants in {SPEC_PATH}"
    )
    numbers = []
    for line in lines[start_idx:end_idx]:
        m = NUMBERED_ITEM_RE.match(line)
        if m:
            numbers.append(int(m.group(1)))
    return numbers


def test_invariants_section_present():
    """Sanity: the Invariants section yields a non-empty list of numbers."""
    nums = _extract_invariant_numbers()
    assert nums, "no numbered invariants extracted from Invariants section"


def test_invariants_monotonic_in_document_order():
    """Top-level numbered invariants MUST be strictly increasing in document
    order (BACKLOG-6). Subsection headings do not reset the scope."""
    nums = _extract_invariant_numbers()
    for prev, curr in zip(nums, nums[1:]):
        assert curr > prev, (
            f"non-monotonic invariant numbering: {prev} appears before "
            f"{curr} in document order (full sequence: {nums})"
        )


def test_inv_35_citation_target_findable():
    """External features cite 'rabbit-feature Inv 35' by number. The
    citation target MUST still resolve inside this feature's spec.md."""
    text = SPEC_PATH.read_text()
    # Look for the numbered item header "35." at column 0.
    assert re.search(r"(?m)^35\.\s", text), (
        "Inv 35 numbered item header not found in spec.md — external "
        "citations to 'rabbit-feature Inv 35' would break"
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
