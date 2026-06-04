#!/usr/bin/env python3
"""test-contiguous-invariants-optin.py — policy opts into the contract
strict contiguous-invariant tier (#724 follow-up, #739).

Asserts two things:

  1. policy/feature.json declares `"contiguous_invariants": true` at the top
     level — the per-feature opt-in into the contract strict tier
     (mirrors the Inv 41 housekeeping_clean opt-in pattern).
  2. policy's own spec.md numbers its `## Invariants` section contiguously
     1..N (no holes), using the SAME parsing semantics as the contract
     gate `check_invariant_monotonic_order` (lib/checks.py): numbered items
     are top-level `N. ` lines; any non-`Invariants` heading closes the
     current run and resets the counter. This keeps the local guard
     faithful to the cross-feature gate so a drift here is caught before
     the contract suite reddens.

Traces: #739 (opt policy into contiguous_invariants strict tier).

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when the contract strict contiguous tier is the
universal baseline (all features opted in) and the per-feature opt-in flag
is retired, making this guard redundant.
"""
import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

# Mirror contract/lib/checks.py parsing semantics exactly.
_INVARIANTS_HEADING_RE = re.compile(r"^(##|###)\s+Invariants\b")
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+")
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s")


def fail(msg):
    print(f"FAIL: #739: {msg}", file=sys.stderr)
    sys.exit(1)


# (1) opt-in flag
with open(FEATURE_JSON) as f:
    data = json.load(f)

if data.get("contiguous_invariants") is not True:
    fail(
        "feature.json must declare top-level "
        '"contiguous_invariants": true (got '
        f"{data.get('contiguous_invariants')!r})"
    )

# (2) contiguous 1..N under each Invariants section, contract semantics
with open(SPEC, encoding="utf-8") as f:
    lines = f.read().splitlines()

in_section = False
prev_num = 0
in_fence = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        in_fence = not in_fence
        continue
    if in_fence:
        continue
    if _ANY_HEADING_RE.match(line):
        in_section = bool(_INVARIANTS_HEADING_RE.match(line))
        prev_num = 0
        continue
    if not in_section:
        continue
    m = _NUMBERED_ITEM_RE.match(line)
    if m:
        n = int(m.group(1))
        if n != prev_num + 1:
            missing = ", ".join(str(g) for g in range(prev_num + 1, n))
            fail(
                f"spec.md Invariants not contiguous: {prev_num} -> {n} "
                f"(missing {missing}); run "
                "contract/scripts/reflow-invariants.py"
            )
        prev_num = n

print("All checks passed.")
