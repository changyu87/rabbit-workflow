#!/usr/bin/env python3
"""test-canonical-convention-text.py — E2E check that the policy rule files
NAME the canonical specs/ spec-directory layout, never the legacy
nested-under-docs layout.

Issue #399 Phase 3 (final) updates the convention *source* — the policy rule
files that every subagent and the repo-root CLAUDE.md consume — so the
canonical-convention text matches the on-disk reality established in Phase 2
(all 11 features migrated to the specs/ layout). This E2E test reads the rule
files exactly as a consumer would and asserts:

  - spec-rules.md ("Where the metadata lives", Specs/contracts row) names
    `specs/spec.md` and `specs/contract.md`.
  - philosophy.md (Bounded Scope) references the contract schema at
    `specs/contract.md`.
  - NO policy-owned file under the feature directory contains the legacy
    nested-spec substring (the convention source is fully migrated; the
    contract dual-read fallback lives in tdd-state-machine, not policy).

Traces: #399 (Phase 3, policy)

Version: 1.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when the canonical spec-directory layout is enforced
workflow-wide by a cross-feature harness that lints convention text against
the on-disk layout, making this per-feature text assertion redundant.
"""
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Built from parts so this source file does not itself contain the contiguous
# legacy substring (keeps the repo-wide convention grep clean).
LEGACY_SUBSTR = "docs" + "/" + "spec"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def read(rel):
    with open(os.path.join(FEATURE_DIR, rel)) as f:
        return f.read()


# spec-rules.md names the canonical specs/ paths in the metadata-location row.
spec_rules = read("spec-rules.md")
for phrase in ("`specs/spec.md`", "`specs/contract.md`"):
    if phrase not in spec_rules:
        fail(f"spec-rules.md must name {phrase} in 'Where the metadata lives'")

# philosophy.md Bounded Scope references the contract schema at specs/.
philosophy = read("philosophy.md")
if "`specs/contract.md`" not in philosophy:
    fail("philosophy.md Bounded Scope must reference `specs/contract.md`")

# No policy-owned file may carry the legacy nested-spec substring. Walk the
# whole feature directory the way the acceptance grep does.
for root, _dirs, files in os.walk(FEATURE_DIR):
    for name in files:
        path = os.path.join(root, name)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        if LEGACY_SUBSTR in content:
            fail(f"legacy '{LEGACY_SUBSTR}' substring must not appear in {path}")

print("All checks passed.")
