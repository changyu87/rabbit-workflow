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

- **v0.6.0 (Housekeeping Phase 2 — history-free doc surfaces, #548):** Opted
  `rabbit-meta` into the contract Inv 49 STRICT tier by setting top-level
  `"housekeeping_clean": true` in `feature.json` (data-driven opt-in via the
  contract checker's `derive_cleaned_features()`). Scrubbed the two strict-tier
  hits from `docs/spec.md`: (1) the layout paragraph dropped its parenthetical
  historical wrapper ("issue #399 Phase 2b migration from the `specs/` layout")
  in favour of a present-tense declarative statement of the current flat `docs/`
  layout — the migration history is recorded in the v0.5.0 note below; (2) the
  `deprecation_criterion` frontmatter was rephrased to active voice ("when a
  native Claude Code workflow contract mechanism supersedes rabbit's per-project
  plugin model") so the forward-looking lifecycle criterion no longer trips the
  tombstone-word pattern while keeping its meaning intact. No invariants were
  renumbered or removed; no substantive behaviour changed. `feature.json` and
  `docs/spec.md` frontmatter versions bumped to 0.6.0 in lockstep.

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
