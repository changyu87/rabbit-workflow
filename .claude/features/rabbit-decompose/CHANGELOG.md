---
feature: rabbit-decompose
owner: rabbit-workflow team
deprecation_criterion: when rabbit-decompose's spec version history is folded into a structured schema-tracked log
---

# rabbit-decompose — Changelog

Version-keyed change log for the rabbit-decompose feature. The version here
tracks the spec version declared in `specs/spec.md` / `specs/contract.md`
frontmatter and the `version` field in `feature.json` (lockstep).

## Version notes

- **v0.2.0 (specs/ migration, #399 Phase 2):** Migrated the feature's spec
  directory from `docs/spec/` to `specs/` (`git mv docs/spec specs`,
  removed the now-empty `docs/`). Updated rabbit-decompose's own
  `docs/spec`-path references to `specs/` in `specs/spec.md` (Surface,
  Invariant 3, Tests section) and `specs/contract.md` (the
  `rabbit-spec-create` invoke purpose string). This rides on the contract
  feature's Phase 1 dual-read (#451), which already prefers `specs/` and
  falls back to `docs/spec/`, so the move keeps the feature green.
  rabbit-decompose has no scripts of its own (dispatcher-orchestrated MVP),
  so no path-resolution code needed updating. New E2E regression test
  `test/test-specs-layout.py` pins the migrated layout. Deprecation of the
  upstream `docs/spec/` fallback is owned by issue #399 Phase 3.

- **v0.1.0:** Initial rabbit-decompose feature — interactive
  feature-decomposition skill orchestrating `rabbit-feature-scaffold` +
  `rabbit-spec-create` per accepted feature.
