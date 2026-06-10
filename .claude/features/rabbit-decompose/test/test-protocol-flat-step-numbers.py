#!/usr/bin/env python3
"""test-protocol-flat-step-numbers.py — issue #1139.

End-to-end check that rabbit-decompose's SKILL.md Protocol uses PURE FLAT
sequential step numbers, not a top-level Step 4 that carries lettered
sub-steps A-E.

Before #1139 the Protocol numbered top-level steps 1-4, but Step 4
("Hand off to scaffold + spec drafting") carried five lettered sub-steps:

  A. Open the decompose-context pass-through
  B. Scaffold
  C. Seed specs
  D. Close the decompose-context pass-through
  E. Report

That forced ambiguous mixed references like "Step 4-C" / "Step 4-D" in the
body. The fix promotes A-E to flat Steps 4-8 and rewrites the internal
cross-references to the new flat numbers.

This test pins the flat numbering so it cannot drift back:

  1. The Protocol exposes `### Step N — <title>` headings for N = 1..8,
     contiguous and in order, each consistent with the Steps 1-3 heading
     style ("### Step N — ").
  2. No lettered sub-step lead-ins remain: the body carries no bold
     `**A. ...**` / `**B. ...**` ... `**E. ...**` pass-through lead-ins
     under the old Step 4 section.
  3. No mixed "Step 4-A".."Step 4-E" references remain anywhere in the body.
  4. The marker-set step (Step 4) still points the reader at the
     marker-clear step by its NEW flat number (Step 7), not the old
     "Step 4-D".

The deployed copy is validated separately by the contract/check-numbered-lists
smoke scan; this per-feature test pins the source SKILL.md structure.

Run non-interactively. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the SKILL.md Protocol step structure is validated
    cross-feature by the contract gate, making this per-feature assertion
    redundant.
"""
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL_MD = os.path.join(
    FEATURE_DIR, "skills", "rabbit-decompose", "SKILL.md")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


if not os.path.isfile(SKILL_MD):
    fail(f"missing SKILL.md: {SKILL_MD}")

with open(SKILL_MD, encoding="utf-8") as f:
    text = f.read()

# --- Check 1: contiguous flat `### Step N — ` headings for N = 1..8 ----------
# Capture the integer step number from every `### Step N — ...` heading, in
# document order. The em dash (—) separates the number from the title, mirror-
# ing the existing Steps 1-3 style.
step_heads = re.findall(r"(?m)^###\s+Step\s+(\d+)\s+—\s+\S", text)
nums = [int(n) for n in step_heads]
if nums != [1, 2, 3, 4, 5, 6, 7, 8]:
    fail(
        "Protocol step headings are not flat contiguous Steps 1..8 "
        f"('### Step N — '); got {nums!r}. Expected the A-E sub-steps "
        "promoted to flat Steps 4-8 (#1139)."
    )

# --- Check 2: no lettered sub-step lead-ins remain --------------------------
# The old form was bold lettered lead-ins like `**A. Open the ...**`.
bad_letter = re.search(r"(?m)^\s*\*\*[A-E]\.\s", text)
if bad_letter:
    fail(
        "SKILL.md still carries a lettered sub-step lead-in "
        f"({bad_letter.group(0).strip()!r}); promote A-E to flat "
        "`### Step N — ` headings (#1139)."
    )

# --- Check 3: no mixed 'Step 4-A'..'Step 4-E' references ---------------------
mixed = re.search(r"Step\s+4-[A-E]\b", text)
if mixed:
    fail(
        "SKILL.md still carries a mixed lettered reference "
        f"({mixed.group(0)!r}); rewrite to the new flat step number (#1139)."
    )

# --- Check 4: marker-set step references the marker-clear step by Step 7 -----
# The pass-through is SET in (new) Step 4 and CLEARED in (new) Step 7. The
# set-step prose must point the reader to "Step 7" for the clear, not the old
# "Step 4-D".
if "Step 4-D" in text:
    fail("SKILL.md still references the old 'Step 4-D' for the marker clear")
if not re.search(r"Step\s+7\b", text):
    fail(
        "SKILL.md no longer points the reader at the marker-clear step by its "
        "new flat number ('Step 7'); the set-step must reference Step 7."
    )

print("All checks passed.")
