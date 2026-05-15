#!/usr/bin/env python3
# test-surface-skills-empty.py — asserts surface.skills is [] in feature.json.
#
# Invariant: surface.skills MUST be [] (empty array).
# Skills are managed via build-contract.json copy-file entries.
# The surface.skills field in feature.json is the retired mechanism.

import subprocess
import sys
import json
from pathlib import Path

REPO_ROOT = Path(subprocess.check_output(
    ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
    text=True
).strip())
FEATURE_DIR = REPO_ROOT / ".claude" / "features" / "rabbit-backlog"
FEATURE_JSON = FEATURE_DIR / "feature.json"

passed = 0
failed = 0


def ok(label):
    global passed
    print(f"  PASS  {label}")
    passed += 1


def fail_t(label, detail=""):
    global failed
    msg = f"  FAIL  {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    failed += 1


print("=== test-surface-skills-empty.py: surface.skills must be [] ===")
print()

# t1: feature.json exists
if FEATURE_JSON.is_file():
    ok("t1: feature.json exists")
else:
    fail_t("t1: feature.json exists", f"not found: {FEATURE_JSON}")

# t2: surface.skills is [] (empty array)
if FEATURE_JSON.is_file():
    try:
        d = json.loads(FEATURE_JSON.read_text())
        skills = d.get("surface", {}).get("skills", None)
        if skills is None:
            fail_t("t2: surface.skills is [] (empty array)", "surface.skills key missing")
        elif not isinstance(skills, list):
            fail_t("t2: surface.skills is [] (empty array)", f"surface.skills is not a list: {skills!r}")
        elif len(skills) != 0:
            fail_t("t2: surface.skills is [] (empty array)", f"surface.skills is not empty: {skills!r}")
        else:
            ok("t2: surface.skills is [] (empty array)")
    except Exception as e:
        fail_t("t2: surface.skills is [] (empty array)", str(e))
else:
    fail_t("t2: surface.skills is [] (empty array)", "feature.json not found (t1 prerequisite failed)")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
