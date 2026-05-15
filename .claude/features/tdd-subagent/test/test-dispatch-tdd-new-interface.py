#!/usr/bin/env python3
# test-dispatch-tdd-new-interface.py — updated for 9-step --scope/--spec interface.
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR).decode().strip()
SCRIPT = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py')
SPEC = os.path.join(REPO_ROOT, '.claude/features/contract/docs/spec/spec.md')

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


# 1. --bug flag is rejected (removed in new interface)
result = subprocess.run(['python3', SCRIPT, 'contract', 'test', '--bug', '/tmp/fake'],
                        capture_output=True)
if result.returncode != 0:
    ok("--bug flag rejected")
else:
    fail("--bug should be rejected")

# 2. --backlog flag is rejected
result = subprocess.run(['python3', SCRIPT, 'contract', 'test', '--backlog', '/tmp/fake'],
                        capture_output=True)
if result.returncode != 0:
    ok("--backlog flag rejected")
else:
    fail("--backlog should be rejected")

# 3. --linked-item without --item-type is rejected
result = subprocess.run(['python3', SCRIPT, '--scope', 'contract', '--spec', SPEC,
                         '--linked-item', '/tmp/fake'],
                        capture_output=True)
if result.returncode != 0:
    ok("--linked-item without --item-type rejected")
else:
    fail("should reject missing --item-type")

# 4. valid basic invocation emits non-empty prompt
result = subprocess.run(['python3', SCRIPT, '--scope', 'contract', '--spec', SPEC],
                        capture_output=True, text=True)
prompt = result.stdout
if prompt.strip():
    ok("basic invocation emits prompt")
else:
    fail("empty prompt")

# 5. prompt references tdd-report-<feature>.json (feature-named)
if 'tdd-report-contract.json' in prompt:
    ok("prompt references tdd-report-contract.json")
else:
    fail("prompt missing tdd-report-contract.json")

# 6. prompt contains spec_compliance field in schema
if 'spec_compliance' in prompt:
    ok("prompt contains spec_compliance")
else:
    fail("prompt missing spec_compliance")

# 7. prompt contains UNLOCK step (replaces test_gap_analysis from old schema)
if 'UNLOCK' in prompt:
    ok("prompt contains UNLOCK step")
else:
    fail("prompt missing UNLOCK step")

# 8. --linked-item --item-type bug is accepted
result2 = subprocess.run(
    ['python3', SCRIPT, '--scope', 'contract', '--spec', SPEC,
     '--linked-item', '/tmp/fake-bug', '--item-type', 'bug'],
    capture_output=True, text=True
)
prompt2 = result2.stdout
if prompt2.strip():
    ok("--linked-item --item-type bug accepted")
else:
    fail("--linked-item bug rejected")

# 9. prompt contains LOCK step (scope guard)
import re
if re.search(r'LOCK|rabbit-scope-active', prompt, re.IGNORECASE):
    ok("prompt mentions LOCK / scope guard")
else:
    fail("prompt missing LOCK / scope guard instruction")

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
