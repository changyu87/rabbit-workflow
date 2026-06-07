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

- **v0.8.0 (detect_mode returns `"vendored"` — completes the #980
  plugin→vendored migration, #990):** Flipped `lib/mode_detection.py`
  `detect_mode()` to return the literal string `"vendored"` (was `"plugin"`)
  for the vendored `.rabbit/` case; `"standalone"` is unchanged. This is the
  final, value-flip step of the staged #980 migration: the preparatory ticks
  (#987/#988/#989/#997/#1001) already made every consumer dual-accept BOTH
  spellings, and the contract repo-gate (post-#998, running all per-feature
  suites) was confirmed fully green after the flip, so no consumer was
  reddened. Added the `is_vendored(mode: str) -> bool` coexistence predicate
  to the same module: it dual-accepts BOTH `"vendored"` and the older
  `"plugin"` spelling as the vendored install and returns `False` for every
  other value (including `"standalone"`). Coexistence deprecation criterion:
  drop the `"plugin"` acceptance in `is_vendored` once no install carries the
  older marker spelling. Updated the module docstring and Inv 1 (now an
  Inv 1(a) vendored-signature clause plus a new Inv 1(b) coexistence-helper
  clause; subsequent clauses re-lettered c–e, no invariant renumbered). The
  Purpose line's "plugin-mode machinery" wording was retitled to
  "vendored-mode machinery". `test/test-mode-detection.py` updated to assert
  the `"vendored"` return for the `.rabbit/` cwd and `"standalone"` for the
  repo root, plus new cases pinning `is_vendored` dual-accept. `feature.json`
  and `docs/spec.md` versions 0.7.4 → 0.8.0; `docs/contract.md` 0.2.4 → 0.2.5
  (own track; JSON block unchanged).

- **v0.7.4 (housekeeping — measured reduction wave, #815, under #794):**
  Measured verify-or-flag reduction pass on `docs/spec.md` (73 → 69 lines,
  −4), cutting redundant restatement and a decorative parenthetical with zero
  behaviour or contract loss. Removals, each resolved by a deterministic check
  first: (1) the Purpose paragraph's Tier-1/Tier-2 boundary restatement — the
  "What this feature does NOT define" section owns that boundary
  authoritatively, and every named owner there (`rabbit-feature`,
  `rabbit-cage`, `contract`, `rabbit-spec`) was confirmed live by inspecting
  each owning feature; Purpose now points to that section instead of
  duplicating it; (2) the Invariants preamble's reflow-recourse sentence
  naming `scripts/reflow-invariants.py` — recoverable from the `contract`
  feature's own spec, so a decorative cross-reference here; the load-bearing
  opt-in claim (the `feature.json` flag and the Inv 30 strict-tier
  enforcement) was kept verbatim; (3) the Tech Stack decorative parenthetical
  "(matches the Python-only invariants in `contract` and `rabbit-cage`)". The
  lib modules, templates, contract JSON, and the existing test suite were
  inspected and left unchanged — already lean after the v0.7.1/v0.7.2 rounds.
  New E2E guard `test/test-spec-lean.py` pins the reduction outcome (removed
  prose stays removed; load-bearing scope-exclusion owners and the
  contiguous-invariant opt-in claim survive); wired into `test/run.py`. No
  invariants renumbered; no behaviour changed. `feature.json` and
  `docs/spec.md` versions 0.7.3 → 0.7.4, `docs/contract.md` 0.2.3 → 0.2.4
  (own track).

- **v0.7.3 (opt into contiguous_invariants strict tier, #741, #724
  follow-up):** Declared `"contiguous_invariants": true` at the top level of
  `feature.json`, opting rabbit-meta into the strict contiguous-numbering tier
  of contract Inv 30. The spec's three invariants were already contiguous
  (1..3) — verified via `scripts/reflow-invariants.py` reporting a no-op — so
  no reflow was needed; this is a pure opt-in. Added the "## Invariants"
  preamble documenting the opt-in and the reflow recourse, plus
  `test/test-contiguous-invariants-optin.py` (t1: flag is true; t2: numbering
  passes the canonical strict-tier checker). Contract version 0.2.2 → 0.2.3
  (own track).

- **v0.7.2 (housekeeping — verify-or-fix stale spec-seeder ownership claim,
  #706, under #639):** Resolved the FLAGGED unverifiable exclusion from v0.7.1.
  Deterministic verification: (1) `find .claude/features/spec-seeder` → EMPTY
  (no such feature dir); (2) `rabbit-spec/docs/spec.md` now owns the
  spec-lifecycle / spec-drafting role (`rabbit-spec-create` + the
  `rabbit-spec-creator` read-only subagent) — the former `spec-seeder` feature
  was absorbed into rabbit-spec; (3) `rabbit-feature-new` is a stale skill
  name — the live skill is `rabbit-feature-scaffold` (`find` confirms
  `.claude/skills/rabbit-feature-scaffold` and
  `.claude/features/rabbit-feature/skills/rabbit-feature-scaffold`; no live
  `rabbit-feature-new` outside this worktree's own checkout). The "What this
  feature does NOT define" line that read "The spec-seeding subagent invoked
  by `rabbit-feature-new` — owned by the `spec-seeder` feature." was CORRECTED
  to name the live owner/skill: "The spec-drafting subagent invoked during
  feature scaffolding (`rabbit-feature-scaffold`) — owned by `rabbit-spec`."
  This is correction of dead content (per coding-rules §6), not a reword: the
  exclusion still holds (rabbit-meta does not own spec-drafting) but the named
  owner and skill were both dead. The separately-noted DEAD
  `.claude/features/spec-seeder/` reference in `rabbit-feature/docs/spec.md` is
  OUT OF rabbit-meta's scope and was FLAGGED as a `housekeeping`-tagged,
  `feature:rabbit-feature` sub-issue for a future in-scope tick (not edited
  here). New E2E guard `test/test-spec-seeder-ownership-retired.py` scans
  `docs/spec.md` and fails on any `spec-seeder` reference or stale
  spec-seeding/`rabbit-feature-new` ownership claim; wired into `test/run.py`.
  No invariants renumbered; no behaviour changed. `feature.json` and
  `docs/spec.md` versions bumped to 0.7.2, `docs/contract.md` to 0.2.2.

- **v0.7.1 (housekeeping round 2 — measured line removal, #687, under #639):**
  Removal pass on `docs/spec.md` (80 → 67 lines, −13). Deletions, each verified
  by a deterministic check before removal: (1) the `scripts/` Surface entry and
  Inv 4 describing `scripts/bootstrap.sh` — `find` returns no such file and no
  `test/test-bootstrap.py` exists, so the artifact and its coverage are proven
  dead (the spec framed it as speculative "MAY exist"); the now-orphaned "and
  the bootstrap helper" fragment in Purpose was removed with it; (2) the Inv 1
  t1–t5 behavioral-case enumeration and the Inv 2/Inv 3 per-test (t1–t7)
  coverage parentheticals — redundant restatements of `test/test-*.py`, which
  remain the authoritative source (collapsed to a pointer); (3) the Tests
  section's stale Inv-4 bootstrap line and per-invariant test-mapping recap,
  collapsed to one sentence. `docs/contract.md` was inspected and left unchanged:
  its JSON block is the minimal all-empty machine-first contract schema with no
  removable dead content. The "spec-seeder feature" ownership exclusion was
  FLAGGED (unverifiable — no `spec-seeder` dir, rabbit-spec calls it the
  "former" feature, rabbit-feature still references its dispatch path) as
  housekeeping issue #706 and KEPT per coding-rules §6. No invariants renumbered
  beyond removing Inv 4; no behaviour changed; existing E2E suite stays green.
  `feature.json` and `docs/spec.md` versions bumped to 0.7.1, `docs/contract.md`
  to 0.2.1.

- **v0.7.0 (retire live B/B vocabulary, #665, part of #420):** Reworded the
  one live bug-and-backlog ("B/B") prose reference in `docs/spec.md` to the
  current rabbit-issue vocabulary. The "What this feature does NOT define"
  bullet that read "Bug/backlog tracking on user-project code … rabbit's
  internal B/B system is reserved for rabbit-self development" now reads
  "Issue tracking on user-project code … rabbit-issue (rabbit-managed GitHub
  Issues) is reserved for rabbit-self development." No behaviour change;
  vocabulary only. Added `test/test-bb-vocab-retired.py` — an E2E content
  guard that scans `docs/spec.md` and `docs/contract.md` for live B/B tokens
  (with an allowlist for load-bearing literals) — wired into `test/run.py`.
  `feature.json` and `docs/spec.md` frontmatter versions bumped to 0.7.0 in
  lockstep.

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
