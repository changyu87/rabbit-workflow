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

- **v5.42.0 (3-row rabbit-box SessionStart banner, #449):** Redesigned the
  SessionStart welcome banner emitted by `hooks/session-start-dispatcher.py`.
  The single compact `[rabbit] 🐇 rabbit v<version>` line is replaced by a
  three-row rabbit box around the centered version: a top border of 32 🐇, a
  middle row `🐇 rabbit v<version> 🐇` with the version centered in the
  32-wide box, and a bottom border of 32 🐇 — each row carrying the brand
  prefix via the dispatcher's subline renderer. The box is built by the new
  `_version_box(root)` helper (module constants `_BOX_WIDTH = 32`,
  `_BOX_RABBIT`) and inserted ahead of all other SessionStart payloads.
  Separately, the welcome line `Welcome — governing policies loaded` is now
  rendered PLAIN (brand prefix only — no ✅ icon, no ━━━ bars): the new
  `_strip_welcome_decoration(payloads)` helper converts contract's
  `welcome_with_policy` `banner` payload to a `subline` in place, leaving the
  three policy summary sublines (philosophy/spec-rules/coding-rules)
  untouched. Version sourcing (`.version` plugin, `feature.json` standalone)
  is unchanged. Spec Inv 36 added; no invariants retired or renumbered.
  `hooks/session-start-dispatcher.py` is a `publish_hook` deployed hook — its
  deployed copy under `.claude/hooks/` drifts until republished. Covered by
  the new e2e `test/test-runtime-banner-shape.py` (box shape, centered
  version, plain welcome line, policy sublines intact, box-before-welcome
  ordering), wired into `test/run.py`; the prior `#326` ordering test
  (`test/test-session-start-version-line.py`) stays green.
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
