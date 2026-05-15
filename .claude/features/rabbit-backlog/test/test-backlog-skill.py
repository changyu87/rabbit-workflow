#!/usr/bin/env python3
# test-backlog-skill.py
# t1: skills/rabbit-backlog/SKILL.md exists
# t2: SKILL.md has name and description frontmatter fields
# t3: feature.json surface.skills contains "rabbit-backlog"
# t4: SKILL.md has a list-backlog.py section header
# t5: SKILL.md Scripts Reference table documents list-backlog.py flags (--status, --feature, --text)
# t6: SKILL.md has a Scripts Reference table with file-backlog-item.py and backlog-item-status.py
# t7: SKILL.md has Status Lifecycle and PR Tiers sections

import subprocess
import sys
import json
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = FEATURE_DIR / "skills" / "rabbit-backlog" / "SKILL.md"

passed = 0
failed = 0


def ok(n, label):
    global passed
    print(f"  PASS t{n}: {label}")
    passed += 1


def fail_t(n, label):
    global failed
    print(f"  FAIL t{n}: {label}")
    failed += 1


print("test-backlog-skill.py")

# t1: skills/rabbit-backlog/SKILL.md exists
T1_LABEL = "t1: skills/rabbit-backlog/SKILL.md exists"
if SKILL_MD.is_file():
    ok(1, T1_LABEL)
else:
    fail_t(1, T1_LABEL)

# t2: SKILL.md has name and description frontmatter
T2_LABEL = "t2: SKILL.md has name and description frontmatter"
if SKILL_MD.is_file():
    content = SKILL_MD.read_text()
    if "name:" in content and "description:" in content:
        ok(2, T2_LABEL)
    else:
        fail_t(2, T2_LABEL)
else:
    fail_t(2, T2_LABEL)

# t3: feature.json surface.skills is [] (skills managed via build-contract.json)
T3_LABEL = "t3: feature.json surface.skills is [] (skills managed via build-contract.json)"
FJ = FEATURE_DIR / "feature.json"
try:
    d = json.loads(FJ.read_text())
    skills = d.get("surface", {}).get("skills", None)
    assert isinstance(skills, list) and len(skills) == 0, f"expected [], got {skills!r}"
    ok(3, T3_LABEL)
except Exception:
    fail_t(3, T3_LABEL)

# t4: SKILL.md has a list-backlog.py section header
T4_LABEL = "t4: SKILL.md has a list-backlog.py section header"
if SKILL_MD.is_file() and "list-backlog.py" in SKILL_MD.read_text():
    ok(4, T4_LABEL)
else:
    fail_t(4, T4_LABEL)

# t5: SKILL.md Scripts Reference table documents list-backlog.py flags (--status, --feature, --text)
T5_LABEL = "t5: SKILL.md Scripts Reference table documents list-backlog.py flags (--status, --feature, --text)"
if SKILL_MD.is_file():
    content = SKILL_MD.read_text()
    if "--status" in content and "--feature" in content and "--text" in content:
        ok(5, T5_LABEL)
    else:
        fail_t(5, T5_LABEL)
else:
    fail_t(5, T5_LABEL)

# t6: SKILL.md has a Scripts Reference table with file-backlog-item.py and backlog-item-status.py
T6_LABEL = "t6: SKILL.md has a Scripts Reference table with file-backlog-item.py and backlog-item-status.py"
if SKILL_MD.is_file():
    content = SKILL_MD.read_text()
    if "Scripts Reference" in content and "file-backlog-item.py" in content and "backlog-item-status.py" in content:
        ok(6, T6_LABEL)
    else:
        fail_t(6, T6_LABEL)
else:
    fail_t(6, T6_LABEL)

# t7: SKILL.md has Status Lifecycle and PR Tiers sections
T7_LABEL = "t7: SKILL.md has Status Lifecycle and PR Tiers sections"
if SKILL_MD.is_file():
    content = SKILL_MD.read_text()
    if "Status Lifecycle" in content and "PR Tiers" in content:
        ok(7, T7_LABEL)
    else:
        fail_t(7, T7_LABEL)
else:
    fail_t(7, T7_LABEL)

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
