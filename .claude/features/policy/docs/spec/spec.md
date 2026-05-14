---
feature: policy
version: 1.2.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native subagent-policy injection point
status: active
---

# policy — Spec

## Purpose

Owns the three canonical rule files fed to every subagent dispatch.

## Surface

- `.claude/features/policy/philosophy.md`
- `.claude/features/policy/spec-rules.md`
- `.claude/features/policy/coding-rules.md`

## Invariants

1. All three rule files (`philosophy.md`, `spec-rules.md`, `coding-rules.md`) exist and are non-empty.
2. `workflow-rules.md` does not exist.

## Out of Scope

- Generating policy output on demand — consumers read files directly.
- Modifying files in any other feature.
