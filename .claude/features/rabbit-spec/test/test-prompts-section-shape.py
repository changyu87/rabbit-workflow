#!/usr/bin/env python3
"""test-prompts-section-shape.py — rabbit-spec Inv 1 (prompts subset).

Loads feature.json and asserts the prompts entry shape: id='spec-create',
kind='subagent', inject containing philosophy + coding-rules, slots equal
to the three expected slot names.

Version: 1.0.0
Owner: rabbit-workflow team
Deprecation criterion: when Claude Code exposes native spec-lifecycle skills
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
    if p.get("id") != "spec-create":
        errors.append(f"prompts[0].id must be 'spec-create', got {p.get('id')!r}")
    if p.get("kind") != "subagent":
        errors.append(f"prompts[0].kind must be 'subagent', got {p.get('kind')!r}")
    inject = p.get("inject", [])
    expected_inject = {
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/coding-rules.md",
    }
    if not expected_inject.issubset(set(inject)):
        errors.append(f"prompts[0].inject must include philosophy + coding-rules, got {inject}")
    slots = p.get("slots", [])
    expected_slots = ["feature_name", "paths_globs", "paths_resolved"]
    if slots != expected_slots:
        errors.append(f"prompts[0].slots must be {expected_slots}, got {slots}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: rabbit-spec prompts section conforms to Inv 1")
