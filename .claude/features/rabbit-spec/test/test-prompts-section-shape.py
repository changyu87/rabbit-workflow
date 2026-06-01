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
by_id = {p.get("id"): p for p in prompts if isinstance(p, dict)}
errors = []

# spec-create — the read-only subagent
sc = by_id.get("spec-create")
if sc is None:
    errors.append("prompts MUST include an entry with id='spec-create'")
else:
    if sc.get("kind") != "subagent":
        errors.append(f"spec-create.kind must be 'subagent', got {sc.get('kind')!r}")
    inject = set(sc.get("inject", []))
    expected_sc_inject = {
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/coding-rules.md",
    }
    if not expected_sc_inject.issubset(inject):
        errors.append(f"spec-create.inject must include philosophy + coding-rules, got {inject}")
    expected_slots = ["feature_name", "paths_globs", "paths_resolved"]
    if sc.get("slots") != expected_slots:
        errors.append(f"spec-create.slots must be {expected_slots}, got {sc.get('slots')}")

# rabbit-spec-update — the spec-revision skill
su = by_id.get("rabbit-spec-update")
if su is None:
    errors.append("prompts MUST include an entry with id='rabbit-spec-update'")
else:
    if su.get("kind") != "skill":
        errors.append(f"rabbit-spec-update.kind must be 'skill', got {su.get('kind')!r}")
    inject = set(su.get("inject", []))
    expected_su_inject = {
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/spec-rules.md",
    }
    if not expected_su_inject.issubset(inject):
        errors.append(f"rabbit-spec-update.inject must include philosophy + spec-rules, got {inject}")
    if su.get("slots") != ["args"]:
        errors.append(f"rabbit-spec-update.slots must be ['args'], got {su.get('slots')}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: rabbit-spec prompts section conforms to Inv 1")
