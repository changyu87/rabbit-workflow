#!/usr/bin/env python3
# Tests that SKILL.md contains the confirm-token bypass path section.
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../../..'))
SKILL_MD = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent/skills/rabbit-feature-touch/SKILL.md')

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


def read_skill():
    if not os.path.isfile(SKILL_MD):
        return None
    with open(SKILL_MD) as f:
        return f.read()


# t1: SKILL.md contains the "Override Path" section header
def t1():
    content = read_skill()
    if content is None:
        ko(f"t1: {SKILL_MD} not found")
        return
    if '## Override Path' in content:
        ok("t1: SKILL.md contains '## Override Path' section header")
    else:
        ko("t1: SKILL.md missing '## Override Path' section header")


# t2: SKILL.md mentions the confirm token presentation step
def t2():
    content = read_skill()
    if content is None:
        ko(f"t2: {SKILL_MD} not found")
        return
    if 'confirm token' in content:
        ok("t2: SKILL.md mentions 'confirm token'")
    else:
        ko("t2: SKILL.md missing 'confirm token' reference")


# t3: SKILL.md documents the one-time override choice
def t3():
    content = read_skill()
    if content is None:
        ko(f"t3: {SKILL_MD} not found")
        return
    if 'one-time' in content:
        ok("t3: SKILL.md documents 'one-time' override choice")
    else:
        ko("t3: SKILL.md missing 'one-time' override choice")


# t4: SKILL.md documents the session override choice
def t4():
    content = read_skill()
    if content is None:
        ko(f"t4: {SKILL_MD} not found")
        return
    if 'session' in content:
        ok("t4: SKILL.md documents 'session' override choice")
    else:
        ko("t4: SKILL.md missing 'session' override choice")


# t5: SKILL.md documents .rabbit-scope-override file writing
def t5():
    content = read_skill()
    if content is None:
        ko(f"t5: {SKILL_MD} not found")
        return
    if '.rabbit-scope-override' in content:
        ok("t5: SKILL.md references '.rabbit-scope-override' file")
    else:
        ko("t5: SKILL.md missing '.rabbit-scope-override' reference")


# t6: SKILL.md states that user approval IS the authorization
def t6():
    content = read_skill()
    if content is None:
        ko(f"t6: {SKILL_MD} not found")
        return
    if 'approval' in content:
        ok("t6: SKILL.md mentions user approval as authorization")
    else:
        ko("t6: SKILL.md missing user approval authorization statement")


print("running confirm-token bypass section tests")
t1(); t2(); t3(); t4(); t5(); t6()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
