---
feature: policy
owner: rabbit-workflow team
deprecation_criterion: when the policy feature is retired (Claude Code exposes a native subagent-policy injection point) or its history is folded into a structured schema-tracked log
---

# policy — CHANGELOG

## Version notes

- **v1.14.0 (prove-it-dead-or-flag cleanup methodology, #639):** Added
  `coding-rules.md` Section 6 "Cleanup: Prove It Dead or Flag It", encoding the
  housekeeping definition-of-done methodology as a durable, declarative rule.
  The rule redefines a cleanup pass's "done" so it removes dead-but-plausible
  content, not only syntactically-tagged historical burden: every claim is
  resolved by a deterministic VERIFICATION check (`find` for paths, `grep` for
  symbols, reachable-path/test for behaviors, direct inspection for
  cross-feature claims), routed through a three-row action table (proven dead →
  DELETE; proven live → KEEP; unverifiable → FLAG a `housekeeping`-tagged
  sub-issue), with annotate-and-continue so one uncertain sentence never stalls
  a feature's cleanup. New `docs/spec.md` Invariant 12 pins the rule's
  presence; `test/test-rule-files-content.py` asserts its distinctive phrases.
  Rule text is declarative and history-free (no issue/PR refs, no tombstone
  language), keeping the policy feature within the Inv 49 strict tier.

- **v1.13.0 (history-free doc surfaces + opt into Inv 49 strict tier, #547 /
  Housekeeping Phase 2):** Opted the policy feature into the contract Inv 49
  STRICT housekeeping tier by declaring top-level `"housekeeping_clean": true`
  in `feature.json`. To satisfy the strict tier, two tombstone-flavoured
  phrasings in `docs/spec.md` were rephrased to non-tombstone wording WITHOUT
  changing the substantive behaviour they describe:
  - Invariant 2's title "Retired file absent" became "Legacy rule file absent"
    (the invariant still requires that `workflow-rules.md` does NOT exist
    anywhere within the feature directory).
  - Invariant 8's deletion-criterion clause "the file is retired once
    `test/test-policy-invariants.py` carries a `# Subsumes:` marker …" became
    "the file is removed once …" (same observable condition; only the verb
    changed from the tombstone word "retired" to "removed").

  No invariant was renumbered or removed; no rule meaning changed. The strict
  check (`contract/test/test-spec-bodies-no-historical-tags.py`) now self-
  verifies the policy doc surfaces are history-free, and the full repo-wide
  contract gate (`contract/test/run.py`) stays green. Lockstep minor bump
  across `feature.json`, `docs/spec.md`, and `docs/contract.md`.

- **v1.12.0 (convention text names flat `docs/` home, #399 Phase 3a):**
  Updated the policy convention text so the canonical "Where the metadata
  lives" rule names the flat `docs/` layout that every feature now uses.
  `spec-rules.md` (the "Specs / contracts" bullet) now names `docs/spec.md`,
  `docs/contract.md`, and `docs/CHANGELOG.md` as the metadata home;
  `philosophy.md` §2 (Bounded Scope) now references the contract schema at
  `docs/contract.md`. The legacy spec-directory paths are no longer named as
  the canonical location. No rule meaning changed — only the path the
  convention names. The `test/test-canonical-convention-text.py` E2E guard was
  flipped to assert the flat `docs/` paths and the absence of the legacy
  spec-directory home. Lockstep minor bump across `feature.json`,
  `docs/spec.md`, and `docs/contract.md`.

- **v1.11.0 (flat `docs/` layout migration, #399 Phase 2b):** Relocated the
  policy feature's documentation surfaces from the legacy spec directory to the
  flat `docs/` layout. `specs/spec.md` → `docs/spec.md` and
  `specs/contract.md` → `docs/contract.md` were moved via `git mv` (history
  preserved); the now-empty spec directory was removed. This fresh
  `docs/CHANGELOG.md` was created to hold the migration note. The spec and
  contract bodies are unchanged — only their on-disk location moved.
  Frontmatter `version` was bumped in lockstep across `feature.json`,
  `docs/spec.md`, and `docs/contract.md`. The contract resolver
  (`resolve_spec_path` / `resolve_changelog_path`) already prefers the flat
  `docs/` layout and falls back to the spec directory, so the migration is
  invisible to every cross-feature consumer. The two layout E2E tests
  (`test/test-spec-layout-migration.py`, `test/test-canonical-convention-text.py`)
  were updated to assert the flat `docs/` reality.
