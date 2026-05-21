#!/usr/bin/env python3
"""test-build-contract-post-consolidation.py — CONTRACT-BACKLOG-25

Data-driven consolidation of three legacy single-entry tests:

  - test-build-contract-tdd-state-machine-sources.py (Inv 35 (b))
  - test-build-contract-absorbed-skill-sources.py
  - test-rabbit-feature-spec-deployment.py            (Inv 35 (a))

Each legacy test asserted name/source/destination for one (or three)
build-contract.json copy-file entries. This test loops over a fixture
list and asserts each entry has the expected source and destination,
plus that the source file exists on disk.

Also enforces the negative assertions originally in
test-rabbit-feature-spec-deployment.py:

  - the legacy entry name 'skills/rabbit-spec/SKILL.md' is absent
    from build-contract.json (Inv 35 (a))
  - the orphan deployed dir '.claude/skills/rabbit-spec/' does not
    exist on disk (Inv 35 (a))
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
    capture_output=True,
    text=True,
)
REPO_ROOT = result.stdout.strip() if result.returncode == 0 else ""
CONTRACT = os.path.join(REPO_ROOT, ".claude/features/contract/build-contract.json")

# Expected post-consolidation copy-file entries.
# Each fixture: (name, source, destination)
EXPECTED_ENTRIES = [
    (
        "agents/tdd-subagent/scripts/tdd-step.py",
        ".claude/features/tdd-state-machine/scripts/tdd-step.py",
        ".claude/agents/tdd-subagent/scripts/tdd-step.py",
    ),
    # tdd-context.py and tdd-drift-check.py retired in
    # TDD-STATE-MACHINE-BACKLOG-7 (zero runtime callers — deleted per
    # Bounded Scope + Designed Deprecation). Their build-contract.json
    # entries and deployed copies were removed in the same cycle.
    (
        "skills/rabbit-feature-scope/SKILL.md",
        ".claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md",
        ".claude/skills/rabbit-feature-scope/SKILL.md",
    ),
    (
        "skills/rabbit-feature-spec/SKILL.md",
        ".claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md",
        ".claude/skills/rabbit-feature-spec/SKILL.md",
    ),
]

# Negative assertions: names / paths that MUST be absent post-consolidation.
LEGACY_ABSENT_NAME = "skills/rabbit-spec/SKILL.md"
LEGACY_ABSENT_DEPLOYED_DIR = os.path.join(REPO_ROOT, ".claude/skills/rabbit-spec")

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


print("test-build-contract-post-consolidation.py")

with open(CONTRACT) as f:
    data = json.load(f)

by_name = {t.get("name"): t for t in data.get("targets", [])}

# t1..tN: one fixture per expected entry; each fixture asserts presence,
# source, destination, and source-on-disk.
for i, (name, expected_source, expected_dest) in enumerate(
    EXPECTED_ENTRIES, start=1
):
    entry = by_name.get(name)
    if entry is None:
        ko(i, f"no entry named {name} in build-contract.json")
        continue
    if entry.get("source") != expected_source:
        ko(
            i,
            f"{name}: source is {entry.get('source')!r}, "
            f"expected {expected_source!r}",
        )
        continue
    if entry.get("destination") != expected_dest:
        ko(
            i,
            f"{name}: destination is {entry.get('destination')!r}, "
            f"expected {expected_dest!r}",
        )
        continue
    source_abs = os.path.join(REPO_ROOT, expected_source)
    if not os.path.isfile(source_abs):
        ko(i, f"{name}: source file does not exist on disk: {source_abs}")
        continue
    ok(i, f"{name}: source/destination correct and source exists")

# Negative t: legacy entry name absent.
neg1 = len(EXPECTED_ENTRIES) + 1
if LEGACY_ABSENT_NAME in by_name:
    ko(neg1, f"legacy entry {LEGACY_ABSENT_NAME} still present in build-contract.json")
else:
    ok(neg1, f"legacy entry {LEGACY_ABSENT_NAME} absent")

# Negative t: orphan deployed dir absent.
neg2 = neg1 + 1
if os.path.exists(LEGACY_ABSENT_DEPLOYED_DIR):
    ko(neg2, f"orphan deployed dir still exists: {LEGACY_ABSENT_DEPLOYED_DIR}")
else:
    ok(neg2, "orphan deployed dir .claude/skills/rabbit-spec/ absent")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
