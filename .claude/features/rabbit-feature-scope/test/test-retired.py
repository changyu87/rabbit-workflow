#!/usr/bin/env python3
"""Regression test for the rabbit-feature-scope retirement.

The feature has been retired; its surface was absorbed into rabbit-feature.
The directory must contain only the retirement notice (feature.json + spec.md)
plus this test directory. No scripts/, skills/, or docs/ may remain.
"""

import json
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parent.parent
FAIL = 0


def fail(msg: str) -> None:
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1


# 1. No forbidden subdirs.
for forbidden in ("scripts", "skills", "docs"):
    p = FEATURE_DIR / forbidden
    if p.exists():
        fail(f"{forbidden}/ still exists under retired rabbit-feature-scope")

# 2. Only the retirement-notice entries are allowed at the feature root.
allowed = {"feature.json", "spec.md", "test"}
actual = {p.name for p in FEATURE_DIR.iterdir()}
unexpected = actual - allowed
if unexpected:
    fail(f"unexpected entries in rabbit-feature-scope/: {sorted(unexpected)}")

# 3. feature.json marks the feature retired.
fj = FEATURE_DIR / "feature.json"
if not fj.exists():
    fail("feature.json missing")
else:
    data = json.loads(fj.read_text())
    if data.get("status") != "retired":
        fail(f"feature.json status must be 'retired', got {data.get('status')!r}")
    if data.get("tdd_state") != "retired":
        fail(f"feature.json tdd_state must be 'retired', got {data.get('tdd_state')!r}")

# 4. spec.md contains the retirement notice.
sm = FEATURE_DIR / "spec.md"
if not sm.exists():
    fail("spec.md missing")
else:
    text = sm.read_text()
    if "RETIRED" not in text:
        fail("spec.md must contain 'RETIRED' marker")
    if "rabbit-feature" not in text:
        fail("spec.md must reference absorbing feature 'rabbit-feature'")

if FAIL:
    print(f"FAILED: {FAIL}")
    sys.exit(1)
print("OK: rabbit-feature-scope retirement notice intact")
