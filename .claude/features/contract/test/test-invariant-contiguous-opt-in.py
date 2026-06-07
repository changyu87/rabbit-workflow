#!/usr/bin/env python3
"""test-invariant-contiguous-opt-in.py — Inv 30 contiguous strict tier (#724).

End-to-end test for the per-feature OPT-IN contiguous-numbering tier of
check_invariant_monotonic_order. The check enforces TWO tiers:

  * Baseline tier (all features): numbering must be strictly INCREASING
    within each Invariants section; gaps are tolerated.
  * Strict (contiguous) tier (opted-in features only): numbering must
    additionally be CONTIGUOUS (1..N, no holes). A feature opts in by
    declaring "contiguous_invariants": true in its OWN feature.json.

Cases (all hermetic — fixture feature trees in tmp dirs):
  t1  Opted-in feature with a GAP (1,2,4) FAILS the check, with a
      diagnostic naming the feature and the missing number.
  t2  Opted-in feature that is contiguous (1,2,3) PASSES.
  t3  Non-opted-in feature with the SAME gap (1,2,4) PASSES (back-compat:
      the strict tier binds only to opted-in features).
  t4  A NON-monotonic opted-in feature (1,5,3) still FAILS (baseline tier
      is unchanged and applies to everyone).

Non-interactive. Exits non-zero on any failure.
"""

import importlib.util
import json
import os
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")

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


def load_checks():
    spec = importlib.util.spec_from_file_location(
        "contract_lib_checks_contig", CHECKS_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_feature(root, name, nums, *, opt_in):
    feat = os.path.join(root, name)
    docs = os.path.join(feat, "docs")
    os.makedirs(docs)
    body = "# F\n\n## Invariants\n\n" + "".join(
        f"{n}. invariant number {n}.\n" for n in nums
    )
    with open(os.path.join(docs, "spec.md"), "w") as f:
        f.write(body)
    fj = {
        "name": name,
        "version": "1.0.0",
        "owner": "test",
        "tdd_state": "test-green",
        "summary": "x",
        "deprecation_criterion": "x",
    }
    if opt_in:
        fj["contiguous_invariants"] = True
    with open(os.path.join(feat, "feature.json"), "w") as f:
        json.dump(fj, f)
    return feat


checks = load_checks()

# t1: opted-in feature with a gap FAILS
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, "opt-in-gap", [1, 2, 4], opt_in=True)
    res = checks.check_invariant_monotonic_order([feat])
    joined = "\n".join(res.messages)
    if not res.passed and "opt-in-gap" in joined:
        ok("t1", "opted-in feature with gap (1,2,4) is rejected")
    else:
        ko("t1", f"opted-in gap not rejected; passed={res.passed} msgs={res.messages}")

# t2: opted-in contiguous feature PASSES
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, "opt-in-contig", [1, 2, 3], opt_in=True)
    res = checks.check_invariant_monotonic_order([feat])
    if res.passed:
        ok("t2", "opted-in contiguous feature (1,2,3) passes")
    else:
        ko("t2", f"opted-in contiguous wrongly rejected: {res.messages}")

# t3: non-opted-in feature with the same gap PASSES (back-compat)
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, "no-opt-gap", [1, 2, 4], opt_in=False)
    res = checks.check_invariant_monotonic_order([feat])
    if res.passed:
        ok("t3", "non-opted-in feature with gap (1,2,4) still passes (back-compat)")
    else:
        ko("t3", f"non-opted-in gap wrongly rejected: {res.messages}")

# t4: non-monotonic opted-in feature still FAILS (baseline tier unchanged)
with tempfile.TemporaryDirectory() as tmp:
    feat = make_feature(tmp, "opt-in-nonmono", [1, 5, 3], opt_in=True)
    res = checks.check_invariant_monotonic_order([feat])
    if not res.passed:
        ok("t4", "opted-in non-monotonic feature (1,5,3) still fails")
    else:
        ko("t4", f"non-monotonic opted-in wrongly passed: {res.messages}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
