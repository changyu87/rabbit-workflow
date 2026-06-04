#!/usr/bin/env python3
"""test-spec-bodies-allowlist-retired-literal.py — issue #634.

End-to-end test that the production ALLOWLIST in
test-spec-bodies-no-historical-tags.py exempts the legitimate literal
status value "retired" in rabbit-config's docs/spec.md.

rabbit-config's spec.md documents rabbit-config.py's
`data.get("status") == "retired"` check (status enum ["active","retired"],
contract Inv 28) on the line that reads "...skipping retired features".
The strict-tier checker flags the bare word "retired" as tombstone
language, but here it is the load-bearing literal value the interpreter
checks verbatim — it cannot be reworded without making the spec
inaccurate. The contract ALLOWLIST already exempts contract's OWN spec.md
retired-enum lines; this asserts the same mechanism now covers
rabbit-config's status-enum literal.

The test drives the REAL checker (no fixture features root) with
rabbit-config simulated as opted-in to the strict tier via the
RABBIT_HISTORICAL_TAGS_CLEANED override (which REPLACES the
feature.json-derived opt-in set, so ONLY rabbit-config is strict-enforced
and every other feature stays baseline-only — keeping the run's pass/fail
pinned to the rabbit-config "retired" line under test). The "retired"
occurrence is the single strict-tier match in rabbit-config's doc
surfaces, so:

  - WITH the production ALLOWLIST entry the run PASSES against the real
    features root (proving the content-keyed entry suppresses the real
    occurrence).
  - The allowlist is CONTENT-keyed, not line-pinned (#696): the SAME
    "retired" content reproduced at a DIFFERENT line number in a fixture
    features root is STILL suppressed (the run PASSES). This is the
    line-shift-independence regression — a housekeeping line removal that
    shifts the real "retired" line no longer reddens the gate. (A genuine
    strict-tier violation is exercised by the separate
    test-spec-bodies-strict-tier.py negative arms; here the point is that a
    legitimate, allowlisted occurrence survives an arbitrary line shift.)

Non-interactive. Exits non-zero on failure.
"""

import os
import re
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
FEATURES_ROOT = os.path.join(REPO_ROOT, ".claude", "features")
CHECKER = os.path.join(TEST_DIR, "test-spec-bodies-no-historical-tags.py")

RC_SPEC = os.path.join(
    FEATURES_ROOT, "rabbit-config", "docs", "spec.md")

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


def run(features_root, cleaned):
    """Run the checker with the given features root and a forced opt-in set.
    cleaned is passed as RABBIT_HISTORICAL_TAGS_CLEANED (REPLACES the
    feature.json-derived set)."""
    env = dict(os.environ)
    env["RABBIT_HISTORICAL_TAGS_FEATURES_ROOT"] = features_root
    env["RABBIT_HISTORICAL_TAGS_CLEANED"] = cleaned
    env.pop("RABBIT_HISTORICAL_TAGS_ALLOWLIST", None)
    return subprocess.run(
        ["python3", CHECKER], capture_output=True, text=True, env=env)


# t0: checker + rabbit-config spec.md exist.
if not os.path.isfile(CHECKER):
    fail("t0", f"checker missing: {CHECKER}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
if not os.path.isfile(RC_SPEC):
    fail("t0", f"rabbit-config spec.md missing: {RC_SPEC}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "checker and rabbit-config spec.md exist")

# Locate the "retired" status-enum line in the live rabbit-config spec.md.
# The production ALLOWLIST entry is line-pinned to this number.
with open(RC_SPEC) as f:
    rc_lines = f.readlines()
retired_lines = [
    i for i, ln in enumerate(rc_lines, start=1)
    if re.search(r"skipping retired features", ln)
]
if len(retired_lines) != 1:
    fail("t0b", f"expected exactly one 'skipping retired features' line in "
                f"{RC_SPEC}; found {retired_lines}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
RETIRED_LINE = retired_lines[0]
ok("t0b", f"rabbit-config 'retired' status-enum literal on line "
          f"{RETIRED_LINE}")

# t1: against the REAL features root with rabbit-config opted in, the run
# PASSES — the production ALLOWLIST entry (content-keyed) suppresses the only
# strict-tier match in rabbit-config's doc surfaces.
r_real = run(FEATURES_ROOT, "rabbit-config")
if r_real.returncode == 0:
    ok("t1", "production allowlist suppresses real rabbit-config 'retired' "
             "literal (opted-in run passes)")
else:
    fail("t1", "expected exit 0 against real features root with rabbit-config "
               f"opted in; exit={r_real.returncode}; "
               f"stdout={r_real.stdout}; stderr={r_real.stderr}")

# t2: line-shift independence (#696). Reproduce rabbit-config's "skipping
# retired features" line at a DIFFERENT line number in a fixture features
# root. Under the OLD line-pinned allowlist this run FAILED (the pinned line
# number no longer matched), penalizing any housekeeping line removal. Under
# the content-keyed allowlist the SAME content is STILL suppressed wherever
# it lands, so the run MUST PASS — proving the gate is delinked from the
# cross-feature line count.
with tempfile.TemporaryDirectory() as tmp:
    fdir = os.path.join(tmp, "rabbit-config", "docs")
    os.makedirs(fdir, exist_ok=True)
    # Prepend blank lines so "skipping retired features" lands at a line
    # number that is NOT the original production allowlist line for
    # rabbit-config.
    shifted = ["\n"] * (RETIRED_LINE + 5) + [
        "   alphabetical order by feature directory name, "
        "skipping retired features\n"
    ]
    with open(os.path.join(fdir, "spec.md"), "w") as f:
        f.writelines(shifted)
    r_shift = run(tmp, "rabbit-config")
    if r_shift.returncode == 0:
        ok("t2", "content-keyed allowlist suppresses the 'retired' literal at "
                 "a shifted line (line-shift independent)")
    else:
        fail("t2", "expected exit 0 when the allowlisted 'retired' content is "
                   f"shifted to a new line; exit={r_shift.returncode}; "
                   f"stdout={r_shift.stdout}; stderr={r_shift.stderr}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-bodies-allowlist-retired-literal: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-bodies-allowlist-retired-literal: all checks passed.")
sys.exit(0)
