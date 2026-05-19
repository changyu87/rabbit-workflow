#!/usr/bin/env python3
# test-build-contract-absorbed-skill-sources.py — verify that
# build-contract.json's copy-file entry for the rabbit-feature-scope
# SKILL.md sources from its absorbed location under the rabbit-feature
# feature (the canonical post-absorption source), not the legacy
# rabbit-feature-scope feature directory.
#
# t1: build-contract.json's copy-file entry for
#     skills/rabbit-feature-scope/SKILL.md sources
#     .claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md
# t2: destination for that entry remains
#     .claude/skills/rabbit-feature-scope/SKILL.md (unchanged)
# t3: the source file actually exists on disk

import os
import sys
import json

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
REPO_ROOT = os.path.normpath(os.path.join(FEATURE_DIR, "..", "..", ".."))
CONTRACT = os.path.join(FEATURE_DIR, "build-contract.json")

ENTRY_NAME = "skills/rabbit-feature-scope/SKILL.md"
EXPECTED_SOURCE = (
    ".claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md"
)
EXPECTED_DESTINATION = ".claude/skills/rabbit-feature-scope/SKILL.md"

passed = 0
failed = 0


def ok(n, msg):
    global passed
    print(f"  PASS t{n}: {msg}")
    passed += 1


def fail_t(n, msg):
    global failed
    print(f"  FAIL t{n}: {msg}")
    failed += 1


print("test-build-contract-absorbed-skill-sources.py")

with open(CONTRACT) as f:
    contract_data = json.load(f)

by_name = {t.get("name"): t for t in contract_data.get("targets", [])}
entry = by_name.get(ENTRY_NAME)

# t1: source path
if entry is None:
    fail_t(1, f"no entry named {ENTRY_NAME} in build-contract.json")
elif entry.get("source") != EXPECTED_SOURCE:
    fail_t(
        1,
        f"{ENTRY_NAME}: source is {entry.get('source')!r}, "
        f"expected {EXPECTED_SOURCE!r}",
    )
else:
    ok(1, f"{ENTRY_NAME} sources {EXPECTED_SOURCE}")

# t2: destination unchanged
if entry is None:
    fail_t(2, f"no entry named {ENTRY_NAME}")
elif entry.get("destination") != EXPECTED_DESTINATION:
    fail_t(
        2,
        f"{ENTRY_NAME}: destination is {entry.get('destination')!r}, "
        f"expected {EXPECTED_DESTINATION!r}",
    )
else:
    ok(2, f"{ENTRY_NAME} destination is {EXPECTED_DESTINATION}")

# t3: the absorbed source path actually exists on disk
source_abs = os.path.join(REPO_ROOT, EXPECTED_SOURCE)
if not os.path.isfile(source_abs):
    fail_t(3, f"expected source file does not exist on disk: {source_abs}")
else:
    ok(3, f"source file exists on disk: {EXPECTED_SOURCE}")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
