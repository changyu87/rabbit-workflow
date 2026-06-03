#!/usr/bin/env python3
"""test-spec-layout.py — Inv 21 (docs/spec -> specs migration, #399 Phase 2).

End-to-end structural test that rabbit-config's spec artifacts live under the
new `specs/` layout and that the legacy `docs/` directory is gone. Read-only:
inspects the live feature directory layout; performs no filesystem mutation
(Inv 17).

  t21a: specs/spec.md exists and is non-empty
  t21b: specs/contract.md exists and is non-empty
  t21c: the legacy docs/ directory no longer exists under the feature
  t21d: spec.md frontmatter version equals feature.json version (lockstep)
  t21e: contract.md frontmatter version is present
"""

import json
import os
import sys

FEATURE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)

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


SPECS_DIR = os.path.join(FEATURE_DIR, "specs")
SPEC_MD = os.path.join(SPECS_DIR, "spec.md")
CONTRACT_MD = os.path.join(SPECS_DIR, "contract.md")
DOCS_DIR = os.path.join(FEATURE_DIR, "docs")
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

# t21a
if not os.path.isfile(SPEC_MD):
    fail("21a", f"specs/spec.md missing at {SPEC_MD}")
elif os.path.getsize(SPEC_MD) == 0:
    fail("21a", "specs/spec.md is empty")
else:
    ok("21a", "specs/spec.md exists and is non-empty")

# t21b
if not os.path.isfile(CONTRACT_MD):
    fail("21b", f"specs/contract.md missing at {CONTRACT_MD}")
elif os.path.getsize(CONTRACT_MD) == 0:
    fail("21b", "specs/contract.md is empty")
else:
    ok("21b", "specs/contract.md exists and is non-empty")

# t21c
if os.path.exists(DOCS_DIR):
    fail("21c", f"legacy docs/ still exists at {DOCS_DIR}")
else:
    ok("21c", "legacy docs/ directory is gone")

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

if FAIL:
    print("test-spec-layout: FAIL", file=sys.stderr)
    sys.exit(1)
print("test-spec-layout: all checks passed.")
