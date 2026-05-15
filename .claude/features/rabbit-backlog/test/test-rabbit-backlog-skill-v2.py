#!/usr/bin/env python3
# test-rabbit-backlog-skill-v2.py

import subprocess
import sys
import json
from pathlib import Path

REPO_ROOT = Path(subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"],
    text=True
).strip())
SKILL = REPO_ROOT / ".claude" / "features" / "rabbit-backlog" / "skills" / "rabbit-backlog" / "SKILL.md"
DEPLOYED = REPO_ROOT / ".claude" / "skills" / "rabbit-backlog" / "SKILL.md"

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    print(f"PASS: {label}")
    PASS += 1


def fail(label):
    global FAIL
    print(f"FAIL: {label}")
    FAIL += 1


if not SKILL.is_file():
    print("FAIL: source SKILL.md missing")
    sys.exit(1)

content = SKILL.read_text()

for phrase in [
    "Filing protocol",
    "Working protocol",
    "eval subagent",
    "rabbit-feature-touch",
    "B/B mode",
    "tdd-report.json",
    "filing/RABBIT-BACKLOG",
    "auto-merge",
    "status: success|failed",
    "implemented",
]:
    import re
    if re.search(phrase, content, re.IGNORECASE):
        ok(f"SKILL.md contains: {phrase}")
    else:
        fail(f"SKILL.md missing: {phrase}")

# Check deployed copy matches source
if DEPLOYED.is_file() and SKILL.read_text() == DEPLOYED.read_text():
    ok("deployed copy matches source")
else:
    fail("deployed copy differs from source")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
