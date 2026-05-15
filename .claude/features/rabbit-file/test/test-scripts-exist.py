#!/usr/bin/env python3
"""Test that required scripts exist in the scripts directory."""
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).parent.parent
SCRIPTS = FEATURE_DIR / "scripts"

pass_ = 0
fail = 0

def assert_pass(msg):
    global pass_
    print(f"PASS: {msg}")
    pass_ += 1

def assert_fail(msg, reason):
    global fail
    print(f"FAIL: {msg} — {reason}")
    fail += 1

for s in ["branch_ops.py", "file-item.py", "item-status.py", "list-items.py"]:
    path = SCRIPTS / s
    if path.is_file():
        assert_pass(f"{s} exists")
    else:
        assert_fail(f"{s} exists", f"missing at {path}")

print()
print(f"Results: {pass_} passed, {fail} failed")
sys.exit(0 if fail == 0 else 1)
