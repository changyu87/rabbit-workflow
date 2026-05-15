#!/usr/bin/env python3
"""rabbit-cage structure tests — verifies rabbit-cage directory layout."""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.run(
    ["git", "-C", SCRIPT_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()
CAGE_DIR = os.path.join(REPO_ROOT, ".claude/features/rabbit-cage")

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


print("test-structure.py")

# t1: agents/ does NOT exist
if not os.path.exists(os.path.join(CAGE_DIR, "agents")):
    ok(1, "agents/ does not exist or is not a directory")
else:
    fail_t(1, "agents/ still exists — must be removed from rabbit-cage")

# t2: commands/ exists as a directory
if os.path.isdir(os.path.join(CAGE_DIR, "commands")):
    ok(2, "commands/ exists as directory")
else:
    fail_t(2, "commands/ does not exist or is not a directory")

# t3: hooks/ exists as a directory
if os.path.isdir(os.path.join(CAGE_DIR, "hooks")):
    ok(3, "hooks/ exists as directory")
else:
    fail_t(3, "hooks/ does not exist or is not a directory")

# t4: skills/ does NOT exist in rabbit-cage
if not os.path.isdir(os.path.join(CAGE_DIR, "skills")):
    ok(4, "skills/ does not exist in rabbit-cage (correctly moved to tdd-state-machine)")
else:
    fail_t(4, "skills/ still exists in rabbit-cage — orphan dir should be removed")

# t5: settings.json exists and is valid JSON
settings_path = os.path.join(CAGE_DIR, "settings.json")
try:
    with open(settings_path) as f:
        json.load(f)
    ok(5, "settings.json exists and is valid JSON")
except Exception:
    fail_t(5, "settings.json missing or invalid JSON")

# t6: policy-header.json exists in rabbit-cage
policy_header = os.path.join(SCRIPT_DIR, "..", "policy-header.json")
if os.path.isfile(policy_header):
    ok(6, "policy-header.json exists in rabbit-cage")
else:
    fail_t(6, "policy-header.json does not exist in rabbit-cage")

# t7: README.md exists
if os.path.isfile(os.path.join(CAGE_DIR, "README.md")):
    ok(7, "README.md exists in rabbit-cage")
else:
    fail_t(7, "README.md not found in rabbit-cage")

# t8: install.py exists and is executable
install_py = os.path.join(CAGE_DIR, "install.py")
if os.path.isfile(install_py) and os.access(install_py, os.X_OK):
    ok(8, "install.py exists and is executable")
else:
    fail_t(8, "install.py missing or not executable")

# t9: CLAUDE.md does NOT exist in rabbit-cage
claude_md = os.path.join(SCRIPT_DIR, "..", "CLAUDE.md")
if not os.path.isfile(claude_md):
    ok(9, "CLAUDE.md does not exist in rabbit-cage (replaced by policy-header.json)")
else:
    fail_t(9, "CLAUDE.md still exists in rabbit-cage — should be replaced by policy-header.json")

print()
print(f"Results: {pass_n} passed, {fail_n} failed")
sys.exit(0 if fail_n == 0 else 1)
