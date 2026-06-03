---
feature: rabbit-decompose
owner: rabbit-workflow team
deprecation_criterion: when rabbit-decompose's spec version history is folded into a structured schema-tracked log
---

# rabbit-decompose — Changelog

Version-keyed change log for the rabbit-decompose feature. The version here
tracks the spec version declared in `docs/spec.md` / `docs/contract.md`
frontmatter, the `version` field in `feature.json`, and the source
`skills/rabbit-decompose/SKILL.md` frontmatter (four-way lockstep).

## Version notes

- **v0.3.0 (flat `docs/` layout migration, #399 Phase 2b):** Relocated the
  feature's documentation surfaces from the legacy spec directory to the flat
  `docs/` layout. `specs/spec.md` → `docs/spec.md`, `specs/contract.md` →
  `docs/contract.md`, and the root `CHANGELOG.md` → `docs/CHANGELOG.md` were
  moved via `git mv` (history preserved); the now-empty spec directory was
  removed. The spec and contract bodies are unchanged — only their on-disk
  location moved. Frontmatter `version` was bumped to 0.3.0 across
  `feature.json`, `docs/spec.md`, `docs/contract.md`, and the source
  `skills/rabbit-decompose/SKILL.md` (four-way alignment). The SKILL.md
  frontmatter previously carried a stale scaffold default of `1.0.0`; it was
  brought into the feature's version lineage at 0.3.0 so all four surfaces
  agree. Because the source SKILL.md version changed, the deployed
  `.claude/skills/` copy needs a dispatcher republish. The contract resolver
  (`resolve_spec_path`) already prefers the flat `docs/` layout and falls back
  to the spec directory, so the migration is invisible to every cross-feature
  consumer. The layout E2E test was renamed/rewritten
  (`test/test-docs-layout.py`) to assert the flat `docs/` reality.

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
