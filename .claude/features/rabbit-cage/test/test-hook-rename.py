#!/usr/bin/env python3
"""Tests rabbit-cage/hooks/ renamed to drop rbt- prefix."""
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
HOOKS_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage/hooks")
SCRIPT_REL = os.path.relpath(os.path.abspath(__file__), REPO_ROOT)

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


print("test-hook-rename.py")

OLD1 = "rbt-refresh.sh"
OLD2 = "rbt-session-init.sh"
OLD3 = "rbt-sync-check.sh"

# t1-3
for t, old in [(1, OLD1), (2, OLD2), (3, OLD3)]:
    if not os.path.isfile(os.path.join(HOOKS_DIR, old)):
        ok(t, f"{old} does not exist in hooks/ (old name gone)")
    else:
        fail_t(t, f"{old} still exists in hooks/ — rename not done")

# t4-6
for t, new in [(4, "refresh.sh"), (5, "session-init.sh"), (6, "sync-check.sh")]:
    if os.path.isfile(os.path.join(HOOKS_DIR, new)):
        ok(t, f"{new} exists in hooks/ (new name present)")
    else:
        fail_t(t, f"{new} does not exist in hooks/ — rename not done")

# t7-9
for t, old, label in [(7, "rbt-refresh\\.sh", OLD1), (8, "rbt-session-init\\.sh", OLD2), (9, "rbt-sync-check\\.sh", OLD3)]:
    res = subprocess.run(
        ["git", "-C", REPO_ROOT, "grep", "-l", old, "--", ":!archive/", f":!{SCRIPT_REL}"],
        capture_output=True, text=True,
    )
    refs = res.stdout.strip()
    if not refs:
        ok(t, f"no tracked file (outside archive/) references {label}")
    else:
        fail_t(t, f"tracked files still reference {label}: {refs.replace(chr(10), ' ')}")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
