#!/usr/bin/env python3
# E2E test for Cycle B re-home of rabbit-feature-touch from tdd-subagent
# to rabbit-feature. Asserts:
#   - tdd-subagent/skills/rabbit-feature-touch/ directory is absent
#   - rabbit-feature/skills/rabbit-feature-touch/SKILL.md exists (new owner)
#   - tdd-subagent contract.md provides.skills is [] (no skill listed)
#   - tdd-subagent spec.md Purpose does not claim to "own" the skill
#   - tdd-subagent feature.json version is >= 2.1.0 and summary mentions
#     the re-home
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../../..'))
TDD_DIR = os.path.join(REPO_ROOT, '.claude/features/tdd-subagent')
RF_DIR = os.path.join(REPO_ROOT, '.claude/features/rabbit-feature')

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


def t1_skill_dir_removed_from_tdd_subagent():
    skill_dir = os.path.join(TDD_DIR, 'skills/rabbit-feature-touch')
    if not os.path.isdir(skill_dir):
        ok(f"t1: {skill_dir} absent (re-homed)")
    else:
        ko(f"t1: {skill_dir} still exists — must be deleted (Cycle B re-home)")


def t2_skill_in_rabbit_feature():
    skill_md = os.path.join(RF_DIR, 'skills/rabbit-feature-touch/SKILL.md')
    if os.path.isfile(skill_md):
        ok(f"t2: {skill_md} exists at new owner")
    else:
        ko(f"t2: {skill_md} missing — rabbit-feature must own the skill source")


def t3_contract_provides_skills_empty():
    contract = os.path.join(TDD_DIR, 'docs/spec/contract.md')
    if not os.path.isfile(contract):
        ko(f"t3: {contract} not found")
        return
    with open(contract) as f:
        content = f.read()
    # Parse the JSON block out of the contract.md
    m = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    if not m:
        ko("t3: no fenced JSON block found in contract.md")
        return
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        ko(f"t3: JSON parse error: {e}")
        return
    skills = data.get('provides', {}).get('skills', None)
    if skills == []:
        ok("t3: contract.md provides.skills is []")
    else:
        ko(f"t3: contract.md provides.skills is not [] — got: {skills}")


def t4_purpose_does_not_claim_ownership():
    spec = os.path.join(TDD_DIR, 'docs/spec/spec.md')
    if not os.path.isfile(spec):
        ko(f"t4: {spec} not found")
        return
    with open(spec) as f:
        content = f.read()
    # Find Purpose section text — assert no "Owns the rabbit-feature-touch ... skill"
    m = re.search(r'## Purpose\s*\n(.*?)(?=\n## )', content, re.DOTALL)
    if not m:
        ko("t4: ## Purpose section not found in spec.md")
        return
    purpose = m.group(1)
    if re.search(r'Owns\s+the\s+`?rabbit-feature-touch`?', purpose):
        ko("t4: Purpose still claims to 'Own' the rabbit-feature-touch skill")
    else:
        ok("t4: Purpose no longer claims to own rabbit-feature-touch")


def t5_feature_json_version_and_summary():
    fj = os.path.join(TDD_DIR, 'feature.json')
    if not os.path.isfile(fj):
        ko(f"t5: {fj} not found")
        return
    with open(fj) as f:
        data = json.load(f)
    version = data.get('version', '')
    # Cycle B bumps to 2.1.0 (minor surface reduction)
    parts = version.split('.')
    if len(parts) >= 2 and parts[0] == '2' and int(parts[1]) >= 1:
        ok(f"t5a: feature.json version {version} >= 2.1.0")
    else:
        ko(f"t5a: feature.json version is {version}; expected >= 2.1.0")
    summary = data.get('summary', '')
    if 'rabbit-feature' in summary and ('rabbit-feature-touch' in summary or 'orchestration' in summary):
        ok("t5b: feature.json summary mentions the re-home (rabbit-feature)")
    else:
        ko(f"t5b: feature.json summary does not mention the re-home: {summary!r}")


print("running Cycle B re-home e2e tests")
t1_skill_dir_removed_from_tdd_subagent()
t2_skill_in_rabbit_feature()
t3_contract_provides_skills_empty()
t4_purpose_does_not_claim_ownership()
t5_feature_json_version_and_summary()
print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
