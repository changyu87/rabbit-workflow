#!/usr/bin/env python3
"""test-spec-tombstone-gaps-match-changelog.py — Inv 46 / CONTRACT-BACKLOG-30.

One-to-one correspondence between:
  (a) numeric gaps in the top-level '## Invariants' section of
      .claude/features/contract/docs/spec/spec.md, and
  (b) tombstone entries in .claude/features/contract/CHANGELOG.md.

The gap set is computed as: max(active_nums) -> {1..max} minus active_nums.
The tombstone set is computed by scanning CHANGELOG body for 'Inv <N>'
mentions.

  t1  spec.md '## Invariants' section is parseable.
  t2  CHANGELOG.md exists and lists at least one 'Inv <N>' tombstone.
  t3  gap set == tombstone set (one-to-one).

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
CHANGELOG = os.path.join(FEATURE_DIR, "CHANGELOG.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# --- parse spec invariants section ---
with open(SPEC, encoding="utf-8") as f:
    spec_text = f.read()

# isolate the top-level '## Invariants' section (stop at next H2 header)
match = re.search(r"^## Invariants\s*$(.*?)(?=^## )", spec_text, re.MULTILINE | re.DOTALL)
if not match:
    ko("t1", "could not locate top-level '## Invariants' section in spec.md")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
section = match.group(1)
active_nums = sorted({int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s", section, re.MULTILINE)})
if not active_nums:
    ko("t1", "no numbered invariants found in '## Invariants' section")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t1", f"parsed spec.md: {len(active_nums)} active invariants, max={max(active_nums)}")

gaps = sorted(set(range(1, max(active_nums) + 1)) - set(active_nums))

# --- parse CHANGELOG tombstones ---
if not os.path.isfile(CHANGELOG):
    ko("t2", f"missing: {CHANGELOG}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
with open(CHANGELOG, encoding="utf-8") as f:
    changelog_text = f.read()
# Tombstones are recognised only by their dedicated heading form
# (`### Inv <N> —` ...). Prose mentions of invariant numbers (e.g. inside
# 'Inv 7 parenthetical' sub-sections that explain a moved annotation, or
# any reference to a still-active invariant in surrounding narrative) are
# intentionally ignored — only headings count as a tombstone for the
# one-to-one correspondence check.
TOMBSTONE_HEADING_RE = re.compile(
    r"^###\s+Inv\s+(\d+)\s+—", re.MULTILINE
)
tombstone_nums = sorted(
    {int(m.group(1)) for m in TOMBSTONE_HEADING_RE.finditer(changelog_text)}
)
if not tombstone_nums:
    ko("t2", "no 'Inv <N>' tombstones found in CHANGELOG.md")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t2", f"CHANGELOG lists tombstones for invariants: {tombstone_nums}")

# --- compare ---
gap_set = set(gaps)
tomb_set = set(tombstone_nums)
if gap_set == tomb_set:
    ok("t3", f"one-to-one: gap set == tombstone set == {sorted(gap_set)}")
else:
    missing_tombstones = sorted(gap_set - tomb_set)
    extra_tombstones = sorted(tomb_set - gap_set)
    parts = []
    if missing_tombstones:
        parts.append(f"gaps lacking tombstones: {missing_tombstones}")
    if extra_tombstones:
        parts.append(f"tombstones for active invariants: {extra_tombstones}")
    ko("t3", "; ".join(parts))

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
