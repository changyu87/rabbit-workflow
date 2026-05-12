---
feature: policy
version: 1.1.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native subagent-policy injection point
status: active
---

# policy — Spec

## Purpose

Owns the four canonical rule files fed to every subagent dispatch.

## Surface

- `.claude/features/policy/philosophy.md`
- `.claude/features/policy/spec-rules.md`
- `.claude/features/policy/coding-rules.md`
- `.claude/features/policy/workflow-rules.md`

## Invariants

1. All four rule files exist and are non-empty.
2. `workflow-rules.md` contains sections: "Subagent-driven", "Full TDD", "Token/compliance", "Hard rules", "Cross-component handoffs".
3. R8 and R9 appear in `workflow-rules.md`.
4. R3 in `workflow-rules.md` explicitly mandates full-stack E2E coverage: tests must exercise the full chain from the user-facing entry point through to the final state change, not just individual script behavior in isolation.
5. R1 in `workflow-rules.md` explicitly states branch enforcement: (a) the session-init hook automatically creates a feature branch when the session starts on main, (b) all commits must land on a feature branch and never directly on main, and (c) the PR/merge step is the only path back to main.

## Out of Scope

- Generating policy output on demand — consumers read files directly.
- Modifying files in any other feature.
