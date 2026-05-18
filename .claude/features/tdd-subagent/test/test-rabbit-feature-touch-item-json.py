#!/usr/bin/env python3
# E2E test for Inv 30 (BUG-37): rabbit-feature-touch SKILL.md B/B mode MUST
# read item JSON from `<item-dir>/item.json`, not `<item-dir>/bug.json`.
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
REPO_ROOT = os.path.abspath(os.path.join(FEATURE_DIR, '..', '..', '..'))

SKILL_SRC = os.path.join(FEATURE_DIR, 'skills', 'rabbit-feature-touch', 'SKILL.md')
SKILL_BUILT = os.path.join(REPO_ROOT, '.claude', 'skills', 'rabbit-feature-touch', 'SKILL.md')

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


def check_skill(path, label):
    if not os.path.isfile(path):
        ko(f"{label}: not found at {path}")
        return
    with open(path) as f:
        src = f.read()
    # B/B mode must extract `related_feature` from `item.json`. We accept any
    # tool (jq syntax `'.related_feature'` OR Python `'related_feature'`),
    # since jq is no longer a declared dependency of this feature (BUG-36).
    extracts_related = (
        "'.related_feature'" in src
        or "'related_feature'" in src
        or '"related_feature"' in src
    )
    if extracts_related and "item.json" in src:
        ok(f"{label}: extracts `related_feature` from item.json")
    else:
        ko(f"{label}: missing related_feature extraction from item.json")
    # B/B mode must NOT reference legacy bug.json path
    if "bug.json" in src:
        ko(f"{label}: stale `bug.json` reference still present")
    else:
        ok(f"{label}: no stale `bug.json` reference")


print(f"checking source SKILL.md: {SKILL_SRC}")
check_skill(SKILL_SRC, 'source')
print(f"checking built SKILL.md: {SKILL_BUILT}")
check_skill(SKILL_BUILT, 'built')

print()
print(f"summary: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
