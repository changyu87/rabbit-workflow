#!/usr/bin/env python3
"""test-spec-layout.py — Inv 21 (specs/ -> flat docs/ migration, #399 Phase 2b).

End-to-end structural test that rabbit-config's spec artifacts live under the
flat `docs/` layout and that the legacy `specs/` directory is gone. Read-only:
inspects the live feature directory layout; performs no filesystem mutation
(Inv 17).

  t21a: docs/spec.md exists and is non-empty
  t21b: docs/contract.md exists and is non-empty
  t21c: the legacy specs/ directory no longer exists under the feature
  t21d: spec.md frontmatter version equals feature.json version (lockstep)
  t21e: contract.md frontmatter version is present
  t21f: docs/CHANGELOG.md exists and is non-empty
  t21g: the contract resolver (resolve_spec_path) resolves spec.md and
        contract.md to the flat docs/ location
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)

# Import the canonical dual-read resolver from contract.lib.checks. The
# feature directory layout is .claude/features/<feature>/test/, so three
# parents up from this file is .claude/features/.
_FEATURES_DIR = os.path.normpath(os.path.join(FEATURE_DIR, ".."))
if _FEATURES_DIR not in sys.path:
    sys.path.insert(0, _FEATURES_DIR)
from contract.lib.checks import resolve_spec_path  # noqa: E402

FAIL = 0


def fail(n, msg):
    global FAIL
    print(f"FAIL t{n}: {msg}", file=sys.stderr)
    FAIL = 1


def ok(n, msg):
    print(f"ok t{n}: {msg}")


def _frontmatter_field(path, field):
    """Return the value of a top-level YAML frontmatter `field:` line, or None."""
    with open(path) as fh:
        content = fh.read()
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    block = content[3:end]
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{field}:"):
            return stripped.split(":", 1)[1].strip()
    return None


DOCS_DIR = os.path.join(FEATURE_DIR, "docs")
SPEC_MD = os.path.join(DOCS_DIR, "spec.md")
CONTRACT_MD = os.path.join(DOCS_DIR, "contract.md")
CHANGELOG_MD = os.path.join(DOCS_DIR, "CHANGELOG.md")
SPECS_DIR = os.path.join(FEATURE_DIR, "specs")
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

# t21a
if not os.path.isfile(SPEC_MD):
    fail("21a", f"docs/spec.md missing at {SPEC_MD}")
elif os.path.getsize(SPEC_MD) == 0:
    fail("21a", "docs/spec.md is empty")
else:
    ok("21a", "docs/spec.md exists and is non-empty")

# t21b
if not os.path.isfile(CONTRACT_MD):
    fail("21b", f"docs/contract.md missing at {CONTRACT_MD}")
elif os.path.getsize(CONTRACT_MD) == 0:
    fail("21b", "docs/contract.md is empty")
else:
    ok("21b", "docs/contract.md exists and is non-empty")

# t21c
if os.path.exists(SPECS_DIR):
    fail("21c", f"legacy specs/ still exists at {SPECS_DIR}")
else:
    ok("21c", "legacy specs/ directory is gone")

# t21d
with open(FEATURE_JSON) as fh:
    feat = json.load(fh)
feat_version = feat.get("version")
if os.path.isfile(SPEC_MD):
    spec_version = _frontmatter_field(SPEC_MD, "version")
    if spec_version is None:
        fail("21d", "spec.md frontmatter has no version field")
    elif spec_version != feat_version:
        fail("21d", f"version mismatch: spec.md={spec_version!r} feature.json={feat_version!r}")
    else:
        ok("21d", f"spec.md version matches feature.json ({feat_version})")
else:
    fail("21d", "cannot check version lockstep: spec.md missing")

# t21e
if os.path.isfile(CONTRACT_MD):
    contract_version = _frontmatter_field(CONTRACT_MD, "version")
    if contract_version is None:
        fail("21e", "contract.md frontmatter has no version field")
    else:
        ok("21e", f"contract.md frontmatter version present ({contract_version})")
else:
    fail("21e", "cannot check contract version: contract.md missing")

# t21f
if not os.path.isfile(CHANGELOG_MD):
    fail("21f", f"docs/CHANGELOG.md missing at {CHANGELOG_MD}")
elif os.path.getsize(CHANGELOG_MD) == 0:
    fail("21f", "docs/CHANGELOG.md is empty")
else:
    ok("21f", "docs/CHANGELOG.md exists and is non-empty")

# t21g
resolved_spec = resolve_spec_path(FEATURE_DIR, "spec.md")
resolved_contract = resolve_spec_path(FEATURE_DIR, "contract.md")
if os.path.normpath(resolved_spec) != os.path.normpath(SPEC_MD):
    fail("21g", f"resolver did not resolve spec.md to docs/: {resolved_spec}")
elif os.path.normpath(resolved_contract) != os.path.normpath(CONTRACT_MD):
    fail("21g", f"resolver did not resolve contract.md to docs/: {resolved_contract}")
else:
    ok("21g", "contract resolver resolves spec.md and contract.md to flat docs/")

if FAIL:
    print("test-spec-layout: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-spec-layout: all checks passed.")
