#!/usr/bin/env python3
"""test-contract-spec-dir-migrated.py — issue #399 Phase 2 (contract).

End-to-end test that contract's own spec/contract docs live under the new
canonical `specs/` layout and that the legacy `docs/spec/` (and the now-empty
`docs/`) tree is gone:

  t1  .claude/features/contract/specs/spec.md exists and is non-empty.
  t2  .claude/features/contract/specs/contract.md exists and is non-empty.
  t3  .claude/features/contract/docs/ no longer exists.
  t4  contract's spec.md is resolved by contract.lib.checks.resolve_spec_path
      to the specs/ candidate (proving the dual-read resolver prefers the
      migrated layout for contract itself).

The dual-read resolver still accepts the legacy `docs/spec/` layout for OTHER
features mid-migration (covered by test-spec-path-dual-read.py); this test only
asserts contract's own canonical has moved.

Non-interactive. Exits non-zero on any failure.

Version: 1.0.0
Owner: rabbit-workflow team (contract)
Deprecation criterion: when issue #399 Phase 3 drops the dual-read fallback and
every feature has migrated to specs/ (this test folds into the generic layout
checks at that point).
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
spec_md = os.path.join(FEATURE_DIR, "specs", "spec.md")
if os.path.isfile(spec_md) and os.path.getsize(spec_md) > 0:
    ok("t1", "specs/spec.md exists and is non-empty")
else:
    ko("t1", f"specs/spec.md missing or empty: {spec_md}")

# t2
contract_md = os.path.join(FEATURE_DIR, "specs", "contract.md")
if os.path.isfile(contract_md) and os.path.getsize(contract_md) > 0:
    ok("t2", "specs/contract.md exists and is non-empty")
else:
    ko("t2", f"specs/contract.md missing or empty: {contract_md}")

# t3
docs_dir = os.path.join(FEATURE_DIR, "docs")
if not os.path.exists(docs_dir):
    ok("t3", "legacy docs/ tree is gone")
else:
    ko("t3", f"legacy docs/ tree still present: {docs_dir}")

# t4
spec = importlib.util.spec_from_file_location(
    "contract_lib_checks_migrated", CHECKS_PATH
)
if spec is None or spec.loader is None:
    ko("t4", f"could not import {CHECKS_PATH}")
else:
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    resolved = mod.resolve_spec_path(FEATURE_DIR, "spec.md")
    if resolved == spec_md:
        ok("t4", "resolve_spec_path resolves contract spec.md to specs/")
    else:
        ko("t4", f"resolve_spec_path returned {resolved}, expected {spec_md}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
