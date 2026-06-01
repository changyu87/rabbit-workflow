#!/usr/bin/env python3
"""test-rabbit-feature-skills-deployment.py — CONTRACT-BUG-41 (bundled deploy).

End-to-end assertions for the bundled deployment of all five
rabbit-feature skills via rabbit-feature/feature.json `manifest`:

  - rabbit-feature-touch
  - rabbit-feature-scope
  - rabbit-feature-spec
  - rabbit-feature-scaffold   (BUG-41)
  - rabbit-feature-audit (BUG-41)

Each skill MUST have:
  - a publish_skill entry in rabbit-feature/feature.json manifest with
    the correct source
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
FEATURE_JSON_PATH = os.path.join(RABBIT_FEATURE_DIR, "feature.json")

EXPECTED_SKILLS = [
    "rabbit-feature-touch",
    "rabbit-feature-scope",
    "rabbit-feature-scaffold",
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

with open(FEATURE_JSON_PATH) as f:
    data = json.load(f)

manifest = data.get("manifest", [])
by_source = {
    entry.get("args", {}).get("source"): entry
    for entry in manifest
    if entry.get("api") == "publish_skill"
}

for i, skill in enumerate(EXPECTED_SKILLS, start=1):
    expected_source = f"skills/{skill}/SKILL.md"
    expected_dest = f".claude/skills/{skill}/SKILL.md"

    entry = by_source.get(expected_source)
    if entry is None:
        ko(i, f"no publish_skill manifest entry with source {expected_source} in rabbit-feature/feature.json")
        continue

    source_abs = os.path.join(RABBIT_FEATURE_DIR, expected_source)
    if not os.path.isfile(source_abs):
        ko(i, f"{skill}: source file missing: {source_abs}")
        continue

    dest_abs = os.path.join(REPO_ROOT, expected_dest)
    if not os.path.isfile(dest_abs):
        ko(i, f"{skill}: deployed SKILL.md missing at {dest_abs}")
        continue

    ok(i, f"{skill}: manifest entry + source + deployed copy wired")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
