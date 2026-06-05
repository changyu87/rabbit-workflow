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

Non-interactive. Exits non-zero on any failure.
"""

import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


def collect_defined(text):
    """Return [(number, line_no), ...] for top-level '## Invariants' items."""
    lines = text.splitlines()
    heading_re = re.compile(r"^(#{1,6})\s+")
    inv_heading_re = re.compile(r"^##\s+Invariants\b")
    item_re = re.compile(r"^(\d+)\.\s+\*\*")
    in_section = False
    in_fence = False
    defined = []
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
    return defined


def check_contiguous(nums):
    """(a) nums must be exactly the contiguous sequence 1..N.

    Returns (passed, detail)."""
    N = len(nums)
    expected = list(range(1, N + 1))
    if nums == expected:
        return True, f"contiguous 1..{N} (no gaps, no duplicates)"
    defined_set = set(nums)
    gaps = sorted(set(range(1, (max(nums) if nums else 0) + 1)) - defined_set)
    dups = sorted({n for n in nums if nums.count(n) > 1})
    return False, f"found {nums}; gaps={gaps}; duplicates={dups}"


def check_no_dangling(text, N, defined_set):
    """(b) no rae-local 'Inv <n>' reference inside [1..N] may be undefined.

    A reference dangles only if it cites a number inside the rae range [1..N]
    that is NOT a defined invariant. Numbers above N cannot be rae invariants
    (rae defines exactly 1..N), so they are cross-feature references
    (contract Inv 64/65, rabbit-config Inv 17, ...) and are out of scope for
    this feature's contiguity guarantee. Returns (passed, detail)."""
    ref_re = re.compile(r"\bInv(?:ariant)?\s+(\d+)\b")
    dangling = []
    for m in ref_re.finditer(text):
        n = int(m.group(1))
        if n <= N and n not in defined_set:
            line_no = text.count("\n", 0, m.start()) + 1
            dangling.append((n, line_no, m.group(0).strip()))
    if dangling:
        detail = "; ".join(
            f"Inv {n} @line {ln} ({frag!r})" for n, ln, frag in dangling
        )
        return False, detail
    return True, "no dangling rae-local invariant references"


# --- (a)/(b) against the shipped spec ---
text = SPEC_MD.read_text(encoding="utf-8")
nums = [n for n, _ in collect_defined(text)]
N = len(nums)
defined_set = set(nums)

passed_a, detail_a = check_contiguous(nums)
if passed_a:
    ok(f"(a) invariant numbering is {detail_a}")
else:
    fail(f"(a) invariant numbering not contiguous 1..N: {detail_a}")

passed_b, detail_b = check_no_dangling(text, N, defined_set)
if passed_b:
    ok(f"(b) {detail_b}")
else:
    fail(f"(b) dangling rae-local invariant reference(s): {detail_b}")

# --- (c) the checker is size-agnostic: it enforces ONLY contiguity (a) and
# no-dangling (b). Exercise the same logic on a tiny contiguous surface; it must
# pass exactly like the full spec. The invariant count is unconstrained. ---
synthetic = (
    "## Invariants\n\n"
    "1. **Alpha** — first.\n"
    "2. **Beta** — second, see Inv 1.\n"
    "3. **Gamma** — third.\n"
)
syn_nums = [n for n, _ in collect_defined(synthetic)]
syn_a, _ = check_contiguous(syn_nums)
syn_b, _ = check_no_dangling(synthetic, len(syn_nums), set(syn_nums))
if syn_a and syn_b:
    ok("(c) a tiny contiguous surface passes (a)+(b) — size-agnostic")
else:
    fail("(c) checker rejected a valid contiguous surface")

# --- (d) self-guard: this file must mention the invariant COUNT nowhere. The
# count is absolutely free; documenting a count number, baseline, or threshold
# is itself noise (#792). Scan this file's own source (excluding this guard's
# own body, which must name the forbidden tokens) and fail if they reappear. ---
GUARD_MARKER = "# --- (d) self-guard:"
scanned = Path(__file__).read_text(encoding="utf-8").split(GUARD_MARKER, 1)[0]
forbidden = re.findall(
    r"\bbaseline\b|(?<!\d)59(?!\d)|count[ -](?:floor|threshold)",
    scanned,
    re.IGNORECASE,
)
if not forbidden:
    ok("(d) no invariant-count baseline language in this file")
else:
    fail(f"(d) residual count-baseline language: {sorted(set(forbidden))}")

sys.exit(FAIL)
