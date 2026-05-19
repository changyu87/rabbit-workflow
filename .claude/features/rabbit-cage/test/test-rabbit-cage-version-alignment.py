#!/usr/bin/env python3
"""
RABBIT-CAGE-BUG-91: feature.json, spec.md, and contract.md versions must align.

Three-way version alignment is required so that rabbit-cage's metadata never
drifts between manifests. Per spec-rules.md §3, the version lives in
feature.json; spec.md and contract.md carry the same version in their YAML
frontmatter.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature.json/spec.md/contract.md versions are
    enforced to align by a shared validator across all features.
"""

import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FAIL = 0


def ok(msg):
    print(f"  ok   {msg}")


def ko(msg):
    global FAIL
    print(f"  FAIL {msg}")
    FAIL = 1


def header_version(text):
    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)", text, re.MULTILINE)
    return m.group(1) if m else None


feature_json_path = os.path.join(FEATURE_DIR, "feature.json")
spec_path = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
contract_path = os.path.join(FEATURE_DIR, "docs", "spec", "contract.md")

with open(feature_json_path) as f:
    feature_json = json.load(f)
feature_v = feature_json.get("version")

with open(spec_path) as f:
    spec_v = header_version(f.read())

with open(contract_path) as f:
    contract_v = header_version(f.read())

if feature_v and spec_v and contract_v and feature_v == spec_v == contract_v:
    ok(f"RABBIT-CAGE-BUG-91: feature.json, spec.md, contract.md aligned at {feature_v}")
else:
    ko(
        f"RABBIT-CAGE-BUG-91: three-way mismatch — "
        f"feature.json={feature_v}, spec.md={spec_v}, contract.md={contract_v}"
    )

sys.exit(FAIL)
