#!/usr/bin/env python3
"""RABBIT-CAGE-BACKLOG-29: assert /rabbit-config Skill section invariants are in monotonic numeric order.

The /rabbit-config Skill section runs from `## /rabbit-config Skill` (H2) to the
next H2 `## Out of Scope`. Within that section, every top-level numbered item
`^(\\d+)\\.` MUST appear in strictly increasing numeric order. Cross-section
monotonic order is OUT OF SCOPE (handled by CONTRACT-BACKLOG-30).

Owner: rabbit-workflow team
Deprecation criterion: retires when contract-wide monotonic-order enforcement
(CONTRACT-BACKLOG-30) covers this assertion at higher level.
"""
import os
import re
import sys

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
SPEC = os.path.join(
    REPO_ROOT, ".claude", "features", "rabbit-cage", "docs", "spec", "spec.md"
)

SECTION_START_H2 = "## /rabbit-config Skill"
SECTION_END_H2 = "## Out of Scope"

NUM_ITEM_RE = re.compile(r"^(\d+)\.\s")


def main() -> int:
    with open(SPEC, encoding="utf-8") as f:
        lines = f.readlines()

    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_idx is None and line.rstrip() == SECTION_START_H2:
            start_idx = i
        elif start_idx is not None and line.rstrip() == SECTION_END_H2:
            end_idx = i
            break

    if start_idx is None:
        print(f"FAIL: section start heading not found: {SECTION_START_H2!r}")
        return 1
    if end_idx is None:
        print(f"FAIL: section end heading not found: {SECTION_END_H2!r}")
        return 1

    numbers: list[tuple[int, int]] = []  # (line_number_1based, invariant_number)
    for i in range(start_idx, end_idx):
        m = NUM_ITEM_RE.match(lines[i])
        if m:
            numbers.append((i + 1, int(m.group(1))))

    if not numbers:
        print("FAIL: no numbered items found in /rabbit-config Skill section")
        return 1

    failures: list[str] = []
    for (la, na), (lb, nb) in zip(numbers, numbers[1:]):
        if nb <= na:
            failures.append(
                f"  out-of-order: Inv {na} at line {la} followed by Inv {nb} at line {lb}"
            )

    if failures:
        print("FAIL: /rabbit-config Skill section invariants are not monotonically increasing:")
        for f in failures:
            print(f)
        return 1

    print(
        f"PASS: /rabbit-config Skill section invariants monotonic "
        f"({len(numbers)} items, {numbers[0][1]}..{numbers[-1][1]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
