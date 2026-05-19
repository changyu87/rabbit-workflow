#!/usr/bin/env python3
"""Regression test for the rabbit-feature-scope retirement.

The feature has been retired; its surface was absorbed into rabbit-feature.
The directory must contain only the retirement notice (feature.json plus
docs/spec/spec.md) and this test directory. No scripts/, skills/, or other
surface files may remain.
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
for forbidden in ("scripts", "skills"):
    p = FEATURE_DIR / forbidden
    if p.exists():
        fail(f"{forbidden}/ still exists under retired rabbit-feature-scope")

# 2. Only retirement-notice entries are allowed at the feature root.
allowed_root = {"feature.json", "docs", "test"}
actual_root = {p.name for p in FEATURE_DIR.iterdir()}
unexpected = actual_root - allowed_root
if unexpected:
    fail(f"unexpected entries in rabbit-feature-scope/: {sorted(unexpected)}")

# 3. docs/ must contain ONLY the retirement spec.md (at docs/spec/spec.md).
docs = FEATURE_DIR / "docs"
if docs.exists():
    allowed_docs = {"spec/spec.md"}
    actual_docs = {p.relative_to(docs).as_posix() for p in docs.rglob("*") if p.is_file()}
    extra = actual_docs - allowed_docs
    if extra:
        fail(f"unexpected files under docs/: {sorted(extra)}")
    if not (docs / "spec" / "spec.md").exists():
        fail("docs/spec/spec.md missing")

# 4. feature.json marks the feature retired.
fj = FEATURE_DIR / "feature.json"
if not fj.exists():
    fail("feature.json missing")
else:
    data = json.loads(fj.read_text())
    if data.get("status") != "retired":
        fail(f"feature.json status must be 'retired', got {data.get('status')!r}")
    if data.get("tdd_state") != "retired":
        fail(f"feature.json tdd_state must be 'retired', got {data.get('tdd_state')!r}")

# 5. spec.md contains the retirement notice and points at absorbing feature.
sm = docs / "spec" / "spec.md" if docs.exists() else None
if sm and sm.exists():
    text = sm.read_text()
    if "RETIRED" not in text:
        fail("spec.md must contain 'RETIRED' marker")
    if "rabbit-feature" not in text:
        fail("spec.md must reference absorbing feature 'rabbit-feature'")

if FAIL:
    print(f"FAILED: {FAIL}")
    sys.exit(1)
print("OK: rabbit-feature-scope retirement notice intact")
