#!/usr/bin/env python3
# test-POLICY-1-no-stale-imports.py — assert no stale @-imports in any CLAUDE.md.
# Verifies policy spec invariant 2: workflow-rules.md does not exist, so no
# CLAUDE.md may @-import it. Also verifies test-imports-resolve.py uses a
# regex that matches the actual @.claude/... import format (not @./..).
#
# Version: 1.0.0
# Owner: rabbit-workflow team (policy)
# Deprecation criterion: when Claude Code enforces @-import resolution natively.
import os
import re
import subprocess
import sys

RABBIT_ROOT = os.environ.get("RABBIT_ROOT")
if not RABBIT_ROOT:
    result = subprocess.run(
        ["git", "-C", os.path.dirname(__file__), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    RABBIT_ROOT = result.stdout.strip()

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   {msg}")
    PASS += 1


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL += 1


# t1: CLAUDE.md at repo root does NOT @-import workflow-rules.md
CLAUDE_MD = os.path.join(RABBIT_ROOT, "CLAUDE.md")
if os.path.isfile(CLAUDE_MD):
    with open(CLAUDE_MD) as f:
        claude_content = f.read()
    if "@.claude/features/policy/workflow-rules.md" in claude_content:
        ko("t1: CLAUDE.md @-imports workflow-rules.md (stale reference — file does not exist)")
    else:
        ok("t1: CLAUDE.md does not @-import workflow-rules.md")
else:
    ko("t1: CLAUDE.md not found at repo root")

# t2: test-imports-resolve.py must detect @-imports in CLAUDE.md (i.e. correct regex).
# The actual CLAUDE.md imports are '@.claude/...' format (no dot-slash between @ and path).
# If the regex '^@\./...' is used, 0 imports are found (regex bug).
IMPORTS_TEST = os.path.join(FEATURE_DIR, "test", "test-imports-resolve.py")
if os.path.isfile(IMPORTS_TEST):
    proc = subprocess.run(
        [sys.executable, IMPORTS_TEST],
        capture_output=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    imports_output = proc.stdout
    imports_total = len(re.findall(r'^  (ok|FAIL)', imports_output, re.MULTILINE))
    if imports_total == 0:
        ko("t2: test-imports-resolve.py found 0 @-imports — regex does not match '@.claude/...' format")
    else:
        ok(f"t2: test-imports-resolve.py found {imports_total} @-import(s) — regex works")
else:
    ko("t2: test-imports-resolve.py not found")

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
