#!/usr/bin/env python3
"""test-contract-spec-dir-migrated.py — issue #399 Phase 2b (contract).

End-to-end test that contract's own spec/contract/CHANGELOG docs live under the
flat `docs/` layout and that the legacy `specs/` tree is gone:

  t1  .claude/features/contract/docs/spec.md exists and is non-empty.
  t2  .claude/features/contract/docs/contract.md exists and is non-empty.
  t3  .claude/features/contract/docs/CHANGELOG.md exists and is non-empty.
  t4  .claude/features/contract/specs/ no longer exists.
  t5  .claude/features/contract/CHANGELOG.md (feature-root) no longer exists.
  t6  contract's spec.md is resolved by contract.lib.checks.resolve_spec_path
      to the flat docs/ candidate (proving the resolver returns the flat
      docs/ layout for contract itself).
  t7  contract's CHANGELOG.md is resolved by resolve_changelog_path to docs/.
  t8  contract validates itself via validate_feature at the new location.

Issue #399's coexistence window is fully in place: resolve_spec_path prefers
the flat docs/<name> layout and falls back to specs/<name>. Phase 2b moves
contract's own docs to docs/; this test asserts contract on the flat layout.

Non-interactive. Exits non-zero on any failure.

Version: 2.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when the per-feature docs/ layout is superseded by a
schema-tracked spec store (this test folds into the generic layout checks at
that point).
"""

import importlib.util
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.normpath(os.path.join(TEST_DIR, ".."))
CHECKS_PATH = os.path.join(FEATURE_DIR, "lib", "checks.py")

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def ko(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1
spec_md = os.path.join(FEATURE_DIR, "docs", "spec.md")
if os.path.isfile(spec_md) and os.path.getsize(spec_md) > 0:
    ok("t1", "docs/spec.md exists and is non-empty")
else:
    ko("t1", f"docs/spec.md missing or empty: {spec_md}")

# t2
contract_md = os.path.join(FEATURE_DIR, "docs", "contract.md")
if os.path.isfile(contract_md) and os.path.getsize(contract_md) > 0:
    ok("t2", "docs/contract.md exists and is non-empty")
else:
    ko("t2", f"docs/contract.md missing or empty: {contract_md}")

# t3
changelog_md = os.path.join(FEATURE_DIR, "docs", "CHANGELOG.md")
if os.path.isfile(changelog_md) and os.path.getsize(changelog_md) > 0:
    ok("t3", "docs/CHANGELOG.md exists and is non-empty")
else:
    ko("t3", f"docs/CHANGELOG.md missing or empty: {changelog_md}")

# t4
specs_dir = os.path.join(FEATURE_DIR, "specs")
if not os.path.exists(specs_dir):
    ok("t4", "legacy specs/ tree is gone")
else:
    ko("t4", f"legacy specs/ tree still present: {specs_dir}")

# t5
root_changelog = os.path.join(FEATURE_DIR, "CHANGELOG.md")
if not os.path.exists(root_changelog):
    ok("t5", "legacy feature-root CHANGELOG.md is gone")
else:
    ko("t5", f"legacy feature-root CHANGELOG.md still present: {root_changelog}")

# Import the resolver module once for t6/t7/t8.
spec = importlib.util.spec_from_file_location(
    "contract_lib_checks_migrated", CHECKS_PATH
)
if spec is None or spec.loader is None:
    ko("t6", f"could not import {CHECKS_PATH}")
else:
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # t6
    resolved = mod.resolve_spec_path(FEATURE_DIR, "spec.md")
    if resolved == spec_md:
        ok("t6", "resolve_spec_path resolves contract spec.md to docs/")
    else:
        ko("t6", f"resolve_spec_path returned {resolved}, expected {spec_md}")

    # t7
    resolved_cl = mod.resolve_changelog_path(FEATURE_DIR)
    if resolved_cl == changelog_md:
        ok("t7", "resolve_changelog_path resolves contract CHANGELOG to docs/")
    else:
        ko("t7", f"resolve_changelog_path returned {resolved_cl}, expected {changelog_md}")

    # t8 — contract validates itself at the new location.
    result = mod.validate_feature(FEATURE_DIR)
    if getattr(result, "passed", False):
        ok("t8", "validate_feature(contract) passes on flat docs/ layout")
    else:
        ko("t8", f"validate_feature(contract) failed: {getattr(result, 'messages', result)}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
