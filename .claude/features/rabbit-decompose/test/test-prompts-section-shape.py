#!/usr/bin/env python3
"""test-prompts-section-shape.py — rabbit-decompose Inv 1.

Loads feature.json and asserts the prompts entry shape: id='rabbit-decompose',
kind='skill', inject containing philosophy + spec-rules, slots == ['args'].

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native feature-decomposition assistance
"""
import json
import os
import sys

FEATURE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_JSON = os.path.join(FEATURE_DIR, "feature.json")

with open(FEATURE_JSON) as f:
    data = json.load(f)

prompts = data.get("prompts", [])
errors = []

if len(prompts) != 1:
    errors.append(f"prompts MUST have exactly 1 entry, got {len(prompts)}")
else:
    p = prompts[0]
    if p.get("id") != "rabbit-decompose":
        errors.append(f"prompts[0].id must be 'rabbit-decompose', got {p.get('id')!r}")
    if p.get("kind") != "skill":
        errors.append(f"prompts[0].kind must be 'skill', got {p.get('kind')!r}")
    inject = set(p.get("inject", []))
    expected_inject = {
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/spec-rules.md",
    }
    if not expected_inject.issubset(inject):
        errors.append(f"prompts[0].inject must include philosophy + spec-rules, got {inject}")
    if p.get("slots") != ["args"]:
        errors.append(f"prompts[0].slots must be ['args'], got {p.get('slots')}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: rabbit-decompose prompts section conforms to Inv 1")
