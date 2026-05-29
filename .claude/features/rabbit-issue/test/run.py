#!/usr/bin/env python3
"""rabbit-issue test runner.

Phase 1: registers only the static-check suites that exist now.
Subsequent phases (runtime scripts, migrate.py) will add their suites
to the SUITES list as those phases land.
"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_suite(script: str) -> bool:
    print(f"=== {script} ===")
    result = subprocess.run([sys.executable, str(SCRIPT_DIR / script)])
    print()
    return result.returncode == 0


# Phase 1: static-check suites only.
SUITES = (
    "test-spec-presence.py",
    "test-prompts-declared.py",
    "test-manifest-shape.py",
)

print("rabbit-issue test runner")
print()

total_fail = 0
for script in SUITES:
    if not run_suite(script):
        total_fail += 1

if total_fail == 0:
    print("ALL SUITES PASSED")
    sys.exit(0)
else:
    print(f"FAILED: {total_fail} suite(s) had failures")
    sys.exit(1)
