#!/usr/bin/env python3
"""test-spec-layout-migration.py — End-to-end check of the policy feature's
canonical spec-directory layout.

Issue #399 Phase 2 relocates the policy feature's spec from the legacy
`docs/spec/` layout to the canonical `specs/` layout. This E2E test asserts
the post-migration on-disk shape of the feature, independent of any single
helper script:

  - specs/spec.md exists, is non-empty, and carries `feature: policy`
    frontmatter.
  - specs/contract.md exists, is non-empty, and carries `feature: policy`
    frontmatter.
  - No `docs/` directory remains anywhere in the feature (the legacy
    docs/spec/ container is fully removed once its only child migrated).
  - specs/spec.md, specs/contract.md, and feature.json all declare the same
    version (three-way frontmatter/JSON alignment survives the move).

Traces: #399 (Phase 2, policy)

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when issue #399 Phase 3 lands and the canonical
spec-directory layout is enforced workflow-wide by a cross-feature harness,
making this per-feature on-disk assertion redundant.
"""
import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPECS_DIR = os.path.join(FEATURE_DIR, "specs")


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def read_nonempty(path, label):
    if not os.path.isfile(path):
        fail(f"{label}: missing file: {path}")
    if os.path.getsize(path) == 0:
        fail(f"{label}: empty file: {path}")
    with open(path) as f:
        return f.read()


def header_field(text, field):
    m = re.search(rf"^{field}:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


# Canonical specs/ layout present and well-formed.
spec_text = read_nonempty(os.path.join(SPECS_DIR, "spec.md"), "specs/spec.md")
contract_text = read_nonempty(
    os.path.join(SPECS_DIR, "contract.md"), "specs/contract.md"
)

if header_field(spec_text, "feature") != "policy":
    fail("specs/spec.md frontmatter does not declare `feature: policy`")
if header_field(contract_text, "feature") != "policy":
    fail("specs/contract.md frontmatter does not declare `feature: policy`")

# Legacy docs/ container fully removed.
for root, dirs, _files in os.walk(FEATURE_DIR):
    if "docs" in dirs:
        fail(f"legacy docs/ directory must not exist: {os.path.join(root, 'docs')}")

# Three-way version alignment survives the move.
spec_v = header_field(spec_text, "version")
contract_v = header_field(contract_text, "version")
with open(os.path.join(FEATURE_DIR, "feature.json")) as f:
    feature_v = json.load(f).get("version")
if not (spec_v and contract_v and feature_v):
    fail(
        f"missing version: spec={spec_v}, contract={contract_v}, "
        f"feature.json={feature_v}"
    )
if not (spec_v == contract_v == feature_v):
    fail(
        f"version mismatch after migration: spec={spec_v}, "
        f"contract={contract_v}, feature.json={feature_v}"
    )

print("All checks passed.")
