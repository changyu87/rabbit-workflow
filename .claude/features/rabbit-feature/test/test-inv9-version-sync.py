#!/usr/bin/env python3
"""E2E test for rabbit-spec Invariant 9 (version sync).

Invariant 9 requires `feature.json` `version` to equal `docs/spec/spec.md`
frontmatter `version` at every commit. Drift between the two means consumers
reading one source see stale lifecycle/contract information.
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")
SPEC_MD = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
CONTRACT_MD = os.path.join(FEATURE_DIR, "docs", "spec", "contract.md")


def _load_feature_version():
    with open(FEATURE_JSON) as f:
        data = json.load(f)
    return data.get("version")


def _load_spec_version():
    with open(SPEC_MD) as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert m, "spec.md must start with YAML frontmatter"
    frontmatter = m.group(1)
    vm = re.search(r"^version:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
    assert vm, "spec.md frontmatter must contain a version field"
    return vm.group(1)


def _load_contract_version():
    with open(CONTRACT_MD) as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert m, "contract.md must start with YAML frontmatter"
    frontmatter = m.group(1)
    vm = re.search(r"^version:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
    assert vm, "contract.md frontmatter must contain a version field"
    return vm.group(1)


def test_feature_json_exists():
    assert os.path.isfile(FEATURE_JSON), f"feature.json missing at {FEATURE_JSON}"


def test_spec_md_exists():
    assert os.path.isfile(SPEC_MD), f"spec.md missing at {SPEC_MD}"


def test_feature_json_has_version():
    v = _load_feature_version()
    assert v is not None and v != "", "feature.json must have a non-empty version"


def test_spec_md_has_version():
    v = _load_spec_version()
    assert v is not None and v != "", "spec.md frontmatter must have a non-empty version"


def test_contract_md_exists():
    assert os.path.isfile(CONTRACT_MD), f"contract.md missing at {CONTRACT_MD}"


def test_contract_md_has_version():
    v = _load_contract_version()
    assert v is not None and v != "", "contract.md frontmatter must have a non-empty version"


def test_versions_equal():
    """Inv 9: feature.json, spec.md, and contract.md versions MUST all match."""
    fv = _load_feature_version()
    sv = _load_spec_version()
    cv = _load_contract_version()
    assert fv == sv == cv, (
        f"version drift: feature.json={fv!r} vs spec.md={sv!r} vs contract.md={cv!r}"
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            fail += 1
    print()
    print("ALL PASS" if fail == 0 else f"FAILED: {fail}")
    sys.exit(0 if fail == 0 else 1)
