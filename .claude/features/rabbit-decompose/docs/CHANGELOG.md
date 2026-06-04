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

- **v0.5.1 (housekeeping round 2 — measured line removal, #684 / #677 / #639):**
  Removal-not-reword pass over the feature's md surfaces under coding-rules §6
  (prove-it-dead-or-flag). Deletions, each verified: (1) the speculative
  "deferred `decomposer` subagent / `dispatch-decompose.py`" future-work prose,
  stated three times — `docs/spec.md` Surface, Tech Stack ("Future
  enhancement"), and Out of Scope; collapsed to the single remaining factual
  MVP statement (no such subagent/script exists — `grep -r decomposer` over the
  feature returns only these prose mentions). (2) The full multi-line
  two-level-nesting rationale duplicated across `docs/spec.md` Protocol step 4
  and Invariant 4; the canonical operational rationale lives in `SKILL.md`
  step 4B (which the E2E test pins), so the spec copies were collapsed to a
  reference + a tightened normative invariant — the constraint is still named
  on a surface and the E2E `test-step4b-no-nested-dispatch.py` stays green.
  (3) The redundant `## Tech Stack` prose section in `docs/contract.md` (the
  contract header instructs consumers to "ignore prose"; no contract check
  requires the section — `grep "Tech Stack"` over contract lib/scripts/tests
  is empty). The source `SKILL.md` body was left unchanged (no reword to
  manufacture a diff); only its frontmatter `version` moved in lockstep.
  Cross-feature `invokes`/`reads` claims were re-verified LIVE and KEPT
  (`scaffold-feature.py --batch`, `rabbit-feature-scaffold`, `rabbit-spec-create`
  all exist; `.rabbit/.runtime/mode` present). Frontmatter `version` bumped to
  0.5.1 across `feature.json`, `docs/spec.md`, `docs/contract.md`, and the
  source `SKILL.md` (four-way alignment); the deployed `.claude/skills/` copy
  needs a dispatcher republish because the source SKILL.md frontmatter version
  changed.

- **v0.5.0 (Step 4B nesting-safety fix, #646):** Corrected the spec-create
  hand-off in `SKILL.md` Step 4B. The step previously claimed
  `rabbit-spec-create` calls "can be run in parallel via the Agent tool for
  batch parallelism." That is architecturally invalid: `rabbit-spec-create`
  is itself a subagent-dispatching skill (it internally dispatches the
  `rabbit-spec-creator` subagent via the Agent tool), so wrapping it in an
  `Agent(...)` call creates a two-level subagent nesting chain
  (decompose -> Agent level-1 -> rabbit-spec-creator level-2) that Claude
  Code does not support — the level-2 dispatch is blocked. The fix rewrites
  Step 4B to invoke `rabbit-spec-create` as sequential `Skill(...)` calls
  from the main session (keeping `rabbit-spec-creator` at level-1) and
  removes the illegal Agent-parallelization claim. The same correction is
  reflected in `docs/spec.md`'s hand-off prose, plus a new spec invariant
  (rabbit-decompose namespace) stating the spec-create hand-off MUST be a
  sequential `Skill(...)` call and MUST NOT be wrapped in `Agent(...)`. A
  new E2E test (`test/test-step4b-no-nested-dispatch.py`) pins both
  surfaces: no Agent-parallelization claim, sequential wording present, and
  the two-level-nesting constraint named. Frontmatter `version` bumped to
  0.5.0 across `feature.json`, `docs/spec.md`, `docs/contract.md`, and the
  source `SKILL.md` (four-way alignment); the deployed `.claude/skills/`
  copy needs a dispatcher republish because the source SKILL.md changed.

- **v0.4.0 (history-free doc surfaces + Inv 49 strict tier, #551 / #530
  Phase 2):** Opted rabbit-decompose into the contract's strict-tier
  historical-burden check by declaring top-level `"housekeeping_clean": true`
  in `feature.json` (data-driven opt-in; no contract-owned file edited).
  Scrubbed the one strict-tier hit: `docs/spec.md` Tests section carried a
  trailing historical parenthetical naming the migration ticket that produced
  the flat-layout test. The parenthetical was removed and the sentence left as
  a present-tense declarative statement; the substantive test description (flat
  `docs/` layout, four-way version alignment, contract-resolver resolution) is
  unchanged. The genuinely-historical migration note already lives in this
  CHANGELOG (v0.3.0 entry below), which is exempt from the doc-surface scan by
  construction. Frontmatter `version` bumped to 0.4.0 across `feature.json`,
  `docs/spec.md`, `docs/contract.md`, and the source SKILL.md (four-way
  alignment); the deployed `.claude/skills/` copy needs a dispatcher republish
  because the source SKILL.md frontmatter version changed. No invariants were
  renumbered or removed; only the historical wrapper text was stripped.

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
