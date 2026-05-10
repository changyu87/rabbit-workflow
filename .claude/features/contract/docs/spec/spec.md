---
feature: contract
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native workflow contract mechanism that supersedes this feature's template, schema, and dispatch responsibilities
status: active
---

# contract — Spec

## Purpose

Owns all cross-feature templates, schemas, dispatch scripts, and enforcement scripts; provides but never directly modifies other features.

## Surface

**templates/**
- `.claude/features/contract/templates/spec-template.md`
- `.claude/features/contract/templates/contract-template.md`
- `.claude/features/contract/templates/bug-template.json`
- `.claude/features/contract/templates/triage-template.md`
- `.claude/features/contract/templates/feature-json-template.json`
- `.claude/features/contract/templates/subagent-launch-template.txt`
- `.claude/features/contract/templates/project-map-template.json`
- `.claude/features/contract/templates/registry-template.json`

**schemas/**
- `.claude/features/contract/schemas/feature.json.schema.json`
- `.claude/features/contract/schemas/registry.json.schema.json`
- `.claude/features/contract/schemas/bug.json.schema.json`
- `.claude/features/contract/schemas/project-map.json.schema.json`

**scripts/**
- `.claude/features/contract/scripts/policy-block.sh`
- `.claude/features/contract/scripts/dispatch-feature-edit.sh`
- `.claude/features/contract/scripts/rebuild-registry.sh`
- `.claude/features/contract/scripts/relink.sh`
- `.claude/features/contract/scripts/render-template.sh`
- `.claude/features/contract/scripts/check-maps-consistent.sh`
- `.claude/features/contract/scripts/rabbit-triage.sh`
- `.claude/features/contract/scripts/validate-feature.sh`

**scripts/enforcement/**
- `.claude/features/contract/scripts/enforcement/check-imports-resolve.sh`
- `.claude/features/contract/scripts/enforcement/check-naming.sh`
- `.claude/features/contract/scripts/enforcement/check-no-main-edits.sh`
- `.claude/features/contract/scripts/enforcement/check-opus-for-planning-agents.sh`
- `.claude/features/contract/scripts/enforcement/check-sentinel.sh`
- `.claude/features/contract/scripts/enforcement/check-symlinks-resolve.sh`
- `.claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.sh`
- `.claude/features/contract/scripts/enforcement/check-tests-non-interactive.sh`

## Invariants

1. Every file in `templates/` carries a `template_version` field.
2. `dispatch-feature-edit.sh` output begins with the sentinel `RABBIT-POLICY-BLOCK-v1`.
3. All scripts in `scripts/` and `scripts/enforcement/` are executable.
4. Every schema file in `schemas/` is valid JSON.

## Out of Scope

- This feature does not directly edit any other feature's files.
