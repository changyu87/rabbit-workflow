#!/usr/bin/env python3
"""test-spec-lean.py — measured-reduction guard for docs/spec.md.

End-to-end content test pinning the outcome of the spec reduction wave: the
redundant prose removed from docs/spec.md stays removed, while the load-bearing
tokens that carry behaviour/scope survive.

  - t1: Purpose does NOT restate the Tier-1/Tier-2 boundary (that boundary is
        owned authoritatively by "What this feature does NOT define").
  - t2: Tech Stack carries no decorative cross-reference parenthetical naming
        other features' Python-only invariants.
  - t3: the load-bearing scope-exclusion owners survive verbatim
        (rabbit-feature, rabbit-cage, contract, rabbit-spec).
  - t4: the contiguous-invariant opt-in claim survives (the load-bearing
        Inv 30 strict-tier enforcement statement and the feature.json flag).

Non-interactive. Exits non-zero on failure.
"""

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
SPEC = os.path.join(FEATURE_DIR, "docs", "spec.md")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


with open(SPEC) as f:
    body = f.read()

# t1: Purpose no longer restates the Tier-1/Tier-2 boundary.
if "Tier-1" not in body and "Tier-2" not in body:
    ok("t1", "no redundant Tier-1/Tier-2 boundary restatement")
else:
    fail("t1", "Tier-1/Tier-2 boundary restatement reappeared in spec.md")

# t2: Tech Stack carries no decorative cross-reference parenthetical.
if "matches the Python-only invariants" not in body:
    ok("t2", "no decorative Python-only cross-reference parenthetical")
else:
    fail("t2", "decorative Python-only cross-reference parenthetical reappeared")

# t3: load-bearing scope-exclusion owners survive.
required_owners = [
    "owned by `rabbit-feature`",
    "owned by `rabbit-cage`",
    "owned by `contract`",
    "owned by `rabbit-spec`",
]
missing = [tok for tok in required_owners if tok not in body]
if not missing:
    ok("t3", "load-bearing scope-exclusion owners survive")
else:
    fail("t3", f"missing load-bearing scope-exclusion owners: {missing}")

# t4: contiguous-invariant opt-in claim survives.
if '"contiguous_invariants": true' in body and "Inv 30 strict tier" in body:
    ok("t4", "contiguous-invariant opt-in + Inv 30 enforcement claim survives")
else:
    fail("t4", "load-bearing contiguous-invariant opt-in claim was lost")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-lean: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-lean: all checks passed.")
sys.exit(0)
