#!/usr/bin/env python3
# Tests for rabbit-feature-touch skill ownership migration from rabbit-cage to tdd-state-machine.
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../../..'))
FEATURES_DIR = os.path.join(REPO_ROOT, '.claude/features')

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


# t1: tdd-state-machine/skills/rabbit-feature-touch/ directory exists
def t1():
    skill_dir = os.path.join(FEATURES_DIR, 'tdd-state-machine/skills/rabbit-feature-touch')
    if os.path.isdir(skill_dir):
        ok(f"t1: {skill_dir} exists")
    else:
        ko(f"t1: {skill_dir} does not exist")


# t2: tdd-state-machine/skills/rabbit-feature-touch/SKILL.md exists
def t2():
    skill_md = os.path.join(FEATURES_DIR, 'tdd-state-machine/skills/rabbit-feature-touch/SKILL.md')
    if os.path.isfile(skill_md):
        ok(f"t2: {skill_md} exists")
    else:
        ko(f"t2: {skill_md} does not exist")


# t3: tdd-state-machine/feature.json surface.skills is [] (retired)
def t3():
    feature_json = os.path.join(FEATURES_DIR, 'tdd-state-machine/feature.json')
    if not os.path.isfile(feature_json):
        ko(f"t3: {feature_json} not found")
        return
    with open(feature_json) as f:
        data = json.load(f)
    skills = data.get('surface', {}).get('skills', [])
    if skills == []:
        ok("t3: tdd-state-machine/feature.json surface.skills is [] (retired)")
    else:
        ko(f"t3: tdd-state-machine/feature.json surface.skills is not [] — got: {skills} (must be empty per invariant 9)")


# t4: rabbit-cage/feature.json surface.skills does NOT include "rabbit-feature-touch"
def t4():
    feature_json = os.path.join(FEATURES_DIR, 'rabbit-cage/feature.json')
    if not os.path.isfile(feature_json):
        ko(f"t4: {feature_json} not found")
        return
    with open(feature_json) as f:
        data = json.load(f)
    skills = data.get('surface', {}).get('skills', [])
    if 'rabbit-feature-touch' not in skills:
        ok("t4: rabbit-cage/feature.json surface.skills does NOT include rabbit-feature-touch")
    else:
        ko(f"t4: rabbit-cage/feature.json surface.skills still includes rabbit-feature-touch (found={skills.count('rabbit-feature-touch')})")


# t5: if .claude/skills/rabbit-feature-touch/SKILL.md exists, its content matches
#     tdd-state-machine/skills/rabbit-feature-touch/SKILL.md
def t5():
    deployed = os.path.join(REPO_ROOT, '.claude/skills/rabbit-feature-touch/SKILL.md')
    source = os.path.join(FEATURES_DIR, 'tdd-state-machine/skills/rabbit-feature-touch/SKILL.md')

    if not os.path.isfile(deployed):
        ok('t5: .claude/skills/rabbit-feature-touch/SKILL.md absent — nothing to compare (skip)')
        return
    if not os.path.isfile(source):
        ko(f"t5: source {source} missing; cannot verify deployed SKILL.md was sourced from tdd-state-machine")
        return
    with open(source) as f:
        src_content = f.read()
    with open(deployed) as f:
        dep_content = f.read()
    if src_content == dep_content:
        ok('t5: deployed SKILL.md matches tdd-state-machine source')
    else:
        ko('t5: deployed SKILL.md differs from tdd-state-machine source (content mismatch)')


# t6: tdd-state-machine SKILL.md does NOT contain "## When to Use" section
def t6():
    skill_md = os.path.join(FEATURES_DIR, 'tdd-state-machine/skills/rabbit-feature-touch/SKILL.md')
    if not os.path.isfile(skill_md):
        ko(f"t6: {skill_md} not found")
        return
    with open(skill_md) as f:
        content = f.read()
    count = content.count('## When to Use')
    if count == 0:
        ok("t6: SKILL.md does not contain '## When to Use' (no duplication)")
    else:
        ko(f"t6: SKILL.md still contains '## When to Use' ({count} occurrence(s))")


print("running rabbit-feature-touch skill ownership tests")
t1(); t2(); t3(); t4(); t5(); t6()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
