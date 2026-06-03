#!/usr/bin/env python3
"""test-canonical-convention-text.py — E2E check that the policy rule files
name the flat `docs/` documentation layout, never the legacy spec-directory
home or the legacy nested-spec container.

The policy rule files that every subagent and the repo-root CLAUDE.md consume
carry the "Where the metadata lives" convention. This E2E test reads the rule
files exactly as a consumer would and asserts:

  - spec-rules.md ("Where the metadata lives", Specs/contracts row) names the
    flat `docs/spec.md`, `docs/contract.md`, and `docs/CHANGELOG.md` paths.
  - spec-rules.md no longer names the legacy spec-directory paths
    (`specs/spec.md`, `specs/contract.md`) as the canonical metadata home.
  - philosophy.md (Bounded Scope) references the contract schema at
    `docs/contract.md`, and no longer at the legacy spec-directory path.
  - NO policy-owned file under the feature directory contains the legacy
    nested-spec container substring (a `spec` subdirectory under `docs`, the
    prior #399 source layout). The flat `docs/spec.md` file — the live #399
    target layout — is a distinct path and is allowed.

Version: 3.0.0
Owner: rabbit-workflow team (policy)
Deprecation criterion: when the spec-directory layout is enforced
workflow-wide by a cross-feature harness that lints convention text against
the on-disk layout, making this per-feature text assertion redundant.
"""
import os
import sys

FEATURE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Built from parts so this source file does not itself contain the contiguous
# legacy substring (keeps the repo-wide convention grep clean). The legacy
# nested layout was a `spec` subdirectory under `docs`; the flat `docs/spec.md`
# file is the live target layout and is NOT matched.
LEGACY_SUBSTR = "docs" + "/" + "spec" + "/"
# Legacy spec-directory paths the convention text must NOT name as the
# canonical metadata home (assembled from parts so this source file does not
# itself name them as a live convention).
LEGACY_SPEC = "`" + "specs" + "/spec.md`"
LEGACY_CONTRACT = "`" + "specs" + "/contract.md`"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def read(rel):
    with open(os.path.join(FEATURE_DIR, rel)) as f:
        return f.read()


# spec-rules.md names the canonical flat docs/ paths in the metadata-location
# row.
spec_rules = read("spec-rules.md")
for phrase in ("`docs/spec.md`", "`docs/contract.md`", "`docs/CHANGELOG.md`"):
    if phrase not in spec_rules:
        fail(f"spec-rules.md must name {phrase} in 'Where the metadata lives'")

# spec-rules.md must no longer name the legacy spec-directory paths.
for phrase in (LEGACY_SPEC, LEGACY_CONTRACT):
    if phrase in spec_rules:
        fail(f"spec-rules.md must NOT name legacy {phrase} as the metadata home")

# philosophy.md Bounded Scope references the contract schema at flat docs/.
philosophy = read("philosophy.md")
if "`docs/contract.md`" not in philosophy:
    fail("philosophy.md Bounded Scope must reference `docs/contract.md`")
if LEGACY_CONTRACT in philosophy:
    fail(f"philosophy.md must NOT reference legacy {LEGACY_CONTRACT}")

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
