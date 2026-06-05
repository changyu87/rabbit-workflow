---
feature: policy
owner: rabbit-workflow team
deprecation_criterion: when the policy feature is retired (Claude Code exposes a native subagent-policy injection point) or its history is folded into a structured schema-tracked log
---

# policy — CHANGELOG

## Version notes

- **v1.21.0 (measured verify-or-flag reduction wave, #808; child of #794):**
  Ran a coding-rules §6 (prove-it-dead-or-flag), §2 (Simplicity First), and §7
  (Parenthetical Clarity) reduction pass over the whole policy feature
  (`philosophy.md`, `spec-rules.md`, `coding-rules.md`, `docs/spec.md`,
  `docs/CHANGELOG.md`). Honest measured result: **zero normative prose
  removed.** Every clause in the three canonical rule files is load-bearing —
  these are NORMATIVE governance documents injected wholesale into the repo
  CLAUDE.md via the three policy `@`-imports and cited verbatim by other
  features' SKILL.md files (Verbatim Policy Embedding), so every numbered
  section, rule clause, citation, and code token is consumed in-place.
  Every parenthetical was classified under §7 and found load-bearing (a
  precise clarifying term, an example list that constrains scope, a code token
  like `Agent(prompt=...)`, or a citation like `(Inv 49)` — exactly the
  load-bearing class §7 keeps inline). Cross-surface redundancy in
  `docs/spec.md` had already been collapsed to its one authoritative home by
  the #618/#680 passes, so no second-copy prose remained to cut. No candidate
  reached the "proven dead" bar; nothing was unverifiable enough to FLAG
  (every claim resolved to proven-live via the on-disk rule files and the
  `test/test-rule-files-content.py` phrase guard). A new E2E guard
  `test/test-housekeep-808-docs-already-tight.py` records the decision so a
  future over-zealous pass cannot silently delete the load-bearing
  parenthetical/citation exemplars this wave verified-and-kept. This is the
  expected outcome for a content-only governance feature already through two
  prior reduction rounds: a near-zero delta with everything verified-and-kept
  is the success condition, not a failure.
- **v1.20.0 (add rabbit-housekeep to the subagent-dispatching named set,
  #730):** rabbit-housekeep is a subagent-dispatching skill — it decomposes
  per-feature housekeeping work and dispatches subagents. Per spec-rules §4
  "No Subagent-Dispatching Skill Inside `Agent()`", the authoritative named
  set MUST list every known subagent-dispatching skill, so spec-rules.md §4
  now names `rabbit-housekeep` alongside `rabbit-spec-create`,
  `rabbit-feature-touch`, and `rabbit-feature-scope`. The
  `test/test-rule-files-content.py` content guard asserts the new member.
- **v1.19.0 (opt into contract strict contiguous-invariant tier, #739 /
  #724 follow-up):** policy/feature.json now declares
  `"contiguous_invariants": true`, opting policy into the contract strict
  tier added by #724 (`check_invariant_monotonic_order`), which enforces
  that the `## Invariants` section is numbered contiguously 1..N with no
  holes. No reflow was needed — policy's numbering was already contiguous
  (the spec body's invariants are 1..N under contract parsing semantics).
  A new per-feature guard `test/test-contiguous-invariants-optin.py`
  asserts both the opt-in flag and contiguity using the same parsing
  semantics as the contract gate, so local drift is caught before the
  contract suite reddens. Mirrors the Inv 41 `housekeeping_clean`
  strict-tier opt-in pattern; single-feature, self-verifying touch with no
  deployed surface (policy has none).

- **v1.18.0 (parenthetical-clarity guideline, #638):** Added §7
  "Parenthetical Clarity" to `coding-rules.md`: prefer declarative sentences
  over parenthetical asides; for each aside, fold a load-bearing one into the
  sentence (or promote it to its own sentence) and drop a redundant one. The
  rule is framed as a clarity GUIDELINE, NOT an absolute ban — load-bearing
  parentheticals (precise terms, citations like `(Inv 49)`, code tokens)
  remain acceptable inline, and the guideline does not mandate a sweep of
  existing prose. This implements the SOFTENED intent of the retitled issue
  (the original body proposed a hard ban; the retitle scoped it to a clarity
  guideline). `test-rule-files-content.py` now asserts the §7 heading and its
  fold/drop/not-a-ban/load-bearing anchor phrases.

- **v1.17.0 (register rabbit-feature-scope as a subagent-dispatching skill, #690):**
  Broadened §4's "No Subagent-Dispatching Skill Inside `Agent()`" rule to cover
  UNTYPED default-model dispatches (`Agent(prompt=...)` with no `subagent_type`),
  not only typed `Agent(subagent_type=...)` ones, and added `rabbit-feature-scope`
  (which dispatches an untyped default-model Agent) to the authoritative named
  set of known subagent-dispatching skills (was `rabbit-spec-create`,
  `rabbit-feature-touch`). The named set is now declared authoritative and any
  future such skill MUST be added to it. Audit confirmed the set of three is
  complete: a repo-wide grep for `Agent(` in SKILL.md bodies surfaced only these
  three genuine dispatchers (`rabbit-decompose` merely warns against wrapping,
  it does not dispatch). `test-rule-files-content.py` now asserts both the
  `rabbit-feature-scope` name and the `Agent(prompt=...)` untyped-dispatch
  coverage.

- **v1.16.0 (housekeeping round 2 — measured spec redundancy removal, #680):**
  Measured line-removal pass under #639 prove-it-dead-or-flag, per #677's
  mandate to remove (not reword) cross-surface redundancy. `docs/spec.md`
  163 → 146 lines (17 removed). Three invariants collapsed their bodies to the
  normative skeleton (presence requirement + authoritative-source pointer +
  enforcing test), with the full rule text preserved in its single
  authoritative home:
  - Inv 6 — dropped the cross-feature provenance narration ("propagates the
    lesson of rabbit-feature's spec-edit Read-before-Edit obligation … remains
    stable across rabbit-feature renumbers"); the normative named-not-numbered
    directive survives.
  - Inv 12 — dropped the verbatim re-description of the four #639 check kinds,
    the three-row action table, and the annotate-and-continue discipline. That
    text is authoritative in `coding-rules.md` Section 6 (session-injected) and
    every distinctive phrase is already asserted by
    `test/test-rule-files-content.py`. The spec keeps the presence requirement
    and the enforcing-test pointer.
  - Inv 13 — dropped the verbatim re-description of the no-nesting rule
    (illegal two-level nesting, dispatch-at-level-1, named skills). That text
    is authoritative in `spec-rules.md` Section 4 and is content-guard-tested.
    The spec keeps the presence requirement and the enforcing-test pointer.
  No invariant added/renumbered/removed; no numbering gap; `docs/contract.md`
  JSON boundary unchanged. New E2E regression
  `test/test-spec-housekeeping-680-dead-prose-removed.py` (wired into
  `test/run.py`) asserts each removed phrase is absent AND each surviving
  normative anchor is present; RED on all seven pre-edit phrases, GREEN after.
  Four-way version bump (feature.json + docs/spec.md + docs/contract.md +
  this entry). Policy stays within the Inv 49 strict tier. Contract suite GREEN.

- **v1.15.0 (no-nesting authoring rule, #647):** Added a
  **No Subagent-Dispatching Skill Inside `Agent()`** bullet to the
  "SKILL.md Authoring Standard" section of `spec-rules.md`. The rule codifies
  that a skill whose body dispatches a subagent (any `Agent(subagent_type=...)`
  call) MUST NOT itself be invoked inside an `Agent()` call, since that creates
  illegal two-level nesting (`main → Agent level 1 → subagent level 2`)
  unsupported by Claude Code. It directs that parallelization be done by
  dispatching the underlying subagent directly at level 1
  (`main → N parallel subagents`) through shared `scripts/`, not by wrapping the
  skill in parallel `Agent()` calls, and names the known subagent-dispatching
  skills (`rabbit-spec-create`, `rabbit-feature-touch`) plus the
  inheritance clause for future such skills. New `docs/spec.md` Invariant 13
  pins the rule's presence; `test/test-rule-files-content.py` asserts its
  distinctive phrases. Rule text is declarative and history-free, keeping policy
  within the Inv 49 strict tier.

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
