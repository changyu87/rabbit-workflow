#!/usr/bin/env python3
"""Test runner for rabbit-spec feature."""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

fail = 0
for t in sorted(f for f in os.listdir(SCRIPT_DIR) if f.startswith("test-") and f.endswith(".py")):
    print(f"=== {t} ===")
    rc = subprocess.run(["python3", os.path.join(SCRIPT_DIR, t)]).returncode
    if rc != 0:
        fail += 1
    print()

print("ALL PASS" if fail == 0 else f"FAILED: {fail} test file(s)")
sys.exit(0 if fail == 0 else 1)
