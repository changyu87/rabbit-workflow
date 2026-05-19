#!/usr/bin/env python3
# test-skill-invocation-and-rabbit-report-path.py
# Tests for:
#   Fix 1 (TDD-STATE-MACHINE-1): SKILL.md Step 1 uses Skill() tool invocation
#   Fix 2 (TDD-STATE-MACHINE-BACKLOG-2): dispatch-tdd-subagent.py writes to .rabbit/ path
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR).decode().strip()
SKILL = os.path.join(REPO_ROOT, '.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md')
DISPATCH = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py')
GITIGNORE = os.path.join(REPO_ROOT, '.gitignore')

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


with open(SKILL) as f:
    skill_content = f.read()

with open(DISPATCH) as f:
    dispatch_content = f.read()

# Fix 1: SKILL.md Step 1 must use Skill() invocation, not direct resolve-scope.sh shell call
if 'Skill("rabbit-feature-scope"' in skill_content:
    ok("SKILL.md Step 1 uses Skill() tool invocation")
else:
    fail("SKILL.md Step 1 missing Skill() tool invocation")

if re.search(r'resolve-scope\.sh', skill_content):
    fail("SKILL.md Step 1 still references resolve-scope.sh shell call")
else:
    ok("SKILL.md Step 1 does not reference resolve-scope.sh")

# Fix 2a: dispatch-tdd-subagent.py must write tdd-report-<feature>.json to .rabbit/ path
SPEC = os.path.join(REPO_ROOT, '.claude/features/contract/docs/spec/spec.md')
result = subprocess.run(
    ['python3', DISPATCH, '--scope', 'contract', '--spec', SPEC],
    capture_output=True, text=True
)
prompt = result.stdout

if re.search(r'\.rabbit/tdd-report-contract\.json', prompt):
    ok("dispatch-tdd-subagent.py prompt references .rabbit/tdd-report-contract.json")
else:
    fail("dispatch-tdd-subagent.py prompt does not reference .rabbit/tdd-report.json")

# Fix 2b: dispatch-tdd-subagent.py must NOT reference bare repo-root tdd-report.json path
if re.search(r'\$\{REPO_ROOT\}/tdd-report\.json|REPO_ROOT\}/tdd-report\.json', prompt):
    fail("dispatch-tdd-subagent.py prompt still references bare repo-root tdd-report.json")
else:
    ok("dispatch-tdd-subagent.py prompt does not reference bare repo-root tdd-report.json")

# Fix 2c: dispatch-tdd-subagent.py must contain mkdir -p for .rabbit/
if 'mkdir' in dispatch_content and '.rabbit' in dispatch_content:
    ok("dispatch-tdd-subagent.py contains mkdir -p for .rabbit/")
else:
    fail("dispatch-tdd-subagent.py missing mkdir -p .rabbit/")

# Fix 2d: .gitignore must list .rabbit/
with open(GITIGNORE) as f:
    gitignore_content = f.read()
if re.search(r'^\.rabbit/', gitignore_content, re.MULTILINE):
    ok(".gitignore contains .rabbit/")
else:
    fail(".gitignore missing .rabbit/")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
