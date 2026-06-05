---
feature: rabbit-housekeep
owner: rabbit-workflow team
deprecation_criterion: when rabbit-housekeep's version history is folded into a structured schema-tracked log
---

# rabbit-housekeep — Changelog

Version-keyed change log for the rabbit-housekeep feature. The version here
tracks the spec version declared in `docs/spec.md` / `docs/contract.md`
frontmatter, the `version` field in `feature.json`, and the source
`skills/rabbit-housekeep/SKILL.md` frontmatter (four-way lockstep).

## Version notes

- **v0.3.0 (script-backed-orchestration verify-or-flag dimension, issue
  #862):** Added a NEW verification DIMENSION enforcing the spec-rules §4
  Script-Backed Orchestration standard. New companion script
  `scripts/check-script-backed.py` (`scan <feature-dir>`) deterministically
  walks a target feature's `skills/*/SKILL.md`, `agents/*.md`, and
  `commands/*.md` bodies and reports, as JSON (`findings` + `count`), every
  orchestration step that is NOT script-backed: a bash block carrying runtime
  placeholders (e.g. `<feature-name>`, `<branch-name>`) the model assembles at
  invocation time, or a computed-value / mode-aware-branching step held as
  prose or inline bash instead of a companion `scripts/` invocation. The §4
  read-only-informational exception holds: simple read-only informational
  commands inline (e.g. `git log --oneline -5`) and trivial one-liners are NOT
  flagged. Detection is SCRIPT-tier (the check enforces the same tier it
  embodies). The disposition reuses housekeep's existing prove-it-dead-or-flag
  machinery — each non-conformant step is FLAGged as a `housekeeping`-tagged
  sub-issue naming the file, the step, and the conversion target. The SKILL.md
  now embeds spec-rules §4 verbatim (byte-for-byte) and documents the new
  dimension. Added spec invariants #7 (the scan script) and #8 (the verbatim
  §4 embed + dimension documentation), extended invariant #6 to name the new
  script under `provides`, and added a new E2E gate
  `test-check-script-backed.py`. The new step was renumbered into the flat
  numeric sequence (Steps 5/6/7) to satisfy the cross-feature numbered-lists
  convention, which forbids letter-suffixed step numbers. The deployed
  `.claude/skills/` copy needs a dispatcher republish because the source
  SKILL.md changed.

- **v0.2.1 (machine-readable rabbit-decompose INVOKE, issue #822):**
  Declared the rabbit-decompose decomposition-shape reuse in the
  machine-readable `invokes.skills` block of `docs/contract.md`. Previously
  this cross-feature reuse lived only in trailing prose after the JSON block,
  violating Machine First (philosophy §1): a consumer reading the structured
  contract could not see the relationship. The file-item.py filing call and
  record-decomposition.py parent-close call were already in `invokes.scripts`;
  rabbit-decompose was the missing machine declaration. Reduced the trailing
  prose to the derived human view (it no longer re-declares the reuse).
  Tightened spec invariant #6 to require every reuse be declared in the
  machine block, never in prose only. Added a new E2E gate,
  `test-contract-invokes.py`, that parses the contract JSON and asserts each
  declared INVOKE (skill / script) is present and resolves to a real file on
  disk, and that the rabbit-decompose reuse is not prose-only. The deployed
  `.claude/skills/` copy needs a dispatcher republish because the source
  SKILL.md frontmatter version changed.

- **v0.2.0 (measured-reduction housekeeping wave, issue #813):** Ran the
  feature's own measured verify-or-flag reduction wave against its doc
  surfaces (`docs/spec.md`, `docs/contract.md`,
  `skills/rabbit-housekeep/SKILL.md`). Every claim was resolved by a
  deterministic check; all were proven-live and KEPT, so the wave removed
  redundant restatement, restated rationale, and decorative parentheticals
  only — no behavior, invariant, schema field, exit code, script name, or
  cross-reference was dropped. The verbatim coding-rules.md §6 embed was left
  byte-faithful. Doc surfaces went from 427 to 411 lines (−16). Added a new
  E2E gate, `test-reduction-wave.py`, that drives `measure-reduction.py`
  `count`/`diff` against the live doc surfaces and asserts both the measured
  reduction (`reduced: true`) and load-bearing-token survival. No
  unverifiable claims were found, so no `housekeeping`-tagged sub-issues were
  filed. The deployed `.claude/skills/` copy needs a dispatcher republish
  because the source SKILL.md changed.

- **v0.1.0 (initial feature, issue #730):** New `rabbit-housekeep` feature
  that distills the proven housekeeping-wave methodology — especially the
  slim / line-reduction work — into a first-class, repeatable capability.
  Manifests ONE skill, `rabbit-housekeep`, that runs measured verify-or-flag
  housekeeping in complexity-sized waves, decomposes cross-feature/repo-wide
  scope into per-feature TDD touches, and reports measured reduction with
  zero behavior loss. Ships a deterministic measurement script
  (`scripts/measure-reduction.py`: per-artifact line accounting + before/after
  diff with a `reduced` verdict). The SKILL.md embeds coding-rules.md §6
  ("Cleanup: Prove It Dead or Flag It") verbatim and documents the
  subagent-dispatching no-Agent()-nesting constraint. The contract declares
  the cross-feature reuse: tdd-subagent (TDD execution via
  rabbit-feature-touch), rabbit-decompose (decomposition shape), rabbit-issue
  `file-item.py` (sub-issue filing), and rabbit-auto-evolve's
  `record-decomposition.py` / `close-decomposed-parents.py` (deterministic
  parent-close). The feature opts into the contract suite's strict-tier
  historical-burden check (`housekeeping_clean: true`) and contiguous
  invariant numbering (`contiguous_invariants: true`). Two E2E tests:
  `test-measure-reduction.py` (measurement correctness + reduction verdict)
  and `test-skill-structure.py` (skill present + verbatim §6 embed +
  nesting constraint documented). rabbit-housekeep is a subagent-dispatching
  skill and is added to the authoritative named set in spec-rules.md by the
  policy follow-up; the deployed `.claude/skills/` copy needs a dispatcher
  republish because a new source SKILL.md was added.
