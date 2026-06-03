---
feature: rabbit-cage
owner: rabbit-workflow team
deprecation_criterion: when rabbit-cage's spec version history is folded into a structured schema-tracked log
---

# rabbit-cage — Changelog

Version-keyed change log for the rabbit-cage feature. The version here tracks
the spec version declared in `docs/spec.md` frontmatter and the `version`
field in `feature.json` (lockstep).

## Version notes

- **v5.41.0 (flat docs/ layout, #399 Phase 2b):** Migrated the feature's spec
  artifacts from `specs/` to the flat `docs/` layout
  (`git mv specs/spec.md docs/spec.md`, `git mv specs/contract.md
  docs/contract.md`, removed the now-empty `specs/`). rabbit-cage carries no
  `docs/bugs/` subtree, so none is created. This rides on the contract
  feature's dual-read (`resolve_spec_path` / `resolve_changelog_path`), which
  prefers the flat `docs/` layout and falls back to `specs/`, so the move
  keeps the feature green. Spec/contract content is unchanged (location only,
  plus the lockstep version bump). The deployed hooks under `hooks/` are
  untouched — a doc move relocates only the doc artifacts the resolver already
  prefers, so no manifest republish is needed. New `docs/CHANGELOG.md` (this
  file) records the migration. The E2E regression test
  `test/test-specs-layout.py` pins the flat layout and asserts the contract
  resolver targets `docs/` for both the spec/contract pair and the changelog.
  Deprecation of the upstream `specs/` fallback is owned by issue #399 Phase 3.

- **v5.40.0 and earlier:** Pre-migration history tracked the `specs/` layout
  spec/contract frontmatter and `feature.json` version (lockstep).
