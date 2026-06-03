#!/usr/bin/env python3
"""test-version-alignment.py — Inv 11.

Asserts feature.json `version`, specs/spec.md frontmatter `version`,
and specs/contract.md frontmatter `version` are byte-equal.
"""

import json
import re
import sys
from pathlib import Path

CAGE = Path(__file__).resolve().parents[1]


def _frontmatter_version(path: Path) -> str:
    text = path.read_text()
    m = re.search(r"(?ms)^---\s*\n(.*?)\n---\s*\n", text)
    if not m:
        raise AssertionError(f"{path}: no YAML frontmatter")
    fm = m.group(1)
    vm = re.search(r"(?m)^version:\s*(\S+)\s*$", fm)
    if not vm:
        raise AssertionError(f"{path}: no version: line in frontmatter")
    return vm.group(1)


def main() -> int:
    fj_version = json.loads((CAGE / "feature.json").read_text())["version"]
    spec_version = _frontmatter_version(CAGE / "specs/spec.md")
    contract_version = _frontmatter_version(CAGE / "specs/contract.md")
    assert fj_version == spec_version == contract_version, (
        f"version drift: feature.json={fj_version!r}, "
        f"spec={spec_version!r}, contract={contract_version!r}")
    print(f"PASS version alignment: {fj_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
