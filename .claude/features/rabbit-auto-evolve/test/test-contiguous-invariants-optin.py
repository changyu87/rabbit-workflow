#!/usr/bin/env python3
"""test-contiguous-invariants-optin.py — rabbit-auto-evolve (issue #738).

Locks in rabbit-auto-evolve's opt-in to the contract STRICT contiguous
invariant-numbering tier (#724 follow-up). The strict tier is per-feature
opt-in via `feature.json "contiguous_invariants": true`; this feature reflowed
to contiguous 1..N under #725 and now declares the flag so the contract suite
enforces contiguity on it permanently.

End-to-end (operates on the SHIPPED surfaces — feature.json + docs/spec.md +
the live contract strict-tier check):

  (a) feature.json declares `"contiguous_invariants": true` at the top level.

  (b) The docs/spec.md `## Invariants` section is contiguous 1..N (no gaps,
      no duplicates) — the precondition the flag asserts.

  (c) The contract strict-tier check itself — `check_invariant_monotonic_order`
      reading rae's real feature.json opt-in — passes GREEN for this feature.
      This is the true end-to-end gate: the same code the contract suite runs.

Non-interactive. Exits non-zero on any failure.
"""

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"
SPEC_MD = FEATURE_DIR / "docs" / "spec.md"
REPO_ROOT = FEATURE_DIR.parents[2]
CONTRACT_LIB = REPO_ROOT / ".claude" / "features" / "contract" / "lib"

FAIL = 0


def fail(msg):
    global FAIL
    print(f"FAIL: {msg}", file=sys.stderr)
    FAIL = 1


def ok(msg):
    print(f"PASS: {msg}")


# --- (a) feature.json opt-in flag ---
fj = json.loads(FEATURE_JSON.read_text(encoding="utf-8"))
if fj.get("contiguous_invariants") is True:
    ok('(a) feature.json declares "contiguous_invariants": true')
else:
    fail(
        '(a) feature.json missing top-level "contiguous_invariants": true; '
        f"got {fj.get('contiguous_invariants')!r}"
    )

# --- (b) docs/spec.md ## Invariants section is contiguous 1..N ---
text = SPEC_MD.read_text(encoding="utf-8")
lines = text.splitlines()
heading_re = re.compile(r"^(#{1,6})\s+")
inv_heading_re = re.compile(r"^##\s+Invariants\b")
item_re = re.compile(r"^(\d+)\.\s+\*\*")

in_section = False
in_fence = False
nums = []
for line in lines:
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
        nums.append(int(m.group(1)))

N = len(nums)
if nums and nums == list(range(1, N + 1)):
    ok(f"(b) docs/spec.md invariants contiguous 1..{N}")
else:
    defined = set(nums)
    gaps = sorted(set(range(1, (max(nums) if nums else 0) + 1)) - defined)
    dups = sorted({n for n in nums if nums.count(n) > 1})
    fail(f"(b) invariants not contiguous 1..N: found {nums}; gaps={gaps}; dups={dups}")

# --- (c) live contract strict-tier check passes for rae ---
# Run the SAME check the contract suite runs (check_invariant_monotonic_order),
# scoped to rae's own feature dir. With the flag opted in, the strict tier is
# active for rae, so a GREEN result proves contiguity is enforced (not merely
# tolerated). A VIOLATION line naming rae is the failure signal.
sys.path.insert(0, str(CONTRACT_LIB))
try:
    import checks  # noqa: E402

    result = checks.check_invariant_monotonic_order([str(FEATURE_DIR)])
    rae_violations = [
        m for m in result.messages
        if m.startswith("VIOLATION:") and "rabbit-auto-evolve" in m
    ]
    if result.passed and not rae_violations:
        ok("(c) contract strict-tier check_invariant_monotonic_order GREEN for rae")
    else:
        fail(
            "(c) contract strict-tier not GREEN for rae: "
            f"passed={result.passed}; violations={rae_violations}"
        )
except Exception as exc:  # pragma: no cover - import/path issues surface here
    fail(f"(c) could not run contract strict-tier check: {exc!r}")

sys.exit(FAIL)
