#!/usr/bin/env python3
"""rabbit-file test runner"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

def run_suite(script):
    print(f"=== {script} ===")
    result = subprocess.run([sys.executable, str(SCRIPT_DIR / script)])
    print()
    return result.returncode == 0

def run_pytest_suite(script):
    print(f"=== {script} ===")
    result = subprocess.run([sys.executable, "-m", "pytest", str(SCRIPT_DIR / script), "-v"])
    print()
    return result.returncode == 0

print("rabbit-file test runner")
print()

total_fail = 0
if not run_pytest_suite("test-branch-ops.py"):
    total_fail += 1
if not run_pytest_suite("test-worktree-fresh-checkout.py"):
    total_fail += 1
if not run_pytest_suite("test-concurrent-worktree.py"):
    total_fail += 1
if not run_pytest_suite("test-file-item.py"):
    total_fail += 1
if not run_pytest_suite("test-item-status.py"):
    total_fail += 1
if not run_pytest_suite("test-list-items.py"):
    total_fail += 1
if not run_pytest_suite("test-bug-fixes.py"):
    total_fail += 1
if not run_pytest_suite("test-RABBIT-FILE-BACKLOG-7-per-field-limits.py"):
    total_fail += 1
if not run_pytest_suite("test-RABBIT-FILE-BACKLOG-7-control-char-strip.py"):
    total_fail += 1
if not run_pytest_suite("test-bug-32-chained-workspace-guard.py"):
    total_fail += 1
if not run_pytest_suite("test-bug-11-cleanup-and-coverage.py"):
    total_fail += 1
if not run_suite("test-skill.py"):
    total_fail += 1
if not run_suite("test-metadata.py"):
    total_fail += 1

if total_fail == 0:
    print("ALL SUITES PASSED")
    sys.exit(0)
else:
    print(f"FAILED: {total_fail} suite(s) had failures")
    sys.exit(1)
