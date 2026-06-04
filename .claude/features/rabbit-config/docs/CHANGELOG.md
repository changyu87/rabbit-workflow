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

- **v1.8.0 (housekeeping round 2 — measured doc-surface line removal, #683
  under #639):** Round-1 (#676) reworded; this pass REMOVES redundant doc
  content, measured in lines deleted, after a #639 prove-it-dead-or-flag check
  per claim. Three collapses landed, each to a single authoritative statement:
  (1) `docs/spec.md` "## Tech Stack" section deleted — it duplicated VERBATIM
  the same blurb in `docs/contract.md` ("Python 3 stdlib only. Imports
  contract.lib.mutation at runtime. No Bash runtime dependency."); `grep`
  across `contract/lib/` and `contract/scripts/` found NO validator that
  requires a Tech-Stack section in spec.md, so the spec copy is proven-dead
  redundancy. The authoritative copy stays in `docs/contract.md` (the
  dependency/stack-declaration surface). The deletion sits BELOW spec.md
  line 44, so the contract strict-tier ALLOWLIST line-pin
  `("rabbit-config", "spec.md", 44, "retired")` is preserved. (2)
  `skills/rabbit-config/SKILL.md` "## Subcommands" bullet list deleted — it
  re-enumerated the subcommand catalog that lives authoritatively (with full
  per-configurable semantics) in the SKILL.md frontmatter `description`, the
  load-bearing trigger surface enforced by `test/test-skill-description.py`
  (Inv 19) and `test/test-skill-no-dead-permissions.py`. (3) The SKILL.md
  "### Values-style" / "### Actions-style" usage sub-blocks and the
  spec-restating "## Active Override Alerts" (duplicates Inv 15/16) and the
  two spec-restating "## Notes" bullets (alphabetical enumeration duplicates
  the Interpreter-Behavior section; validation-rules duplicates Inv 12/13)
  were dropped; the one non-duplicated operational fact — the concrete
  `python3 .../rabbit-config.py <subcommand> ...` invocation pointer plus the
  idempotency note — is kept. Measured reduction: spec.md 233 → 228, SKILL.md
  65 → 28; contract.md unchanged (62, holds the surviving Tech-Stack copy).
  The stale `feature.json spec_no_change_reason` (left over from #676, which
  was SKILL-only) is removed because this version DOES edit spec.md. New E2E
  regression `test/test-housekeeping-683-redundancy-removed.py` (t1–t5) pins
  the removals AND guards the must-survive content (contract.md Tech Stack,
  the line-44 "retired" pin, every active configurable in SKILL.md). No
  invariant added, renumbered, or removed; no boundary-contract surface
  change; the strict-tier and deployed-skills gates stay GREEN. Frontmatter
  `version` bumped in four-way lockstep across `feature.json`, `docs/spec.md`,
  `docs/contract.md`, and `skills/rabbit-config/SKILL.md` (1.7.1 → 1.8.0).
  Because the source SKILL.md frontmatter version AND body changed, the
  deployed copy at `.claude/skills/rabbit-config/SKILL.md` needs a dispatcher
  republish.

- **v1.7.1 (drop dangling `permissions lock/unlock` references):** rabbit-cage
  retired the dead `permissions lock|unlock` configurable and deleted its
  backing script `repo-permissions.py`. rabbit-config's `SKILL.md` still
  documented that subcommand, so those references dangled. Removed the
  `permissions (lock/unlock)` enumeration item and the `permissions lock|unlock`
  trigger phrase from the frontmatter description (configurables enumeration now
  ends at (5) bash-allow); removed the `permissions lock|unlock` CLI-table row;
  and removed the `rabbit-config permissions lock` / `unlock` example block
  (the now-empty "Actions-style subcommands (no extra value)" subsection was
  dropped with it). The active `bypass-permissions` configurable (sets
  `permissions.defaultMode`) is load-bearing and was left untouched, as were
  `human-approval`, `prompt-threshold`, `allowed-tools`, and `bash-allow`.
  Regression test `test/test-skill-no-dead-permissions.py` asserts the dead
  references are gone while every active configurable remains documented.
  Frontmatter `version` bumped in four-way lockstep across `feature.json`,
  `docs/spec.md`, `docs/contract.md`, and `skills/rabbit-config/SKILL.md`
  (1.7.0 → 1.7.1). Because the source SKILL.md frontmatter version changed,
  the deployed copy at `.claude/skills/rabbit-config/SKILL.md` needs a
  dispatcher republish.

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
