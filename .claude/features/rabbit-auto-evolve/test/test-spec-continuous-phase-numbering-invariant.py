#!/usr/bin/env python3
"""test-spec-continuous-phase-numbering-invariant.py — rabbit-auto-evolve
continuous phase-numbering invariant (issue #640).

The loop's phase numbering MUST be a continuous integer sequence 0..12 with no
fractional index. Issue #640 eliminated the fractional `phase 1.5`
(`post-merge-drain`) and cascaded every later phase number +1 in lock-step:
1.5->2, 2->3, 3->4, 4->5, 5->6, 6->7, 7->8, 8->9, 9->10, 10->11, 11->12. Phase
NAMES and all machine identifiers (result['phases'][...] keys, record-kinds,
state fields, script filenames) are unchanged — only the human-facing NUMBERS.

This is the end-to-end regression for the renumber. It asserts:
  1. The phase table in BOTH the source and deployed SKILL.md has a first
     ("#") column that, once range cells are expanded, covers exactly the
     contiguous integer set 0..12 with no gaps and no duplicates.
  2. No fractional phase index (`phase 1.5` / `| 1.5 |`) survives in any of
     the five files the renumber swept (SKILL.md, spec.md, run-tick-phases.py,
     run-post-merge.py, merge-prs.py). The module `Version: 1.5.0` line in
     merge-prs.py is NOT a phase index and is explicitly tolerated.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
# Resolve the feature spec dual-read (issue #399): prefer flat docs/spec.md.
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "specs" / "spec.md"
if not SPEC_MD.is_file():
    SPEC_MD = FEATURE_DIR / "docs" / "spec" / "spec.md"

SOURCE_SKILL = FEATURE_DIR / "skills" / "rabbit-auto-evolve" / "SKILL.md"
REPO_ROOT = FEATURE_DIR.parents[2]
DEPLOYED_SKILL = REPO_ROOT / ".claude" / "skills" / "rabbit-auto-evolve" / "SKILL.md"

SWEEP_FILES = [
    SOURCE_SKILL,
    SPEC_MD,
    FEATURE_DIR / "scripts" / "run-tick-phases.py",
    FEATURE_DIR / "scripts" / "run-post-merge.py",
    FEATURE_DIR / "scripts" / "merge-prs.py",
]

EXPECTED = set(range(0, 13))  # 0..12 inclusive

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# A phase-table row's first column is either a single integer (`| 6 |`) or a
# hyphen/en-dash range (`| 7-9 |` / `| 8–10 |`).
CELL_RE = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*$")


def phase_numbers_from_table(text, label):
    """Extract and expand the first-column phase numbers of the phase table.

    The phase table is identified by its header row `| # | Phase | ... |`. We
    read the contiguous run of table rows that follow the header separator and
    expand any range cell (`7-9`) into its integer span. Returns the ordered
    list of integers covered.
    """
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == "#" and cells[1].lower() == "phase":
            header_idx = i
            break
    if header_idx is None:
        fail(f"{label}: could not locate the phase table header `| # | Phase |`")
        return []
    nums = []
    # Row after header is the `|---|---|` separator; data rows follow.
    for line in lines[header_idx + 2:]:
        if not line.lstrip().startswith("|"):
            break
        first = line.strip().strip("|").split("|")[0]
        m = CELL_RE.match(first)
        if not m:
            fail(f"{label}: phase-table cell {first!r} is not an integer or "
                 f"integer range (fractional index?)")
            continue
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        nums.extend(range(lo, hi + 1))
    return nums


def assert_table_continuous(path, label):
    if not path.is_file():
        fail(f"{label}: file not found at {path}")
        return
    nums = phase_numbers_from_table(path.read_text(), label)
    if not nums:
        return
    if len(nums) != len(set(nums)):
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        fail(f"{label}: phase table has duplicate phase number(s) {dupes}")
    covered = set(nums)
    if covered != EXPECTED:
        missing = sorted(EXPECTED - covered)
        extra = sorted(covered - EXPECTED)
        fail(f"{label}: phase table is not the contiguous 0..12 sequence "
             f"(missing={missing}, extra={extra}, covered={sorted(covered)})")
    elif nums != sorted(nums):
        fail(f"{label}: phase table numbers are not in ascending order: {nums}")
    else:
        ok(f"{label}: phase table is the continuous 0..12 integer sequence")


# (1) Both source and deployed SKILL.md tables are continuous 0..12.
assert_table_continuous(SOURCE_SKILL, "source SKILL.md")
assert_table_continuous(DEPLOYED_SKILL, "deployed SKILL.md")

# (2) No fractional phase index survives in any swept file. The merge-prs.py
# module `Version: 1.5.0` line is not a phase index and is tolerated.
FRACTIONAL_RE = re.compile(r"phases?\s+1\.5|\|\s*1\.5\s*\|", re.IGNORECASE)
for path in SWEEP_FILES:
    if not path.is_file():
        fail(f"sweep file not found: {path}")
        continue
    hits = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if "Version: 1.5.0" in line:
            continue  # module version, not a phase index
        if FRACTIONAL_RE.search(line):
            hits.append((n, line.strip()))
    if hits:
        for n, content in hits:
            fail(f"{path.name}:{n} carries a fractional phase index: {content!r}")
    else:
        ok(f"{path.name}: no fractional phase index remains")

sys.exit(FAIL)
