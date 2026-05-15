#!/usr/bin/env python3
# test-rabbit-bug-skill-v2.py

import os
import re
import subprocess
import sys

r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
REPO_ROOT = r.stdout.strip()

SKILL = os.path.join(REPO_ROOT, ".claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md")
DEPLOYED = os.path.join(REPO_ROOT, ".claude/skills/rabbit-bug/SKILL.md")

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


if not os.path.isfile(SKILL):
    print("FAIL: source SKILL.md missing")
    sys.exit(1)

content = open(SKILL).read()

phrases = [
    "Filing protocol",
    "Working protocol",
    "eval subagent",
    "rabbit-feature-touch",
    "B/B mode",
    "tdd-report.json",
    "filing/RABBIT-BUG",
    "auto-merge",
    "status: success|failed",
    "vet-triage.json",
]

for phrase in phrases:
    if re.search(phrase, content, re.IGNORECASE):
        ok(f"SKILL.md contains: {phrase}")
    else:
        fail(f"SKILL.md missing: {phrase}")

# Check deployed copy matches source
try:
    with open(SKILL) as f:
        src = f.read()
    with open(DEPLOYED) as f:
        dst = f.read()
    if src == dst:
        ok("deployed copy matches source")
    else:
        fail("deployed copy differs from source")
except FileNotFoundError as e:
    fail(f"deployed copy differs from source: {e}")

print("")
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
