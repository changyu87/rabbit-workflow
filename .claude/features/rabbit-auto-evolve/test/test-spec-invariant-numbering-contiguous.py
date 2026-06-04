#!/usr/bin/env python3
"""test-spec-invariant-numbering-contiguous.py — rabbit-auto-evolve (issue #725).

Locks in the contiguous invariant numbering reflow required by #725. The
contract-suite monotonic check (contract Inv 38) only guarantees
strictly-increasing numbers; it tolerates GAPS (e.g. 1 -> 5 passes). This
feature-level test additionally guarantees CONTIGUITY — the numbering policy
intent: strictly-increasing PURE integers, CONTIGUOUS 1..N with NO gaps.

End-to-end (operates on the shipped docs/spec.md surface):

  (a) The '## Invariants' section's top-level numbered items are exactly the
      contiguous sequence 1..N — no gaps, no duplicates, no back-steps.

  (b) No rae-LOCAL 'Inv <n>' reference anywhere in docs/spec.md dangles:
      every cited number in the rae range [1..N] resolves to a defined
      invariant. A "dangling rae-local reference" is a citation of a number
      that falls inside [1..N] but is NOT a defined invariant (i.e. a number
      left orphaned by a gap). Numbers ABOVE N are, by construction, NOT
      rae invariants — rae defines exactly 1..N — so they are cross-feature
      references (e.g. 'contract Inv 64', 'rabbit-config Inv 17') and are
      excluded.

  (c) The invariant COUNT has not silently shrunk below the #725 baseline of
      59 — no invariant lost in a future renumber/edit. (New invariants may
      raise N; the floor guards against accidental deletion.)

Non-interactive. Exits non-zero on any failure.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"

# #725 baseline: the reflow landed a contiguous 1..59 sequence. The count may
# only grow (new invariants); it must never drop below this floor.
COUNT_FLOOR = 59

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


text = SPEC_MD.read_text(encoding="utf-8")
lines = text.splitlines()

# --- locate the '## Invariants' section and collect top-level item numbers ---
heading_re = re.compile(r"^(#{1,6})\s+")
inv_heading_re = re.compile(r"^##\s+Invariants\b")
item_re = re.compile(r"^(\d+)\.\s+\*\*")

in_section = False
in_fence = False
defined = []  # list of (number, line_no)
for i, line in enumerate(lines, start=1):
    stripped = line.strip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        in_fence = not in_fence
        continue
    if in_fence:
        continue
    if heading_re.match(line):
        in_section = bool(inv_heading_re.match(line))
        continue
    if not in_section:
        continue
    m = item_re.match(line)
    if m:
        defined.append((int(m.group(1)), i))

nums = [n for n, _ in defined]

# (a) contiguous 1..N, no gaps / dups
N = len(nums)
expected = list(range(1, N + 1))
if nums == expected:
    ok(f"(a) invariant numbering is contiguous 1..{N} (no gaps, no duplicates)")
else:
    defined_set = set(nums)
    gaps = sorted(set(range(1, (max(nums) if nums else 0) + 1)) - defined_set)
    dups = sorted({n for n in nums if nums.count(n) > 1})
    fail(
        "(a) invariant numbering not contiguous 1..N: "
        f"found {nums}; gaps={gaps}; duplicates={dups}"
    )

# (b) no dangling rae-local 'Inv <n>' reference. A reference dangles only if it
# cites a number inside the rae range [1..N] that is NOT a defined invariant.
# Numbers above N cannot be rae invariants (rae defines exactly 1..N), so they
# are cross-feature references (contract Inv 64/65, rabbit-config Inv 17, ...)
# and are out of scope for this feature's contiguity guarantee.
defined_set = set(nums)
ref_re = re.compile(r"\bInv(?:ariant)?\s+(\d+)\b")
dangling = []
for m in ref_re.finditer(text):
    n = int(m.group(1))
    if n <= N and n not in defined_set:
        line_no = text.count("\n", 0, m.start()) + 1
        dangling.append((n, line_no, m.group(0).strip()))
if dangling:
    detail = "; ".join(f"Inv {n} @line {ln} ({frag!r})" for n, ln, frag in dangling)
    fail(f"(b) dangling rae-local invariant reference(s): {detail}")
else:
    ok("(b) no dangling rae-local invariant references")

# (c) count floor
if N >= COUNT_FLOOR:
    ok(f"(c) invariant count {N} >= #725 baseline floor {COUNT_FLOOR}")
else:
    fail(f"(c) invariant count {N} dropped below #725 baseline floor {COUNT_FLOOR}")

sys.exit(FAIL)
