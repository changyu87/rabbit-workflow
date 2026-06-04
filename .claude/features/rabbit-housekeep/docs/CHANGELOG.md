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
