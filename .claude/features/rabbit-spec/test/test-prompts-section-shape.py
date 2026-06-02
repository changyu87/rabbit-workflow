#!/usr/bin/env python3
"""test-prompts-section-shape.py — rabbit-spec Inv 1 (prompts subset).

Loads feature.json and asserts the prompts entry shape: id='spec-create',
kind='subagent', inject containing philosophy + coding-rules, slots equal
to the three expected slot names.

Post issue #391 (Skill-path injection retirement): the kind='skill'
entry for 'rabbit-spec-update' is no longer expected; the test now
asserts ONLY the surviving 'spec-create' subagent entry and verifies
no kind:skill entries remain.

Version: 1.1.0
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

# post-#391 retirement: no kind:skill entries remain in this feature
skill_entries = [p for p in prompts if isinstance(p, dict) and p.get("kind") == "skill"]
if skill_entries:
    ids = sorted(p.get("id") for p in skill_entries)
    errors.append(f"kind:skill prompts entries are retired (issue #391); found ids: {ids}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("PASS: rabbit-spec prompts section conforms to Inv 1")
