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

- **v1.7.0 (housekeeping strict-tier opt-in):** Declared top-level
  `"housekeeping_clean": true` in `feature.json`, opting rabbit-config into
  the contract historical-burden strict tier (bare issue/PR refs, per-issue
  prose pointers, tombstone language) enforced by
  `contract/test/test-spec-bodies-no-historical-tags.py`. A scan of all
  rabbit-config doc surfaces (`docs/spec.md`, `docs/contract.md`,
  `skills/rabbit-config/SKILL.md`) found no historical-burden tags to scrub:
  the sole strict-tier match is the load-bearing status-enum literal
  "retired" at `docs/spec.md:44` ("skipping retired features"), which names
  the verbatim `data.get("status") == "retired"` value the interpreter
  checks and is suppressed by the line-pinned contract ALLOWLIST entry
  `("rabbit-config", "spec.md", 44, "retired")`. The opt-in is therefore a
  clean no-op beyond the flag — the strict tier engages and stays GREEN.
  Frontmatter `version` bumped in four-way lockstep across `feature.json`,
  `docs/spec.md`, `docs/contract.md`, and `skills/rabbit-config/SKILL.md`
  (1.6.0 → 1.7.0). Because the source SKILL.md frontmatter version changed,
  the deployed copy at `.claude/skills/rabbit-config/SKILL.md` needs a
  dispatcher republish.

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
