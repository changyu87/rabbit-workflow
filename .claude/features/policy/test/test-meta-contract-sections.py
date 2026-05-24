#!/usr/bin/env python3
"""test-meta-contract-sections.py — Verifies Inv 10 (Plan E.* migration).

Asserts that policy/feature.json explicitly declares the three meta-contract
sections (`manifest`, `runtime`, `configuration`) with the exact empty shapes
required for a content-only feature with no deployment surface:

  - manifest: [] (empty list)
  - runtime: {} (empty dict)
  - configuration: [] (empty list)

Traces: Plan E.policy migration / spec Inv 10.

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when the meta-contract sections are validated by a
cross-feature harness (e.g. contract/scripts/validate-meta-contract.py)
that policy's run.py invokes directly, making this per-feature check
redundant.
"""
import json
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")


def fail(msg):
    print(f"FAIL: Inv 10: {msg}", file=sys.stderr)
    sys.exit(1)


with open(FEATURE_JSON) as f:
    data = json.load(f)

if "manifest" not in data:
    fail("feature.json missing top-level key 'manifest'")
if "runtime" not in data:
    fail("feature.json missing top-level key 'runtime'")
if "configuration" not in data:
    fail("feature.json missing top-level key 'configuration'")

if not isinstance(data["manifest"], list):
    fail(f"'manifest' must be a list, got {type(data['manifest']).__name__}")
if len(data["manifest"]) != 0:
    fail(f"'manifest' must be empty (policy has no deployment surface), got {len(data['manifest'])} entries")

if not isinstance(data["runtime"], dict):
    fail(f"'runtime' must be a dict, got {type(data['runtime']).__name__}")
if len(data["runtime"]) != 0:
    fail(f"'runtime' must be empty (policy has no runtime surface), got {len(data['runtime'])} keys")

if not isinstance(data["configuration"], list):
    fail(f"'configuration' must be a list, got {type(data['configuration']).__name__}")
if len(data["configuration"]) != 0:
    fail(f"'configuration' must be empty (policy has no configuration surface), got {len(data['configuration'])} entries")

print("All checks passed.")
