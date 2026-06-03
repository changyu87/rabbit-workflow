---
feature: rabbit-config
owner: rabbit-workflow team
deprecation_criterion: when rabbit-config's spec version history is folded into a structured schema-tracked log
---

# rabbit-config — CHANGELOG

Version-keyed change log for the rabbit-config feature. The version here
tracks the spec version declared in `docs/spec.md` frontmatter, the
`version` field in `feature.json`, the `docs/contract.md` frontmatter
version, and the `skills/rabbit-config/SKILL.md` frontmatter version
(four-way lockstep).

## Version notes

- **v1.6.0 (flat `docs/` layout migration, #399 Phase 2b):** Relocated the
  rabbit-config feature's documentation surfaces from `specs/` to the flat
  `docs/` layout. `specs/spec.md` → `docs/spec.md` and `specs/contract.md` →
  `docs/contract.md` were moved via `git mv` (history preserved); the
  now-empty `specs/` directory was removed. This fresh `docs/CHANGELOG.md`
  was created to hold the migration note (rabbit-config had no prior
  feature-root CHANGELOG.md). The spec and contract bodies are unchanged —
  only their on-disk location moved (and Inv 21 was rewritten in place to
  describe the flat `docs/` reality). Frontmatter `version` was bumped in
  four-way lockstep across `feature.json`, `docs/spec.md`,
  `docs/contract.md`, and `skills/rabbit-config/SKILL.md` (1.5.0 → 1.6.0;
  contract.md 1.3.0 → 1.6.0 and SKILL.md 1.2.0 → 1.6.0 brought into
  equality). The contract resolver (`resolve_spec_path`) already prefers the
  flat `docs/` layout and falls back to `specs/`, so the migration is
  invisible to every cross-feature consumer. The E2E layout test
  `test/test-spec-layout.py` was updated to assert the flat `docs/` reality
  (docs/spec.md, docs/contract.md, docs/CHANGELOG.md present; specs/ gone;
  resolver resolves to docs/). Because the source SKILL.md frontmatter
  version changed, the deployed copy at `.claude/skills/rabbit-config/SKILL.md`
  needs a dispatcher republish.
