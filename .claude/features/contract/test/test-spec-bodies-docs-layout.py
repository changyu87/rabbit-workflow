#!/usr/bin/env python3
"""test-spec-bodies-docs-layout.py — Inv 69 dual-read scan coverage.

End-to-end test proving the contract spec-body scanners
(test-spec-bodies-no-historical-tags.py and, by extension, the
strict-tier behaviour exercised by test-spec-bodies-strict-tier.py)
resolve a feature's spec/contract doc surfaces through the SAME dual-read
resolver as lib/checks.py (prefer flat docs/<name>, fall back to
specs/<name>). Without dual-read a feature migrated to the flat docs/
layout silently drops out of the scan — a coverage regression that
produces a FALSE GREEN.

Drives the checker as a subprocess against fixture feature trees built
under tempfile.TemporaryDirectory(), using the
RABBIT_HISTORICAL_TAGS_FEATURES_ROOT and RABBIT_HISTORICAL_TAGS_CLEANED
env overrides so the test never depends on the live repo's layout.

Behaviours covered (each from Inv 69):

  t1: a feature laid out flat-docs/ (docs/spec.md) with a baseline-tier
      historical tag is DETECTED (proving migrated features are scanned).
  t2: the same feature laid out specs/ (specs/spec.md) is also detected
      (the fallback path stays live).
  t3: a strict-tier violation in a flat-docs/ feature that has opted in
      (feature.json housekeeping_clean) is DETECTED.
  t4: a docs/contract.md surface is also scanned (not just docs/spec.md).
  t5: a sibling docs/bugs/ subdirectory is NEVER a resolution target
      (only the flat docs/<name> file is scanned).

Non-interactive. Exits non-zero on failure.
"""

import json
import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(TEST_DIR, "test-spec-bodies-no-historical-tags.py")

PASS = 0
FAIL = 0

# Assembled by concatenation so this test file itself carries no literal
# strict-tier / baseline strings that a future scan of the corpus could
# trip on (the scanner never scans test/, but this is defensive).
_HASH_REF = "see " + "#" + "123 for context"
_TOMBSTONE = "this was " + "superseded" + " later"
_BASELINE = "BUG" + "-7 tracked this"


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


def make_feature_docs(root, name, spec_body=None, contract_body=None,
                      bugs_body=None, housekeeping_clean=None):
    """Create <root>/<name>/docs/{spec.md,contract.md} (flat docs/ layout),
    plus an optional docs/bugs/<bug>.md sibling and an optional feature.json
    with a top-level housekeeping_clean flag."""
    docs = os.path.join(root, name, "docs")
    os.makedirs(docs, exist_ok=True)
    if spec_body is not None:
        with open(os.path.join(docs, "spec.md"), "w") as f:
            f.write(spec_body)
    if contract_body is not None:
        with open(os.path.join(docs, "contract.md"), "w") as f:
            f.write(contract_body)
    if bugs_body is not None:
        bugs = os.path.join(docs, "bugs")
        os.makedirs(bugs, exist_ok=True)
        with open(os.path.join(bugs, "bug-1.md"), "w") as f:
            f.write(bugs_body)
    if housekeeping_clean is not None:
        with open(os.path.join(root, name, "feature.json"), "w") as f:
            json.dump({"name": name, "housekeeping_clean": housekeeping_clean},
                      f)


def make_feature_specs(root, name, spec_body):
    """Create <root>/<name>/specs/spec.md (legacy specs/ layout)."""
    specs = os.path.join(root, name, "specs")
    os.makedirs(specs, exist_ok=True)
    with open(os.path.join(specs, "spec.md"), "w") as f:
        f.write(spec_body)


def run(features_root, cleaned=None):
    env = dict(os.environ)
    env["RABBIT_HISTORICAL_TAGS_FEATURES_ROOT"] = features_root
    env.pop("RABBIT_HISTORICAL_TAGS_CLEANED", None)
    if cleaned is not None:
        env["RABBIT_HISTORICAL_TAGS_CLEANED"] = cleaned
    return subprocess.run(
        ["python3", CHECKER],
        capture_output=True,
        text=True,
        env=env,
    )


# t0: checker exists
if not os.path.isfile(CHECKER):
    fail("t0", f"checker missing: {CHECKER}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1)
ok("t0", "checker exists")

# t1: flat-docs/ feature with a baseline tag in docs/spec.md is DETECTED.
with tempfile.TemporaryDirectory() as tmp:
    body = "# alpha\n\n" + _BASELINE + "\n"
    make_feature_docs(tmp, "alphadocs", spec_body=body)
    r = run(tmp, "")  # baseline tier is unconditional; empty strict set
    if r.returncode != 0 and "alphadocs" in (r.stdout + r.stderr):
        ok("t1", "flat-docs/ feature scanned (baseline tag detected)")
    else:
        fail("t1", f"expected nonzero + 'alphadocs'; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t2: same content on specs/ layout is also detected (fallback live).
with tempfile.TemporaryDirectory() as tmp:
    body = "# beta\n\n" + _BASELINE + "\n"
    make_feature_specs(tmp, "betaspecs", body)
    r = run(tmp, "")
    if r.returncode != 0 and "betaspecs" in (r.stdout + r.stderr):
        ok("t2", "specs/ fallback feature scanned (baseline tag detected)")
    else:
        fail("t2", f"expected nonzero + 'betaspecs'; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t3: strict-tier violation in a flat-docs/ opted-in feature is DETECTED
# (data-driven opt-in via feature.json housekeeping_clean, no env override).
with tempfile.TemporaryDirectory() as tmp:
    body = "# heading\n\n" + _HASH_REF + "\n" + _TOMBSTONE + "\n"
    make_feature_docs(tmp, "cleandocs", spec_body=body,
                      housekeeping_clean=True)
    r = run(tmp)  # derive opt-in from feature.json
    out = r.stdout + r.stderr
    if r.returncode != 0 and "cleandocs" in out:
        ok("t3", "flat-docs/ opted-in feature strict-scanned")
    else:
        fail("t3", f"expected nonzero + 'cleandocs'; exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

# t4: a docs/contract.md surface is scanned too (not just docs/spec.md).
with tempfile.TemporaryDirectory() as tmp:
    contract = "# gamma contract\n\n" + _BASELINE + "\n"
    make_feature_docs(tmp, "gammadocs",
                      spec_body="# gamma\n\nclean\n",
                      contract_body=contract)
    r = run(tmp, "")
    out = r.stdout + r.stderr
    if r.returncode != 0 and "contract.md" in out and "gammadocs" in out:
        ok("t4", "flat-docs/ contract.md surface scanned")
    else:
        fail("t4", f"expected nonzero naming docs/contract.md; "
                   f"exit={r.returncode}; stdout={r.stdout}; stderr={r.stderr}")

# t5: a sibling docs/bugs/ subdirectory is NEVER a resolution target.
with tempfile.TemporaryDirectory() as tmp:
    make_feature_docs(tmp, "deltadocs",
                      spec_body="# delta\n\nclean current design\n",
                      bugs_body="# bug\n\n" + _BASELINE + "\n")
    r = run(tmp, "")
    if r.returncode == 0:
        ok("t5", "docs/bugs/ sibling never scanned")
    else:
        fail("t5", f"expected exit 0 (bugs/ not a surface); exit={r.returncode}; "
                   f"stdout={r.stdout}; stderr={r.stderr}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")

if FAIL > 0:
    print("test-spec-bodies-docs-layout: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-spec-bodies-docs-layout: all checks passed.")
sys.exit(0)
