#!/usr/bin/env python3
"""rabbit-cage obsolete artifact removal tests."""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
FEATURES = os.path.join(REPO_ROOT, ".claude/features")

pass_n = 0
fail_n = 0


def ok(t, msg):
    global pass_n
    print(f"  PASS t{t}: {msg}")
    pass_n += 1


def fail_t(t, msg):
    global fail_n
    print(f"  FAIL t{t}: {msg}")
    fail_n += 1


print("test-obsolete-removed.py")

checks = [
    (1, "root-management", os.path.join(FEATURES, "root-management")),
    (2, "policy-enforcement", os.path.join(FEATURES, "policy-enforcement")),
    (3, "subagent-policy-injection", os.path.join(FEATURES, "subagent-policy-injection")),
    (4, "breeder", os.path.join(FEATURES, "breeder")),
    (5, "vet", os.path.join(FEATURES, "vet")),
    (6, "rabbit-breeder.md", os.path.join(REPO_ROOT, ".claude/agents/rabbit-breeder.md")),
    (7, "rabbit-vet.md", os.path.join(REPO_ROOT, ".claude/agents/rabbit-vet.md")),
]

for t, name, path in checks:
    if not os.path.exists(path):
        ok(t, f"{name} removed")
    else:
        fail_t(t, f"{name} still exists at {path}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
