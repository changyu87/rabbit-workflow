#!/usr/bin/env python3
"""Inv 35: three-way version alignment.

`feature.json.version`, `docs/spec/spec.md` frontmatter `version`, and
`docs/spec/contract.md` frontmatter `version` MUST match exactly.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when feature versioning moves to a single source of
truth (e.g., feature.json only).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FEATURE_DIR = Path(__file__).resolve().parents[1]
FEATURE_JSON = FEATURE_DIR / "feature.json"
SPEC_MD = FEATURE_DIR / "docs/spec/spec.md"
CONTRACT_MD = FEATURE_DIR / "docs/spec/contract.md"


def _frontmatter_version(md_path: Path) -> str:
    text = md_path.read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, f"{md_path.name} must start with YAML frontmatter"
    vm = re.search(r"^version:\s*(\S+)\s*$", m.group(1), re.MULTILINE)
    assert vm, f"{md_path.name} frontmatter must declare a version field"
    return vm.group(1)


def test_versions_equal() -> None:
    fv = json.loads(FEATURE_JSON.read_text())["version"]
    sv = _frontmatter_version(SPEC_MD)
    cv = _frontmatter_version(CONTRACT_MD)
    assert fv == sv == cv, (
        f"version drift: feature.json={fv!r}, spec.md={sv!r}, contract.md={cv!r}"
    )


if __name__ == "__main__":
    try:
        test_versions_equal()
        print("PASS test_versions_equal")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL test_versions_equal: {e}", file=sys.stderr)
        sys.exit(1)
