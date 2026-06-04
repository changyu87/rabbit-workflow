#!/usr/bin/env python3
"""test-contiguous-invariants-optin.py — issue #740 (#724 follow-up)

End-to-end check that rabbit-decompose has opted into the contract feature's
strict CONTIGUOUS-invariant tier and that its spec actually satisfies that
tier.

#724 added a per-feature, data-driven opt-in to the contract suite's Inv 30
strict tier: a feature opts in by declaring `"contiguous_invariants": true`
at the top level of its OWN feature.json, after which its `## Invariants`
section MUST number contiguously 1..N with no holes (not merely strictly
increasing). #740 opts rabbit-decompose in.

This E2E test asserts the post-opt-in shape independent of the version string:

  - feature.json declares `"contiguous_invariants": true` at top level.
  - The live contract check (check_invariant_monotonic_order) — the same
    function the repo gate (contract/test/run.py) runs cross-feature —
    passes for THIS feature, proving the spec's invariants are contiguous
    1..N under the strict tier the flag turns on.

Run non-interactively. Exits non-zero on failure.

Version: 0.1.0
Owner: rabbit-workflow team
Deprecation criterion: when the strict CONTIGUOUS tier is enforced
workflow-wide for every feature, making this per-feature opt-in assertion
redundant.
"""
import json
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Import the live contract check the way the repo gate runs it, so this E2E
# test exercises the real strict-tier code path rather than re-implementing it.
_CONTRACT_LIB = os.path.abspath(os.path.join(FEATURE_DIR, "..", "contract", "lib"))
if _CONTRACT_LIB not in sys.path:
    sys.path.insert(0, _CONTRACT_LIB)
from checks import check_invariant_monotonic_order  # noqa: E402


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


# 1. feature.json carries the opt-in flag.
with open(os.path.join(FEATURE_DIR, "feature.json"), encoding="utf-8") as f:
    feature = json.load(f)
if feature.get("contiguous_invariants") is not True:
    fail(
        'feature.json must declare top-level `"contiguous_invariants": true`; '
        f'found {feature.get("contiguous_invariants")!r}'
    )

# 2. Under the strict tier the flag turns on, the live contract check passes
#    for this feature (invariants number contiguously 1..N, no holes).
result = check_invariant_monotonic_order([FEATURE_DIR])
if not result.passed:
    fail(
        "check_invariant_monotonic_order failed under the contiguous tier "
        f"for rabbit-decompose: {result.messages}"
    )

print("All checks passed.")
