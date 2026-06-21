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
