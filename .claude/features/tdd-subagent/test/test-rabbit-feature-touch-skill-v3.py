#!/usr/bin/env python3
# test-rabbit-feature-touch-skill-v3.py
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR).decode().strip()
SKILL = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/skills/rabbit-feature-touch/SKILL.md')
DEPLOYED = os.path.join(REPO_ROOT, '.claude/skills/rabbit-feature-touch/SKILL.md')

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

with open(SKILL) as f:
    skill_content = f.read()

phrases = [
    "B/B mode",
    r"feat/<feature-name>",
    r"fix/<bug-id>",
    r"task/<backlog-id>",
    "tdd-report.json",
    "rabbit-feature-scope",
    "Unified Five-Step",
    r"primary.*first",
    r"status: success|failed",
]

for phrase in phrases:
    if re.search(phrase, skill_content, re.IGNORECASE):
        ok(f"SKILL.md contains: {phrase}")
    else:
        fail(f"SKILL.md missing: {phrase}")

if os.path.isfile(DEPLOYED):
    with open(DEPLOYED) as f:
        deployed_content = f.read()
    if skill_content == deployed_content:
        ok("deployed copy matches source")
    else:
        fail("deployed copy differs from source")
else:
    fail(f"deployed copy not found at {DEPLOYED}")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
