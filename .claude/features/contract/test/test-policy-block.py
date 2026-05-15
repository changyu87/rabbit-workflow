#!/usr/bin/env python3
# test-policy-block.py — verify policy-block.py output is correct.

import os
import sys
import subprocess

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(FEATURE_DIR, "scripts/policy-block.py")
FAIL = 0

result = subprocess.run(["python3", SCRIPT], capture_output=True, text=True)
OUTPUT = result.stdout + result.stderr
EXIT_CODE = result.returncode

if EXIT_CODE != 0:
    print(f"FAIL: policy-block.py exited with code {EXIT_CODE}", file=sys.stderr)
    FAIL = 1


def check_contains(label, pattern):
    global FAIL
    if pattern not in OUTPUT:
        print(f"FAIL: output does not contain '{pattern}' (check: {label})", file=sys.stderr)
        FAIL = 1


check_contains("sentinel line", "RABBIT-POLICY-BLOCK-v1")
check_contains("banner", "MANDATORY POLICY")
check_contains("philosophy.md section header", "philosophy.md")
check_contains("coding-rules.md section header", "coding-rules.md")

if FAIL != 0:
    print("test-policy-block: FAIL", file=sys.stderr)
    sys.exit(1)

print("test-policy-block: all checks passed.")
