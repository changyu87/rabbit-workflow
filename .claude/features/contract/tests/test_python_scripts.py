#!/usr/bin/env python3
# test_python_scripts.py — TDD tests verifying that Python runtime scripts exist
# and the corresponding .sh wrapper files have been deleted.
#
# Affected scripts (all migrated to .py, .sh deleted):
#   find-feature.sh          -> find-feature.py
#   check-maps-consistent.sh -> check-maps-consistent.py
#   render-template.sh       -> render-template.py
#   workspace-map.sh         -> workspace-map.py
#   audit-orphan-storage.sh  -> audit-orphan-storage.py
#   check-template-schema-producer-consistency.sh -> check-template-schema-producer-consistency.py
#
# Exit: 0 all pass; 1 one or more failures.

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

result = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
SCRIPTS_DIR = os.path.join(REPO_ROOT, ".claude/features/contract/scripts") if REPO_ROOT else ""
ENFORCEMENT_DIR = os.path.join(SCRIPTS_DIR, "enforcement") if SCRIPTS_DIR else ""

PASS = 0
FAIL = 0


def check_exists(desc, filepath):
    global PASS, FAIL
    if os.path.isfile(filepath):
        print(f"  PASS: {desc}")
        PASS += 1
    else:
        print(f"  FAIL: {desc} (not found: {filepath})")
        FAIL += 1


def check_absent(desc, filepath):
    global PASS, FAIL
    if not os.path.isfile(filepath):
        print(f"  PASS: {desc}")
        PASS += 1
    else:
        print(f"  FAIL: {desc} (should not exist: {filepath})")
        FAIL += 1


print("=== test_python_scripts.py ===")

# --- find-feature ---
print()
print("--- find-feature ---")
check_exists("find-feature.py exists", os.path.join(SCRIPTS_DIR, "find-feature.py"))
check_absent("find-feature.sh deleted", os.path.join(SCRIPTS_DIR, "find-feature.sh"))

# --- check-maps-consistent ---
print()
print("--- check-maps-consistent ---")
check_exists("check-maps-consistent.py exists", os.path.join(SCRIPTS_DIR, "check-maps-consistent.py"))
check_absent("check-maps-consistent.sh deleted", os.path.join(SCRIPTS_DIR, "check-maps-consistent.sh"))

# --- render-template ---
print()
print("--- render-template ---")
check_exists("render-template.py exists", os.path.join(SCRIPTS_DIR, "render-template.py"))
check_absent("render-template.sh deleted", os.path.join(SCRIPTS_DIR, "render-template.sh"))

# --- workspace-map ---
print()
print("--- workspace-map ---")
check_exists("workspace-map.py exists", os.path.join(SCRIPTS_DIR, "workspace-map.py"))
check_absent("workspace-map.sh deleted", os.path.join(SCRIPTS_DIR, "workspace-map.sh"))

# --- audit-orphan-storage ---
print()
print("--- audit-orphan-storage ---")
check_exists("audit-orphan-storage.py exists", os.path.join(SCRIPTS_DIR, "audit-orphan-storage.py"))
check_absent("audit-orphan-storage.sh deleted", os.path.join(SCRIPTS_DIR, "audit-orphan-storage.sh"))

# --- check-template-schema-producer-consistency ---
print()
print("--- check-template-schema-producer-consistency ---")
check_exists(
    "check-template-schema-producer-consistency.py exists",
    os.path.join(ENFORCEMENT_DIR, "check-template-schema-producer-consistency.py")
)
check_absent(
    "check-template-schema-producer-consistency.sh deleted",
    os.path.join(ENFORCEMENT_DIR, "check-template-schema-producer-consistency.sh")
)

print()
print(f"=== Results: {PASS} pass, {FAIL} fail ===")

sys.exit(1 if FAIL > 0 else 0)
