---
feature: rabbit-spec
version: 2.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: RETIRED 2026-05-19 — absorbed into rabbit-feature as rabbit-feature-spec
status: retired
---

# rabbit-spec — RETIRED

This feature is **RETIRED** as of v2.0.0. Its entire surface (the
`rabbit-spec` skill) has been absorbed into the
[`rabbit-feature`](../../../rabbit-feature/) feature and renamed to
`rabbit-feature-spec`. The build pipeline (`build-contract.json`) sources
the skill from its absorbed location under
`rabbit-feature/skills/rabbit-feature-spec/SKILL.md`.

This directory is preserved only to host the retirement notice and a
regression test that pins the directory contents to the notice. There is no
runnable surface here.

## Where things live now

- Skill: `.claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md`
- Deployed skill: `.claude/skills/rabbit-feature-spec/SKILL.md`
- Spec invariants: `.claude/features/rabbit-feature/docs/spec/spec.md`
- Tests: `.claude/features/rabbit-feature/test/`

## Lifecycle

- **Status:** retired
- **Final version:** 2.0.0 (retirement-only)
- **Successor:** `rabbit-feature` (skill name: `rabbit-feature-spec`)
- **Deprecation criterion:** met 2026-05-19 (absorption complete)
