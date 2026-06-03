---
feature: rabbit-issue
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-issue feature is retired or its change history is folded into a structured schema-tracked log
---

# rabbit-issue — Changelog

Version-keyed change log for the rabbit-issue feature. The version here tracks
the spec version declared in `docs/spec.md` frontmatter and the `version`
field in `feature.json` (lockstep); `contract.md` carries its own version.

## Version notes

- **v1.3.0 (flat docs/ layout, #399 Phase 2b):** Relocated the feature's spec
  artifacts from `specs/` to the flat `docs/` layout via `git mv`
  (`specs/spec.md` -> `docs/spec.md`, `specs/contract.md` -> `docs/contract.md`,
  root `CHANGELOG.md` -> `docs/CHANGELOG.md`, this file); the now-empty
  `specs/` directory was removed. The pre-existing `docs/bugs/` subtree is
  preserved as a sibling of the flat doc files — never replaced or nested
  under. This rides on the contract feature's dual-read resolver
  (`resolve_spec_path`), which prefers the flat `docs/` layout and falls back
  to `specs/`, so the move keeps the feature green. Spec/contract content is
  unchanged (location only). Updated rabbit-issue's own spec-aware tooling for
  the flat layout: `test/test-spec-presence.py` resolver now prefers `docs/`
  over `specs/` and its cutover invariant pins that `docs/spec.md` exists and
  `specs/` is gone; the `rabbit-issue` SKILL Work Protocol dual-read prose and
  the `test-gh-helper-resolves-rabbit-repo.py` docstring reference were updated
  to the flat `docs/` layout. Added the E2E regression test
  `test/test-specs-layout.py`, which pins the flat layout, asserts `docs/bugs/`
  is retained, the root `CHANGELOG.md` is gone, and the contract resolver
  targets `docs/`. Lockstep minor bump of `feature.json` / `spec.md` /
  `SKILL.md` (1.2.3 -> 1.3.0) and `contract.md` (1.1.2 -> 1.2.0). Deprecation
  of the upstream `specs/` fallback is owned by issue #399 Phase 3.

- **v1.2.3 (persist not-planned reason-text, #476):** `item-status.py close
  --reason not-planned` now persists the validated `--reason-text` as the close
  comment on the same `gh issue close` call, instead of validating then
  discarding it. With `--comment` also supplied, the reason-text leads
  (separated by a blank line); with only `--reason-text` it is the comment on
  its own. The `completed` close path is unchanged. Added three regression
  tests in `test/test-item-status.py`. Lockstep bump of `feature.json` /
  `spec.md` / `SKILL.md` (1.2.2 -> 1.2.3) and the `item-status.py` module
  docstring (1.1.0 -> 1.1.1).

- **v1.2.2 (specs/ migration, #399 Phase 2):** Migrated the spec surface from
  `docs/spec/` to the canonical `specs/` layout via `git mv` (superseded by
  v1.3.0's flat `docs/` layout). The `docs/bugs/` directory was retained.
  Resolved the `feature.json` backlink in `spec.md` and made the feature's own
  spec-aware tooling dual-read. Lockstep patch bump of `feature.json` /
  `spec.md` / `SKILL.md` (1.2.1 -> 1.2.2) and `contract.md` (1.1.1 -> 1.1.2).

- **v1.2.1 (owner sweep, #416):** Changed the feature owner from an individual
  login to the team identity `rabbit-workflow team` across every owner-bearing
  location in the feature (feature.json, spec/contract frontmatter, SKILL.md
  frontmatter, every runtime-script docstring, and the test-helper / test-module
  owner markers). Added `test/test-owner-sweep.py`. Lockstep patch bump of
  `feature.json` / `spec.md` / `SKILL.md` (1.2.0 -> 1.2.1) and `contract.md`
  (1.1.0 -> 1.1.1).

- **v1.2.0 and earlier:** Pre-sweep history of the GH-Issues wrapper (File /
  List / Work protocols, label schema, rabbit-managed safety guard, close-reason
  gating, and upstream-repo discovery), tracked lockstep across `feature.json`
  and the spec/contract frontmatter.
