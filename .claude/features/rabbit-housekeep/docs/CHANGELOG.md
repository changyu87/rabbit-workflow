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

- **v0.9.0 (single governed TDD cycle for the per-feature spec reduction, issue #1189):**
  Documents on the housekeep surfaces that a measured reduction wave's
  per-feature spec reduction now rides ONE governed RED->GREEN cycle. The
  `housekeep: measured reduction wave` request rabbit-housekeep already
  dispatches is the exact signal rabbit-feature-touch's reduction-wave
  detection keys on, so feature-touch threads the spec-reduction intent into
  the dispatch and the TDD subagent authors BOTH the spec reduction AND its
  gating test inside the single cycle — with no dispatcher pre-commit of the
  spec outside the cycle and no forced no-spec-change escape hatch. The
  substantive behavior is delivered transitively by the rabbit-spec /
  rabbit-feature prerequisites; this wave is the honest housekeep-side
  acknowledgment plus a regression guard. New test
  `test/test-reduction-single-tdd.py` pins the signal match, the absence of
  the retired escape-hatch reference, and the single-TDD framing. No script or
  behavior change in rabbit-housekeep itself.

- **v0.8.0 (gated wave auto-merge for user-installed runs, issue #1191):** A
  user-installed `/rabbit-housekeep` run no longer leaves a green wave's PR
  pending for the user to merge by hand. The wave still CREATES its PR through
  the rabbit-feature-touch path for the audit trail; on green gates it is now
  AUTO-MERGED to `main` (default-ON, with a `--no-automerge` opt-out), and a
  wave that fails any gate leaves its PR OPEN exactly as before. New companion
  script `scripts/wave-automerge.py` owns the script-tier decision (spec-rules
  §4 Script-Backed Orchestration): `decide` reads a JSON gating payload — the
  HANDOFF gates (`tdd_state`/`test_result`/`spec_compliance`), the
  honest-reduction `verdict`, and the PR-side `mergeable`/`merge_state_status`/
  `ci_status` — and emits `decision: merge` ONLY when ALL hold (a `no-op` verdict
  is a PASSING outcome, per the honest-gate semantics), else `leave-open` with
  each failing gate NAMED in `reasons`; `gather --pr <N>` collects the PR-side
  signals via `gh pr view`. The auto-merge step is HOUSEKEEP-SPECIFIC — added to
  rabbit-housekeep's OWN flow as Step 8, AFTER the rabbit-feature-touch
  invocation returns a created PR — so feature-touch's PR-only behavior is
  unchanged for every other feature. No shared trust-mode config exists today to
  reuse (safety-governance and rabbit-cage carry no `auto-merge`/`gated-merge`
  key); aligning the opt-out with a future shared trust-mode config is noted as a
  follow-up. Added SKILL.md Step 8 + the wave-automerge.py interface section,
  spec Surface/Gated-wave-auto-merge/wave-automerge.py sections + invariant #12,
  the contract `provides.scripts` entry, command `--no-automerge` usage + Step 3
  note, and new gate `test-wave-automerge.py` (10 cases, gh-free via in-payload
  signals). `test-reduction-wave.py` doc-surface ceiling refreshed for the
  additive growth (SPEC 296->367, CONTRACT 90->91, SKILL 338->384, total
  724->842) with the new load-bearing tokens added. `wave-automerge.py` is a NEW
  skill-referenced script, so rabbit-cage's vendored-install closure
  (`FEATURE_INCLUDES['rabbit-housekeep']` + the skill-referenced-scripts gate)
  needs a follow-up update owned by rabbit-cage; filed as a discovered issue.
  feature/spec/contract/SKILL/command versions bumped 0.7.0 -> 0.8.0 in lockstep
  (Inv 11). SKILL.md + command `.md` are publish surfaces — their deployed copies
  drift until the dispatcher republishes. Closes #1191.

- **v0.7.0 (honest gate + opt-in code dimension, issue #1190):** Two coupled
  changes. CHANGE A (honest gate): the wave's reduction gate changed from
  "must reduce" to "reduce IF there is dead/redundant/simplifiable content,
  else honestly report a no-op / already-clean verdict." `measure-reduction.py
  diff` now emits a `verdict` field (`reduced` when content was removed, else
  `no-op`) alongside the existing `reduced` boolean; reduction is REPORTED, not
  MANDATED. The ONE MANDATORY gate is now behavior preserved (the feature's
  existing test suite stays green). SKILL.md Steps 4/6/7, the "What you do NOT
  do" list, spec Purpose/Methodology/Waves and invariant #5, and the contract
  `never` block were updated so an already-lean feature passes honestly instead
  of being forced into a reword. CHANGE B (opt-in code dimension): added a
  `--code` selector to `measure-reduction.py count` (a new `_iter_code_surfaces`
  that scopes a directory argument to `src/**/*.py`, mutually exclusive with
  `--docs-only`) and a new SKILL.md "OPT-IN code dimension" section. The code
  dimension keeps the DOC dimension as the default and runs, in priority order,
  SIMPLIFY (via the in-environment `code-simplifier` agent, declared in
  `docs/contract.md` `invokes.agents`), then DEAD CODE removal (coding-rules §6
  grep-for-callers on `src/` symbols; none = dead → remove, unverifiable →
  FLAG), then honest measured REDUCTION — all through the governed TDD path with
  the existing test suite as the zero-behavior-loss gate. Added spec invariant
  #11 (code dimension) and command `--code` usage. New test cases `t8`
  (verdict no-op/reduced) and `t9` (`count --code` scopes to `src/`) in
  `test-measure-reduction.py`. `measure-reduction.py` script Version 0.2.0 ->
  0.3.0; feature/spec/contract/SKILL/command versions bumped 0.6.0 -> 0.7.0 in
  lockstep (Inv 11). SKILL.md + command `.md` are publish surfaces — their
  deployed copies drift until the dispatcher republishes. NOTE: rabbit-housekeep
  is still absent from rabbit-cage's vendored install closure (the v0.5.0 known
  gap), so no new src-scoped behavior ships in a vendored install yet; the
  `--code` flag is additive and the default whole-tree / `--docs-only` walks are
  unchanged. Closes #1190.

- **v0.6.0 (doc-scoped measurement so the mandated test does not flip the
  verdict, issue #1187):** `measure-reduction.py count` walked the ENTIRE
  feature directory, so the +157-line housekeeping e2e test plus baseline
  fixture a wave MUST add in Step 6 outweighed the genuine doc-surface
  reduction — Step 7's whole-feature diff reported `reduced: false` even when
  `docs/spec.md` and `docs/contract.md` were genuinely slimmed, contradicting a
  successful wave. FIX adds an ADDITIVE `--docs-only` flag to `count` that
  restricts a directory argument to the DOC SURFACES a wave slims
  (`docs/spec.md`, `docs/contract.md`, `skills/*/SKILL.md`), excluding `test/`
  and `docs/CHANGELOG.md` (a wave GROWS the changelog by design). The default
  whole-tree walk is unchanged, so the install-closure and any other caller
  that relies on it is unaffected. SKILL.md Steps 3 and 7 now snapshot with
  `--docs-only` on the SAME doc-scoped baseline so the operator's
  confirm-success command and the Step-6 in-test gate agree, and Step 6's
  test-authoring guidance is aligned. New test case `t7` in
  `test-measure-reduction.py` pins the failure mode: docs shrink, a test file
  is added, whole-tree diff = `reduced: false`, doc-scoped diff =
  `reduced: true`. `test-reduction-wave.py` ceiling refreshed
  (SPEC 255->266, SKILL 258->269, total 599->621) for the additive doc growth,
  and `--docs-only` added to its load-bearing token set. Inv 5 extended to
  mandate the flag. `measure-reduction.py` script Version 0.1.0 -> 0.2.0;
  feature/spec/contract/SKILL/command versions bumped 0.5.1 -> 0.6.0 in
  lockstep (Inv 11). SKILL.md + command `.md` are publish surfaces — their
  deployed copies drift until the dispatcher republishes. Closes #1187.

- **v0.5.1 (neutralize loop-only script reference on the deployed surface,
  issue #1182):** Removed the live invocation of the loop-only
  `.claude/features/rabbit-auto-evolve/scripts/record-decomposition.py` from
  the SKILL.md Step 2 decompose block. rabbit-auto-evolve is the self-driving
  loop feature, deliberately ABSENT from rabbit-cage's vendored install
  closure; a literal `.claude/features/rabbit-auto-evolve/scripts/<x>.py` path
  in a shipped SKILL.md body is treated as a referenced-but-missing backing
  script by both rabbit-cage gates (test-feature-includes-scripts-closure.py /
  Inv 24 and test-install-ships-skill-referenced-scripts.py / #897+#1035),
  which would fail once the SKILL ships in the vendored closure (#1181). The
  block now states in prose that parent→children linkage recording is
  loop-only machinery handled automatically by the auto-evolve loop, not a
  user step; the cross-feature reuse stays declared in `docs/contract.md`
  (`invokes.scripts`), which the gates do not scan. Net SKILL.md reduction of
  one line (the measured-reduction ceiling holds). Added
  `test/test-no-loop-only-script-ref.py`, which mirrors the rabbit-cage
  scanner regex against the SOURCE SKILL.md and asserts no non-shipped
  loop-only script reference survives. No user-facing behavior change; the
  command surface is unchanged.

- **v0.5.0 (user-facing command + consuming-project scope, issue #1179):**
  Exposed rabbit-housekeep on the user-facing invocation surface and anchored
  the wave on the CONSUMING PROJECT. Added the `/rabbit-housekeep` command
  (`commands/rabbit-housekeep.md`, six-key frontmatter, owner
  `rabbit-workflow team`, lockstep version) as a THIN entry point that resolves
  scope deterministically then hands off to the skill, honoring the
  no-Agent()-nesting constraint. Added `scripts/resolve-housekeep-scope.py`
  (`list` / `paths`), a mode-aware resolver that enumerates the consuming
  project's features — `rabbit-project/features/*` in a vendored install
  (EXCLUDING rabbit's own `.claude/features/*`) and `.claude/features/*`
  standalone — deliberately differing from `contract/find-feature.py`, which
  returns BOTH sets. Wired the manifest with a `publish_command` entry and named
  both new artifacts in `surface`/`provides`. Updated the SKILL.md to document
  consuming-project targeting and reference the scope script, refreshed the
  `test-reduction-wave.py` doc-surface ceiling for the additive growth, and
  added spec invariants #9 (command) and #10 (scope resolution) plus a new E2E
  gate `test-user-facing-surface.py`. KNOWN GAP (cross-scope, flagged for a
  follow-up): the vendored installer closure is HARDCODED in rabbit-cage's
  `install.py` (SKILLS / COMMANDS / FEATURE_INCLUDES) and does NOT include
  rabbit-housekeep, so a fresh vendored install still ships none of these files;
  adding the rabbit-housekeep closure entries is owned by rabbit-cage and is out
  of this feature's scope. The deployed `.claude/skills/` + `.claude/commands/`
  copies need a dispatcher republish because the source SKILL.md changed and a
  new command was added.

- **v0.4.0 (illustrative-example scanner exemption, issue #869):** Resolved a
  self-flag: `scripts/check-script-backed.py`, run against rabbit-housekeep
  itself, flagged three `runtime-placeholder` findings in the SKILL.md's OWN
  example invocation bash blocks (the measure-reduction / check-script-backed
  snippets carrying `<name>` slots). Those are illustrative snippets shown to
  document how to invoke the scripts, not live orchestration steps the model
  assembles at invocation time. Applied the preferred narrow scanner exemption:
  the scan now skips any fenced bash block carrying an `<!-- example -->` marker
  on the line directly above its opening fence. The exemption is NARROW — it
  must sit on the immediately-preceding line, so an unmarked live step with a
  placeholder STILL flags; it does not weaken detection of real orchestration
  steps. Marked the three illustrative SKILL.md blocks accordingly, so a
  self-scan now reports zero findings. Extended `test-check-script-backed.py`
  with three cases (a marked example is skipped, a mixed file flags only the
  unmarked live step, and the real SKILL.md self-scans clean) and refreshed the
  `test-reduction-wave.py` doc-surface ceiling for the additive growth. Spec
  invariant #7 and the check-script-backed.py section now document the marker.
  The deployed `.claude/skills/` copy needs a dispatcher republish because the
  source SKILL.md changed.

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
