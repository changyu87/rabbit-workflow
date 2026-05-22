#!/usr/bin/env python3
"""test-rabbit-feature-skills-deployment.py — CONTRACT-BUG-41 (bundled deploy).

End-to-end assertions for the bundled deployment of all five
rabbit-feature skills via rabbit-feature/publish.json:

  - rabbit-feature-touch
  - rabbit-feature-scope
  - rabbit-feature-spec
  - rabbit-feature-new   (BUG-41)
  - rabbit-feature-audit (BUG-41)

Each skill MUST have:
  - an entry in rabbit-feature/publish.json with the correct source/destination
  - a SKILL.md source file on disk under .claude/features/rabbit-feature/skills/
  - a deployed copy at .claude/skills/<name>/SKILL.md

Non-interactive. Exits non-zero on failure.
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
RABBIT_FEATURE_DIR = os.path.join(REPO_ROOT, ".claude", "features", "rabbit-feature")
PUBLISH_PATH = os.path.join(RABBIT_FEATURE_DIR, "publish.json")

EXPECTED_SKILLS = [
    "rabbit-feature-touch",
    "rabbit-feature-scope",
    "rabbit-feature-spec",
    "rabbit-feature-new",
    "rabbit-feature-audit",
]

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def ko(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}", file=sys.stderr)
    failed += 1


print("test-rabbit-feature-skills-deployment.py")

with open(PUBLISH_PATH) as f:
    data = json.load(f)

by_name = {t.get("name"): t for t in data.get("targets", [])}

for i, skill in enumerate(EXPECTED_SKILLS, start=1):
    name = f"skills/{skill}/SKILL.md"
    expected_source = f"skills/{skill}/SKILL.md"
    expected_dest = f".claude/skills/{skill}/SKILL.md"

    entry = by_name.get(name)
    if entry is None:
        ko(i, f"no entry named {name} in rabbit-feature/publish.json")
        continue
    if entry.get("source") != expected_source:
        ko(i, f"{name}: source {entry.get('source')!r} != {expected_source!r}")
        continue
    if entry.get("destination") != expected_dest:
        ko(i, f"{name}: destination {entry.get('destination')!r} != {expected_dest!r}")
        continue

    source_abs = os.path.join(RABBIT_FEATURE_DIR, expected_source)
    if not os.path.isfile(source_abs):
        ko(i, f"{name}: source file missing: {source_abs}")
        continue

    dest_abs = os.path.join(REPO_ROOT, expected_dest)
    if not os.path.isfile(dest_abs):
        ko(i, f"{name}: deployed SKILL.md missing at {dest_abs}")
        continue

    ok(i, f"{skill}: source + destination wired and deployed")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
