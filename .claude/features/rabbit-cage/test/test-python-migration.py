#!/usr/bin/env python3
"""Tests verifying complete Python migration: no .sh references in sync-check.py,
tests use .rabbit-skills-updated marker, test harnesses are Python files.
Covers Spec Inv 26, 28, 39 and BACKLOG14 test correctness."""
import glob
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

HOOKS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/scripts")
TEST_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/test")
SPEC_FILE = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/docs/spec/spec.md")
SYNC_CHECK = os.path.join(HOOKS_DIR, "sync-check.py")

failures = 0
total = 0


def ok(msg):
    global total
    total += 1
    print(f"  PASS t{total}: {msg}")


def fail_t(msg):
    global total, failures
    total += 1
    failures += 1
    print(f"  FAIL t{total}: {msg}")


print("test-python-migration.py")
print("Verifying complete Python migration (Spec Inv 26, 28, 39)")
print()

# t1: sync-check.py does NOT reference test-generated-surface.sh
print("=== t1: sync-check.py references test-generated-surface.py (not .sh) ===")
with open(SYNC_CHECK) as f:
    sync_content = f.read()
if "test-generated-surface.sh" in sync_content:
    fail_t("sync-check.py still references test-generated-surface.sh — must use .py (Spec Inv 26)")
else:
    ok("sync-check.py does not reference test-generated-surface.sh")

if "test-generated-surface.py" in sync_content:
    ok("sync-check.py references test-generated-surface.py")
else:
    fail_t("sync-check.py does not reference test-generated-surface.py — Spec Inv 26 requires .py")

# t2: test-generated-surface.py exists (Spec Inv 26)
print("=== t2: test-generated-surface.py exists (Spec Inv 26) ===")
py_surf = os.path.join(TEST_DIR, "test-generated-surface.py")
if os.path.isfile(py_surf):
    ok("test-generated-surface.py exists (Spec Inv 26)")
else:
    fail_t("test-generated-surface.py does NOT exist — violates Spec Inv 26")

# t3: test-generated-surface.sh does NOT exist in test/ (replaced by .py)
print("=== t3: test-generated-surface.sh does NOT exist in test/ ===")
sh_surf = os.path.join(TEST_DIR, "test-generated-surface.sh")
if not os.path.exists(sh_surf):
    ok("test-generated-surface.sh does not exist (correctly replaced by .py)")
else:
    fail_t("test-generated-surface.sh still exists — should be replaced by test-generated-surface.py")

# t4: no .sh files exist in test/ (Spec Inv 39 updated)
print("=== t4: no .sh files exist in test/ (Spec Inv 39) ===")
sh_in_test = sorted(glob.glob(os.path.join(TEST_DIR, "*.sh")))
if not sh_in_test:
    ok("test/ has no .sh files (Spec Inv 39)")
else:
    fail_t(f"test/ still contains .sh files: {' '.join(sh_in_test)} — violates Spec Inv 39")

# t5: BACKLOG7 test references test-generated-surface.py (not .sh)
print("=== t5: test-RABBIT-CAGE-BACKLOG7 uses test-generated-surface.py ===")
backlog7 = os.path.join(TEST_DIR, "test-RABBIT-CAGE-BACKLOG7-visual-messages.py")
with open(backlog7) as f:
    b7_content = f.read()
if "test-generated-surface.sh" in b7_content:
    fail_t("BACKLOG7 test still references test-generated-surface.sh — must use .py")
else:
    ok("BACKLOG7 test does not reference test-generated-surface.sh")

# t6: BACKLOG9 test references test-generated-surface.py (not .sh)
print("=== t6: test-RABBIT-CAGE-BACKLOG9 uses test-generated-surface.py ===")
backlog9 = os.path.join(TEST_DIR, "test-RABBIT-CAGE-BACKLOG9-green-messages.py")
with open(backlog9) as f:
    b9_content = f.read()
if "test-generated-surface.sh" in b9_content:
    fail_t("BACKLOG9 test still references test-generated-surface.sh — must use .py")
else:
    ok("BACKLOG9 test does not reference test-generated-surface.sh")

# t7: BACKLOG14 test uses .rabbit-skills-updated (not .rabbit-plugins-stale)
print("=== t7: test-RABBIT-CAGE-BACKLOG14 uses .rabbit-skills-updated marker ===")
backlog14 = os.path.join(TEST_DIR, "test-RABBIT-CAGE-BACKLOG14-conditional-priority.py")
with open(backlog14) as f:
    b14_content = f.read()
if ".rabbit-plugins-stale" in b14_content:
    fail_t("BACKLOG14 test still uses .rabbit-plugins-stale — must use .rabbit-skills-updated")
else:
    ok("BACKLOG14 test does not use .rabbit-plugins-stale")

if ".rabbit-skills-updated" in b14_content:
    ok("BACKLOG14 test uses .rabbit-skills-updated")
else:
    fail_t("BACKLOG14 test does not use .rabbit-skills-updated — test checks wrong marker")

# t8: BACKLOG14 checks for 'Skills-updated' in spec (not 'Plugins-stale')
print("=== t8: test-RABBIT-CAGE-BACKLOG14 checks 'Skills-updated' in spec ===")
if "Plugins-stale" in b14_content or "plugins stale" in b14_content.lower():
    fail_t("BACKLOG14 test still checks for 'Plugins-stale' — must check 'Skills-updated'")
else:
    ok("BACKLOG14 test does not check for 'Plugins-stale'")

if "Skills-updated" in b14_content or "skills-updated" in b14_content or "skills updated" in b14_content.lower():
    ok("BACKLOG14 test checks for 'Skills-updated' in spec")
else:
    fail_t("BACKLOG14 test does not check for 'Skills-updated' — test checks wrong priority label")

# t9: run.py includes BACKLOG14, RABBIT-CAGE-22, and BUG4 tests
print("=== t9: run.py includes all 3 previously unregistered tests ===")
run_py = os.path.join(TEST_DIR, "run.py")
with open(run_py) as f:
    run_content = f.read()
for suite in ("test-RABBIT-CAGE-BACKLOG14-conditional-priority.py",
              "test-RABBIT-CAGE-22-stale-marker.py",
              "test-RABBIT-CAGE-BUG4.py"):
    if suite in run_content:
        ok(f"run.py includes {suite}")
    else:
        fail_t(f"run.py is missing {suite}")

# t10: spec Inv 26 references .py not .sh
print("=== t10: spec Inv 26 references test-generated-surface.py ===")
with open(SPEC_FILE) as f:
    spec_content = f.read()
import re
if re.search(r"26\. .+test-generated-surface\.py", spec_content):
    ok("spec Inv 26 correctly references test-generated-surface.py")
else:
    fail_t("spec Inv 26 does NOT reference test-generated-surface.py — spec not updated")

# t11: spec Tech Stack no longer says tests may be .sh
print("=== t11: spec Tech Stack section updated for Python tests ===")
if "may be `.sh` or `.py`" in spec_content or "may remain `.sh`" in spec_content:
    fail_t("spec Tech Stack still says tests may be .sh — must declare tests are Python")
else:
    ok("spec Tech Stack does not say tests may remain .sh")

print()
print(f"Results: {total - failures} passed, {failures} failed")
if failures == 0:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"{failures} TEST(S) FAILED")
    sys.exit(1)
