#!/usr/bin/env python3
# test-rabbit-feature-touch-skill-v3.py
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=SCRIPT_DIR).decode().strip()
SKILL = os.path.join(REPO_ROOT, '.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md')
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
    "tdd-report-",
    "rabbit-feature-scope",
    "Unified Seven-Step",
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

def test_rabbit_spec_is_step_3():
    """rabbit-feature-touch must list rabbit-spec as Step 3."""
    skill_path = os.path.join(
        REPO_ROOT, ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
    )
    with open(skill_path) as f:
        content = f.read()
    assert "Step 3" in content and "rabbit-spec" in content, \
        "SKILL.md must list rabbit-spec as Step 3"


def test_seven_steps_total():
    """rabbit-feature-touch must have 7 steps total (spec invariant 13)."""
    skill_path = os.path.join(
        REPO_ROOT, ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
    )
    with open(skill_path) as f:
        content = f.read()
    assert "Step 7" in content, "SKILL.md must have 7 steps total"
    assert "Step 8" not in content, "SKILL.md must not have a Step 8"


def test_dispatch_tdd_subagent_referenced():
    """rabbit-feature-touch must reference dispatch-tdd-subagent.py."""
    skill_path = os.path.join(
        REPO_ROOT, ".claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md"
    )
    with open(skill_path) as f:
        content = f.read()
    assert "dispatch-tdd-subagent" in content, \
        "SKILL.md must reference dispatch-tdd-subagent.py"


# Run function-based tests
for fn_name in ['test_rabbit_spec_is_step_3', 'test_seven_steps_total', 'test_dispatch_tdd_subagent_referenced']:
    fn = locals()[fn_name]
    try:
        fn()
        ok(fn_name)
    except AssertionError as e:
        fail(fn_name + ": " + str(e))

print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
