#!/usr/bin/env python3
"""Structural tests for the rabbit-spec feature."""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


def test_feature_json_exists():
    path = os.path.join(FEATURE_DIR, "feature.json")
    assert os.path.isfile(path), "feature.json missing"


def test_feature_json_name():
    path = os.path.join(FEATURE_DIR, "feature.json")
    with open(path) as f:
        data = json.load(f)
    assert data.get("name") == "rabbit-spec", f"name: {data.get('name')}"


def test_feature_json_has_required_fields():
    path = os.path.join(FEATURE_DIR, "feature.json")
    with open(path) as f:
        data = json.load(f)
    for field in ["name", "version", "owner", "tdd_state", "summary", "deprecation_criterion"]:
        assert field in data, f"Missing field: {field}"


def test_feature_json_surface_skills_empty():
    path = os.path.join(FEATURE_DIR, "feature.json")
    with open(path) as f:
        data = json.load(f)
    assert data.get("surface", {}).get("skills") == [], "surface.skills must be []"


def test_spec_md_exists():
    path = os.path.join(FEATURE_DIR, "docs", "spec", "spec.md")
    assert os.path.isfile(path), "docs/spec/spec.md missing"


def test_contract_md_exists():
    path = os.path.join(FEATURE_DIR, "docs", "spec", "contract.md")
    assert os.path.isfile(path), "docs/spec/contract.md missing"


def test_skill_md_exists():
    path = os.path.join(FEATURE_DIR, "skills", "rabbit-spec", "SKILL.md")
    assert os.path.isfile(path), "skills/rabbit-spec/SKILL.md missing"


def test_skill_md_has_opus_model():
    path = os.path.join(FEATURE_DIR, "skills", "rabbit-spec", "SKILL.md")
    with open(path) as f:
        content = f.read()
    assert "model: opus" in content, "SKILL.md must declare model: opus in frontmatter"


def test_skill_md_mentions_brainstorming():
    path = os.path.join(FEATURE_DIR, "skills", "rabbit-spec", "SKILL.md")
    with open(path) as f:
        content = f.read()
    assert "brainstorming" in content.lower(), "SKILL.md must reference brainstorming superpower"


def test_skill_md_mentions_writing_plans():
    path = os.path.join(FEATURE_DIR, "skills", "rabbit-spec", "SKILL.md")
    with open(path) as f:
        content = f.read()
    assert "writing-plans" in content.lower() or "writing_plans" in content.lower(), \
        "SKILL.md must reference writing-plans superpower"


def test_skill_md_mentions_impl_suggestion():
    path = os.path.join(FEATURE_DIR, "skills", "rabbit-spec", "SKILL.md")
    with open(path) as f:
        content = f.read()
    assert "impl-suggestion" in content or "impl_suggestion" in content, \
        "SKILL.md must reference impl-suggestion output file"


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
