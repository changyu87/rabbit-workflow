#!/usr/bin/env python3
"""test-docs-layout.py — issue #399 Phase 2b (rabbit-spec flat docs/ move)

End-to-end check of rabbit-spec's canonical flat-docs/ documentation layout.

Phase 2 (#399) relocated the feature's spec directory from docs/spec/ to
specs/. Phase 2b (this test) relocates the doc artifacts again, this time to
the flat docs/ layout shared workflow-wide:

  - docs/spec.md      (was specs/spec.md)
  - docs/contract.md  (was specs/contract.md)
  - docs/CHANGELOG.md  (was root CHANGELOG.md)

The contract feature's coexistence window (resolve_spec_path: docs/ preferred,
specs/ fallback) keeps the move green. This E2E test asserts the
post-migration on-disk shape independent of any single helper script:

  - docs/spec.md exists, is non-empty, carries `feature: rabbit-spec`.
  - docs/contract.md exists, is non-empty, carries `feature: rabbit-spec`.
  - docs/CHANGELOG.md exists and is non-empty.
  - No legacy specs/ directory remains in the feature.
  - No root CHANGELOG.md remains in the feature (moved into docs/).
  - docs/spec.md, docs/contract.md, and feature.json all declare the same
    version (the spec/contract/feature.json version lineage survives the
    move). rabbit-spec hosts multiple skills + an agent, each on its own
    independent version lineage, so SKILL.md/agent versions are NOT folded
    into this equality.
  - The contract resolver (resolve_spec_path) resolves both spec.md and
    contract.md to the flat docs/ location, and validate_feature reports
    no errors for the relocated feature.

Run non-interactively. Exits non-zero on failure.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when the flat docs/ layout is enforced workflow-wide by
a cross-feature harness, making this per-feature on-disk assertion redundant.
"""
import json
import os
import re
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(FEATURE_DIR, "docs")

# Import the contract resolver/validator the way every cross-feature consumer
# does, so this E2E test exercises the live resolution path.
_CONTRACT_LIB = os.path.abspath(
    os.path.join(FEATURE_DIR, "..", "contract", "lib")
)
if _CONTRACT_LIB not in sys.path:
    sys.path.insert(0, _CONTRACT_LIB)
from checks import resolve_spec_path, validate_feature  # noqa: E402


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def read_nonempty(path, label):
    if not os.path.isfile(path):
        fail(f"{label}: missing file: {path}")
    if os.path.getsize(path) == 0:
        fail(f"{label}: empty file: {path}")
    with open(path, encoding="utf-8") as f:
        return f.read()


def header_field(text, field):
    m = re.search(rf"^{field}:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


# Canonical flat docs/ layout present and well-formed.
spec_text = read_nonempty(os.path.join(DOCS_DIR, "spec.md"), "docs/spec.md")
contract_text = read_nonempty(
    os.path.join(DOCS_DIR, "contract.md"), "docs/contract.md"
)
changelog_text = read_nonempty(
    os.path.join(DOCS_DIR, "CHANGELOG.md"), "docs/CHANGELOG.md"
)

if header_field(spec_text, "feature") != "rabbit-spec":
    fail("docs/spec.md frontmatter does not declare `feature: rabbit-spec`")
if header_field(contract_text, "feature") != "rabbit-spec":
    fail("docs/contract.md frontmatter does not declare "
         "`feature: rabbit-spec`")

# Legacy specs/ container fully removed.
if os.path.isdir(os.path.join(FEATURE_DIR, "specs")):
    fail(f"legacy specs/ directory must not exist: "
         f"{os.path.join(FEATURE_DIR, 'specs')}")

# Root CHANGELOG.md fully removed (moved into docs/).
if os.path.isfile(os.path.join(FEATURE_DIR, "CHANGELOG.md")):
    fail(f"root CHANGELOG.md must not exist after move: "
         f"{os.path.join(FEATURE_DIR, 'CHANGELOG.md')}")

# spec/contract/feature.json version lineage survives the move. (SKILL.md and
# agent versions are independent lineages and intentionally excluded.)
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

# The contract resolver finds spec/contract at the flat docs/ location.
for name in ("spec.md", "contract.md"):
    resolved = resolve_spec_path(FEATURE_DIR, name)
    expected = os.path.join(DOCS_DIR, name)
    if os.path.abspath(resolved) != os.path.abspath(expected):
        fail(f"resolve_spec_path({name}) -> {resolved}, expected {expected}")

# validate_feature reports no errors for the relocated feature.
result = validate_feature(FEATURE_DIR)
if not result.passed:
    fail(f"validate_feature reported errors after migration: {result.messages}")

print("All checks passed.")
