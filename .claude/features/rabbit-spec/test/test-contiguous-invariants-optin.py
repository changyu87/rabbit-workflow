#!/usr/bin/env python3
"""test-contiguous-invariants-optin.py — issue #742 (#724 follow-up)

End-to-end check that rabbit-spec has opted into the strict CONTIGUOUS
invariant-numbering tier introduced by the contract feature in #724.

Two facts are asserted, both exercised through the LIVE contract surfaces so
this is a true E2E test (not a private re-implementation of the rule):

  1. rabbit-spec's feature.json declares `"contiguous_invariants": true` at
     the top level, and the contract feature's `_contiguous_opt_in` helper
     reports rabbit-spec as opted in.

  2. rabbit-spec's invariant numbering is contiguous 1..N (no holes) — i.e.
     the contract feature's `check_invariant_monotonic_order`, run over
     rabbit-spec under the strict tier, passes. (Opting into the flag while
     numbering still has a gap would redden the repo-wide contract gate; this
     test guards against that regression.)

Run non-interactively. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the strict contiguous tier is enforced
workflow-wide by default (no per-feature opt-in), making this per-feature
opt-in assertion redundant.
"""
import json
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_CONTRACT_LIB = os.path.abspath(os.path.join(FEATURE_DIR, "..", "contract", "lib"))
if _CONTRACT_LIB not in sys.path:
    sys.path.insert(0, _CONTRACT_LIB)
from checks import _contiguous_opt_in, check_invariant_monotonic_order  # noqa: E402


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


# 1. The flag is set in feature.json.
with open(os.path.join(FEATURE_DIR, "feature.json"), encoding="utf-8") as f:
    feature = json.load(f)
if feature.get("contiguous_invariants") is not True:
    fail('feature.json must declare top-level "contiguous_invariants": true')

# Ensure the env override (hermetic-test escape hatch) is NOT leaking in, so we
# exercise the real feature.json-derived opt-in path.
prior_override = os.environ.pop("RABBIT_CONTIGUOUS_INVARIANTS", None)
try:
    if not _contiguous_opt_in(FEATURE_DIR):
        fail("contract _contiguous_opt_in does not report rabbit-spec as opted in")

    # 2. Numbering is contiguous 1..N under the strict tier.
    result = check_invariant_monotonic_order([FEATURE_DIR])
    if not result.passed:
        fail(
            "check_invariant_monotonic_order failed for rabbit-spec under the "
            f"strict contiguous tier: {result.messages}"
        )
finally:
    if prior_override is not None:
        os.environ["RABBIT_CONTIGUOUS_INVARIANTS"] = prior_override

print("All checks passed.")
