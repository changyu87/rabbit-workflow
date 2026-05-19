#!/usr/bin/env python3
"""test-rabbit-feature-spec-deployment.py — verify build-contract.json
deploys the rabbit-feature-spec SKILL (post-rename from rabbit-spec).

End-to-end regression for the rabbit-spec -> rabbit-feature-spec rename:

  t1: build-contract.json has a copy-file entry whose name is
      'skills/rabbit-feature-spec/SKILL.md'.
  t2: That entry's source is
      '.claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md'.
  t3: That entry's destination is
      '.claude/skills/rabbit-feature-spec/SKILL.md'.
  t4: The source file exists on disk.
  t5: build-contract.json no longer carries an entry whose name is
      'skills/rabbit-spec/SKILL.md' (the old entry was renamed).
  t6: The orphaned deployed dir '.claude/skills/rabbit-spec/' no longer
      exists on disk.
"""

import os
import sys
import json
import subprocess

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
result = subprocess.run(
    ["git", "-C", FEATURE_DIR, "rev-parse", "--show-toplevel"],
    capture_output=True, text=True,
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""

CONTRACT = os.path.join(REPO_ROOT, ".claude/features/contract/build-contract.json")

NEW_NAME = "skills/rabbit-feature-spec/SKILL.md"
NEW_SOURCE = ".claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md"
NEW_DEST = ".claude/skills/rabbit-feature-spec/SKILL.md"
OLD_NAME = "skills/rabbit-spec/SKILL.md"
OLD_DEPLOYED_DIR = os.path.join(REPO_ROOT, ".claude/skills/rabbit-spec")

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def ko(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}")
    failed += 1


print("test-rabbit-feature-spec-deployment.py")

with open(CONTRACT) as f:
    data = json.load(f)

by_name = {t.get("name"): t for t in data.get("targets", [])}
new_entry = by_name.get(NEW_NAME)

# t1: new entry present
if new_entry is None:
    ko(1, f"no entry named {NEW_NAME} in build-contract.json")
else:
    ok(1, f"entry {NEW_NAME} present in build-contract.json")

# t2: source path
if new_entry is None:
    ko(2, "skipped: no entry")
elif new_entry.get("source") != NEW_SOURCE:
    ko(2, f"source is {new_entry.get('source')!r}, expected {NEW_SOURCE!r}")
else:
    ok(2, f"source is {NEW_SOURCE}")

# t3: destination
if new_entry is None:
    ko(3, "skipped: no entry")
elif new_entry.get("destination") != NEW_DEST:
    ko(3, f"destination is {new_entry.get('destination')!r}, expected {NEW_DEST!r}")
else:
    ok(3, f"destination is {NEW_DEST}")

# t4: source exists on disk
source_abs = os.path.join(REPO_ROOT, NEW_SOURCE)
if not os.path.isfile(source_abs):
    ko(4, f"source file does not exist on disk: {source_abs}")
else:
    ok(4, f"source file exists on disk: {NEW_SOURCE}")

# t5: old entry removed
if OLD_NAME in by_name:
    ko(5, f"legacy entry {OLD_NAME} still present in build-contract.json")
else:
    ok(5, f"legacy entry {OLD_NAME} absent")

# t6: orphan deployed dir removed
if os.path.exists(OLD_DEPLOYED_DIR):
    ko(6, f"orphan deployed dir still exists: {OLD_DEPLOYED_DIR}")
else:
    ok(6, "orphan deployed dir .claude/skills/rabbit-spec/ absent")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
