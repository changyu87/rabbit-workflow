---
feature: rabbit-meta
owner: rabbit-workflow team
deprecation_criterion: when rabbit-meta's spec version history is folded into a structured schema-tracked log
---

# rabbit-meta — Changelog

Version-keyed change log for the rabbit-meta feature. The version here tracks
the spec version declared in `docs/spec.md` frontmatter and the `version`
field in `feature.json` (lockstep).

## Version notes

- **v0.5.0 (flat docs/ layout, #399 Phase 2b):** Migrated the feature's spec
  artifacts from `specs/` to the flat `docs/` layout
  (`git mv specs/spec.md docs/spec.md`, `git mv specs/contract.md
  docs/contract.md`, removed the now-empty `specs/`). The pre-existing
  `docs/bugs/` subtree is preserved as a sibling of the flat doc files —
  never replaced or nested under. This rides on the contract feature's
  dual-read (`resolve_spec_path` / `resolve_changelog_path`), which prefers
  the flat `docs/` layout and falls back to `specs/`, so the move keeps the
  feature green. Spec/contract content is unchanged (location only). New
  `docs/CHANGELOG.md` (this file) records the migration. The E2E regression
  test `test/test-specs-layout.py` pins the flat layout and asserts the
  resolver targets `docs/`. Deprecation of the upstream `specs/` fallback is
  owned by issue #399 Phase 3.

- **v0.4.0 and earlier:** Pre-migration history tracked the `specs/` layout
  spec/contract frontmatter and `feature.json` version (lockstep).
