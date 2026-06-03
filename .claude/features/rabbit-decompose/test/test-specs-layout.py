#!/usr/bin/env python3
"""test-specs-layout.py — issue #399 Phase 2 (rabbit-decompose specs/ migration)

End-to-end test for rabbit-decompose's docs/spec/ -> specs/ migration.

Phase 1 (#451) made the contract feature dual-read spec/contract paths
(specs/ preferred, docs/spec/ fallback). Phase 2 moves each feature's own
spec dir to specs/ one feature at a time; this test pins rabbit-decompose to
the migrated layout so a regression that re-introduces docs/spec/ is caught.

Asserts (all against the real feature tree, not a fixture):
  - specs/spec.md and specs/contract.md exist and are non-empty.
  - the legacy docs/ directory is gone (no docs/spec/ left behind).
  - rabbit-decompose's own tracked files carry no stale "docs/spec" string
    references (spec.md self-description, contract.md prose, feature.json).

Run non-interactively. Exits non-zero on failure.
"""

import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)

PASS = 0
FAIL = 0


def ok(name, msg):
    global PASS
    print(f"  PASS {name}: {msg}")
    PASS += 1


def fail(name, msg):
    global FAIL
    print(f"  FAIL {name}: {msg}", file=sys.stderr)
    FAIL += 1


# t1: specs/spec.md exists and is non-empty.
spec_md = os.path.join(FEATURE_DIR, "specs", "spec.md")
if os.path.isfile(spec_md) and os.path.getsize(spec_md) > 0:
    ok("t1", "specs/spec.md exists and is non-empty")
else:
    fail("t1", f"specs/spec.md missing or empty: {spec_md}")

# t2: specs/contract.md exists and is non-empty.
contract_md = os.path.join(FEATURE_DIR, "specs", "contract.md")
if os.path.isfile(contract_md) and os.path.getsize(contract_md) > 0:
    ok("t2", "specs/contract.md exists and is non-empty")
else:
    fail("t2", f"specs/contract.md missing or empty: {contract_md}")

# t3: the legacy docs/ directory is gone (migration removed empty docs/).
docs_dir = os.path.join(FEATURE_DIR, "docs")
if not os.path.exists(docs_dir):
    ok("t3", "legacy docs/ directory removed")
else:
    fail("t3", f"legacy docs/ still present: {docs_dir}")

# t4: no stale "docs/spec" string references in rabbit-decompose's own
# *active* files. The changelog and this test legitimately record the old
# path (history / assertion), so both are excluded from the scan.
EXCLUDE = {os.path.abspath(__file__),
           os.path.abspath(os.path.join(FEATURE_DIR, "CHANGELOG.md"))}
stale = []
for root, _dirs, files in os.walk(FEATURE_DIR):
    for fn in files:
        path = os.path.join(root, fn)
        # only scan text-ish tracked sources
        if not fn.endswith((".md", ".json", ".py", ".txt")):
            continue
        if os.path.abspath(path) in EXCLUDE:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                body = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        if "docs/spec" in body:
            stale.append(os.path.relpath(path, FEATURE_DIR))
if not stale:
    ok("t4", "no stale docs/spec references in rabbit-decompose files")
else:
    fail("t4", f"stale docs/spec references in: {stale}")


print()
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
