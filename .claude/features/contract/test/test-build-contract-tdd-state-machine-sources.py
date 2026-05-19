#!/usr/bin/env python3
# test-build-contract-tdd-state-machine-sources.py — verify the three
# tdd-* copy-file entries in build-contract.json point at the
# tdd-state-machine feature (the canonical post-consolidation source),
# not the legacy tdd-subagent feature.
#
# t1: build-contract.json's copy-file entry for tdd-step.py sources
#     .claude/features/tdd-state-machine/scripts/tdd-step.py
# t2: build-contract.json's copy-file entry for tdd-context.py sources
#     .claude/features/tdd-state-machine/scripts/tdd-context.py
# t3: build-contract.json's copy-file entry for tdd-drift-check.py sources
#     .claude/features/tdd-state-machine/scripts/tdd-drift-check.py
# t4: destinations for those three entries remain unchanged
#     (.claude/agents/tdd-subagent/scripts/...)

import os
import sys
import json

FEATURE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CONTRACT = os.path.join(FEATURE_DIR, "build-contract.json")

EXPECTED = {
    "agents/tdd-subagent/scripts/tdd-step.py": {
        "source": ".claude/features/tdd-state-machine/scripts/tdd-step.py",
        "destination": ".claude/agents/tdd-subagent/scripts/tdd-step.py",
    },
    "agents/tdd-subagent/scripts/tdd-context.py": {
        "source": ".claude/features/tdd-state-machine/scripts/tdd-context.py",
        "destination": ".claude/agents/tdd-subagent/scripts/tdd-context.py",
    },
    "agents/tdd-subagent/scripts/tdd-drift-check.py": {
        "source": ".claude/features/tdd-state-machine/scripts/tdd-drift-check.py",
        "destination": ".claude/agents/tdd-subagent/scripts/tdd-drift-check.py",
    },
}

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


print("test-build-contract-tdd-state-machine-sources.py")

with open(CONTRACT) as f:
    contract_data = json.load(f)

by_name = {t.get("name"): t for t in contract_data.get("targets", [])}

# t1-t3: source paths
for i, name in enumerate(
    [
        "agents/tdd-subagent/scripts/tdd-step.py",
        "agents/tdd-subagent/scripts/tdd-context.py",
        "agents/tdd-subagent/scripts/tdd-drift-check.py",
    ],
    start=1,
):
    expected_src = EXPECTED[name]["source"]
    entry = by_name.get(name)
    if entry is None:
        fail_t(i, f"no entry named {name} in build-contract.json")
    elif entry.get("source") != expected_src:
        fail_t(
            i,
            f"{name}: source is {entry.get('source')!r}, expected {expected_src!r}",
        )
    else:
        ok(i, f"{name} sources {expected_src}")

# t4: destinations unchanged
t4_fail = False
for name, exp in EXPECTED.items():
    entry = by_name.get(name)
    if entry is None:
        fail_t(4, f"no entry named {name}")
        t4_fail = True
        continue
    if entry.get("destination") != exp["destination"]:
        fail_t(
            4,
            f"{name}: destination is {entry.get('destination')!r}, expected {exp['destination']!r}",
        )
        t4_fail = True
if not t4_fail:
    ok(4, "destinations for the three tdd-* entries unchanged")

print()
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
