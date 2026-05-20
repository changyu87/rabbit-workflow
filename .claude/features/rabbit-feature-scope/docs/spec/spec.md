---
feature: rabbit-feature-scope
version: 2.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: RETIRED 2026-05-19 — absorbed into rabbit-feature
status: retired
---

# rabbit-feature-scope — RETIRED

This feature is **RETIRED** as of v2.0.0. Its entire surface
(`resolve-scope.py`, `format-feature-context.py`, and the
`rabbit-feature-scope` skill) has been absorbed into the
[`rabbit-feature`](../../../rabbit-feature/) feature. The build pipeline
(`build-contract.json`) sources the skill from its absorbed location under
`rabbit-feature/skills/rabbit-feature-scope/SKILL.md`.

This directory is preserved only to host the retirement notice and a
regression test that pins the directory contents to the notice. There is no
runnable surface here.

## Where things live now

- Skill: `.claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md`
- Scripts: `.claude/features/rabbit-feature/scripts/resolve-scope.py`,
  `.claude/features/rabbit-feature/scripts/format-feature-context.py`
- Spec invariants: `.claude/features/rabbit-feature/docs/spec/spec.md`
  (section "Absorbed from rabbit-feature-scope")
- Tests: `.claude/features/rabbit-feature/test/`

## Lifecycle

- **Status:** retired
- **Final version:** 2.0.0 (retirement-only)
- **Successor:** `rabbit-feature`
- **Deprecation criterion:** met 2026-05-19 (absorption complete)
