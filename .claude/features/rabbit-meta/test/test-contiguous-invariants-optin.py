#!/usr/bin/env python3
"""test-contiguous-invariants-optin.py — strict contiguous tier opt-in (#741)

End-to-end test verifying rabbit-meta has opted into the strict
contiguous-invariant-numbering tier (#724) and that its spec actually
satisfies it:
  - t1: feature.json declares "contiguous_invariants": true at top level
  - t2: spec.md "## Invariants" leading numbers are contiguous 1..N
        (verified via the canonical contract checker, opted-in tier),
        so the contract suite's Inv 30 strict tier passes for rabbit-meta
"""

import importlib.util
import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
FEATURES_ROOT = os.path.dirname(FEATURE_DIR)
CHECKS_PATH = os.path.join(FEATURES_ROOT, "contract", "lib", "checks.py")
_spec = importlib.util.spec_from_file_location("checks", CHECKS_PATH)
_checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checks)

PASS = 0
FAIL = 0


def ok(n, msg):
    global PASS
    print(f"  PASS {n}: {msg}")
    PASS += 1


def fail_t(n, msg):
    global FAIL
    print(f"  FAIL {n}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: feature.json opt-in flag
with open(os.path.join(FEATURE_DIR, "feature.json")) as f:
    fj = json.load(f)
if fj.get("contiguous_invariants") is True:
    ok("t1", 'feature.json "contiguous_invariants" is true')
else:
    fail_t("t1", f'feature.json "contiguous_invariants" is {fj.get("contiguous_invariants")!r}, expected True')

# t2: spec numbering passes the canonical strict (contiguous) tier check.
# Drive the canonical checker against rabbit-meta only, forcing the opt-in
# via the test override so the result reflects the strict tier regardless of
# the just-written flag.
os.environ["RABBIT_CONTIGUOUS_INVARIANTS"] = "rabbit-meta"
res = _checks.check_invariant_monotonic_order([FEATURE_DIR])
del os.environ["RABBIT_CONTIGUOUS_INVARIANTS"]
violations = [m for m in res.messages if m.startswith("VIOLATION")]
if res.passed and not violations:
    ok("t2", "spec.md invariants are contiguous 1..N (strict tier passes)")
else:
    fail_t("t2", f"strict-tier check failed: {res.messages}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
