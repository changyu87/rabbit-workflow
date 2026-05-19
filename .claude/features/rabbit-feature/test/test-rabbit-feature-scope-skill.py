#!/usr/bin/env python3
# test-rabbit-feature-scope-skill.py

import subprocess
import sys
from pathlib import Path

repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
skill = Path(repo_root) / ".claude/features/rabbit-feature-scope/skills/rabbit-feature-scope/SKILL.md"
deployed = Path(repo_root) / ".claude/skills/rabbit-feature-scope/SKILL.md"

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    print(f"PASS: {msg}")
    PASS += 1

def fail(msg):
    global FAIL
    print(f"FAIL: {msg}")
    FAIL += 1

if not skill.is_file():
    print("FAIL: source SKILL.md missing")
    sys.exit(1)
if not deployed.is_file():
    print("FAIL: deployed SKILL.md missing")
    sys.exit(1)

skill_content = skill.read_text()

for phrase in [
    "resolve-scope.py",
    '"features"',
    '"rationale"',
    "default model",
    "single line",
    "find-feature.py",
]:
    if phrase in skill_content:
        ok(f"source SKILL.md contains: {phrase}")
    else:
        fail(f"source SKILL.md missing: {phrase}")

# Deployed copy matches source
if skill.read_text() == deployed.read_text():
    ok("deployed copy matches source")
else:
    fail("deployed copy differs from source")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
