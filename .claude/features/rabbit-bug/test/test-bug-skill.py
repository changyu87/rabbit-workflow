#!/usr/bin/env python3
# test-bug-skill.py
# t1: skills/rabbit-bug/SKILL.md exists
# t2: SKILL.md has name and description frontmatter fields
# t3: feature.json surface.skills contains [] (skills retired from feature.json)

import json
import os
import re
import sys

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_MD = os.path.join(FEATURE_DIR, "skills/rabbit-bug/SKILL.md")

passed = 0
failed = 0


def ok(num, label):
    global passed
    print(f"  PASS t{num}: {label}")
    passed += 1


def fail_t(num, label):
    global failed
    print(f"  FAIL t{num}: {label}")
    failed += 1


print("test-bug-skill.py")

# t1: skills/rabbit-bug/SKILL.md exists
T1_LABEL = "t1: skills/rabbit-bug/SKILL.md exists"
if os.path.isfile(SKILL_MD):
    ok(1, T1_LABEL)
else:
    fail_t(1, T1_LABEL)

# t2: SKILL.md has name and description frontmatter
T2_LABEL = "t2: SKILL.md has name and description frontmatter"
if os.path.isfile(SKILL_MD):
    content = open(SKILL_MD).read()
    if re.search(r'^name:', content, re.MULTILINE) and re.search(r'^description:', content, re.MULTILINE):
        ok(2, T2_LABEL)
    else:
        fail_t(2, T2_LABEL)
else:
    fail_t(2, T2_LABEL)

# t3: feature.json surface.skills is [] (skills retired from feature.json)
T3_LABEL = "t3: feature.json surface.skills is [] (skills retired from feature.json)"
fj = os.path.join(FEATURE_DIR, "feature.json")
try:
    d = json.load(open(fj))
    skills = d.get("surface", {}).get("skills", None)
    assert skills == [], f"not empty: {skills!r}"
    ok(3, T3_LABEL)
except Exception:
    fail_t(3, T3_LABEL)

print("")
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
