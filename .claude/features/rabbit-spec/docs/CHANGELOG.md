---
feature: rabbit-spec
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-spec spec's invariant numbering is folded into a structured schema-tracked log
---

# rabbit-spec — Retired Invariants Log

This file holds the tombstones for invariants previously declared in the feature spec and since retired, plus version notes for notable non-retirement changes.

Each retirement entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the cascade or backlog ID that drove the retirement.

## Retired invariants

- **Inv 4 (retired v1.17.0, #922): `skills/rabbit-spec-create/SKILL.md`
  existence + 4-step orchestration protocol.** The rabbit-spec-create skill
  wrapper is retired: the `rabbit-spec-creator` subagent now drafts AND writes
  its own `docs/spec.md` and an orchestrator dispatches it directly (after
  assembling the prompt with `scripts/dispatch-spec-creator.py`). With no skill
  wrapper there is nothing for this invariant to assert. Surviving invariants
  5..9 were renumbered to close the hole (now 4..8); numbering stays contiguous
  1..8. The skill source dir was removed; the deployed copy
  `.claude/skills/rabbit-spec-create/` and rabbit-cage's `install.py` listing
  are removed by the rabbit-cage piece of #922.

## Version notes

- **v1.19.0 (bug #1066 — pin spec-create prompt to the single-`.rabbit`
  runtime root):** `scripts/dispatch-spec-creator.py` invokes
  `contract/scripts/build-prompt.py`, which unconditionally joins
  `<its repo_root>/.rabbit/prompts/...`. In a vendored install the session
  exports `RABBIT_ROOT=<host>/.rabbit`, so build-prompt's join DOUBLED to
  `<host>/.rabbit/.rabbit/prompts/...`, splitting assembled prompts off the
  single-`.rabbit` runtime root every other writer/reader (SessionStart,
  scope-guard) uses. FIX: after build-prompt returns, the dispatcher resolves
  the canonical runtime root via rabbit-cage's `rabbit_runtime_root`
  (`.claude/features/rabbit-cage/lib/runtime_root.py`, Inv 52, #1046),
  lazy-imported with the `importlib.util` cross-feature INVOKE pattern
  rabbit-cage's session-start dispatcher establishes, and RELOCATES the prompt
  to `<runtime_root>/prompts/` when build-prompt wrote it elsewhere, printing
  that canonical path. Idempotent: in standalone mode build-prompt already
  writes the canonical path and no move occurs. Inv 3 gains clause (f) stating
  the canonical-prompts-dir + relocation rule; clause (d)'s stdlib list gains
  `shutil` + `importlib.util`. `contract.md` `invokes.scripts` gains the
  rabbit-cage `runtime_root.py` invoke. Added enforcing E2E tests
  `test/test-dispatch-prompt-path-no-double-rabbit.py` (vendored layout with
  `RABBIT_ROOT=<host>/.rabbit` → single-`.rabbit` path, file present) and
  `test/test-dispatch-prompt-path-standalone.py` (standalone → canonical path,
  no relocation). `dispatch-spec-creator.py` module version 2.0.0 -> 2.1.0.
  Numbering stays contiguous 1..8. Version quad bumped 1.18.0 -> 1.19.0
  (feature.json + spec.md + contract.md frontmatter + this note).

- **v1.18.0 (bug #1043 — rabbit-spec-update dual-accept the `vendored` mode
  marker):** After the #980 plugin->vendored rename, `write_mode_marker`
  writes `vendored` (the value `detect_mode` now returns) verbatim to
  `.rabbit/.runtime/mode`. The `rabbit-spec-update` SKILL.md `## Modes` section
  recognized only `standalone` and `plugin`, so following it literally a
  `vendored` marker matched neither and fell through to the standalone path,
  resolving `feature_root` to `.claude/features/<name>/` instead of the
  vendored `.rabbit/rabbit-project/features/<name>/` and aborting at Step 1 (or
  silently targeting the wrong path). Inv 4 now requires the body to
  dual-accept BOTH `vendored` (canonical) and the legacy `plugin` for the
  vendored branch — the same `_VENDORED_MODES = ("vendored", "plugin")`
  coexistence idiom every contract reader uses; the legacy `plugin` acceptance
  drops only once no install carries the older marker spelling. SKILL.md body
  `## Modes` section rewritten (v2.7.0 -> v2.8.0), `feature_root` definition
  updated to name the vendored branch. Added enforcing test
  `test/test-rabbit-spec-update-vendored-mode.py` (asserts the body mentions
  `vendored` and places every `vendored` mention in the vendored/plugin branch
  context). Inv 4 "Enforced by" clause extended to cite it. No invariants
  renumbered or retired; numbering stays contiguous 1..8. Four-way version
  alignment bumped spec.md/contract.md/feature.json 1.17.0 -> 1.18.0. Deployed
  `.claude/skills/rabbit-spec-update/SKILL.md` republished in this cycle.
  Source SKILL.md change requires skill-creator validation; skill-creator was
  invoked but the targeted dual-accept edit was applied directly (no eval-loop
  rerun) given the constrained, test-pinned scope.

- **v1.17.0 (#922 retire the rabbit-spec-create skill wrapper):** Renamed
  `scripts/dispatch-spec-create.py` -> `scripts/dispatch-spec-creator.py` (git
  mv; name now matches the subagent it serves) and bumped it 1.2.0 -> 2.0.0.
  Upgraded `agents/rabbit-spec-creator.md` 1.2.0 -> 2.0.0: granted `Write` +
  `Explore` (no longer read-only), mandated `docs/spec.md` as its SOLE write
  target, mandated Explore-superpower codebase reading, and mandated a
  contracted `{path_written, summary}` handoff (the subagent writes the spec
  itself and never echoes the full body — context isolation for the
  orchestrator). Removed the `skills/rabbit-spec-create/` skill source, its
  `feature.json` `surface.skills` + `publish_skill` manifest entries, and Inv 4
  (renumber 5..9 -> 4..8). Four-way version bump (feature.json + spec.md +
  contract.md + dispatch-spec-creator.py docstring; the surviving
  rabbit-spec-update SKILL.md is on its own lineage and unchanged this cycle).
  Deployed-surface deltas: republish `agents/rabbit-spec-creator.md`; the
  retired `.claude/skills/rabbit-spec-create/` deployed dir is removed by the
  rabbit-cage piece. The cross-feature contract gate stays red until the
  later #922 pieces land (install.py + policy still reference the retired
  skill) — expected and out of scope for this piece.

- **v1.16.0 (#875 script-backed-orchestration cleanup; child of #863):**
  `check-script-backed.py scan` of the feature reported 1 `runtime-placeholder`
  finding: the `scripts/dispatch-spec-create.py --feature-name <feature-name>
  --paths ...` fenced bash block in `skills/rabbit-spec-create/SKILL.md` Step 1.
  Disposition (verify-or-flag, spec-rules §4): the block is an ILLUSTRATIVE CLI
  synopsis documenting how to invoke the existing companion script — the live
  invocation is assembled by `dispatch-spec-create.py` itself (rabbit-spec-create
  is a subagent-dispatching skill already script-backed for prompt assembly),
  not by the model inline. EXEMPTED, not converted: added the `<!-- example -->`
  marker (the mechanism shipped in #869) on the line directly above the opening
  fence. Added Inv 9 codifying the zero-findings requirement and the example
  exemption; numbering stays contiguous 1..9 (no renumber). New E2E guard
  `test/test-script-backed-clean.py` asserts the scan reports `count: 0`. SKILL.md
  body changed -> deployed surface republished by the dispatcher.

- **v1.15.0 (#816 measured-reduction wave; child of #794):**
  Removal pass (prove-it-dead-or-flag, coding-rules §6/§2/§7), not a reword.
  rabbit-spec had already been through two reduction passes (#553, #688) and a
  fallback-removal pass (#633), so it was lean; this wave makes minimal honest
  cuts to the only surviving restated rationale. `docs/spec.md` 187 -> 181
  lines (-6):
    - Inv 3(b): cut the downstream-consumption restatement ("the dropped count
      is consumed by `rabbit-spec-create` Step 4 so the user is told 'and M
      dropped' ...") — that consumption is owned by
      `skills/rabbit-spec-create/SKILL.md` Step 4. The load-bearing NOTE
      behaviour (non-silent stderr note naming the dropped count; silent
      at/below cap) and the "Enforced by" clause stay.
    - Inv 3(e): cut the `parents[0]=scripts ... [4]=repo_root` path-arithmetic
      enumeration and the expanded "forbidden because ... resolve to the
      user-project root ... causing the build-prompt.py path to point to a
      non-existent location" prose — both restate the inline comment in
      `scripts/dispatch-spec-create.py`. Compressed to a one-sentence reason.
      The load-bearing constraint (`Path(__file__).resolve().parents[4]`; NOT
      `git rev-parse`; NOT `os.getcwd()`) and the "Enforced by 3 tests" clause
      stay.
  Verification: SKILL.md Step 4 inspected (owns the dropped-count surfacing);
  `scripts/dispatch-spec-create.py` comment inspected (owns the parents[4]
  arithmetic + forbidden-mechanism rationale). No invariant renumbered or
  retired (no tombstone); numbering stays contiguous 1..8. New E2E content
  guard `test/test-no-restated-rationale.py` forbids the removed restatement
  AND asserts the load-bearing tokens (`dropped`,
  `Path(__file__).resolve().parents[4]`, `git rev-parse`, `os.getcwd()`,
  `test-dispatch-truncation-not-silent.py`) survive; auto-wired via
  `test/run.py` glob. Four-way version alignment bumped
  spec.md/contract.md/feature.json 1.14.0 -> 1.15.0 (contract.md content
  unchanged — version-only bump to satisfy the lockstep assertion in
  `test/test-docs-layout.py`). No deployed skill/agent surface changed
  (cuts are spec-only), so NO dispatcher republish is required. Behaviour is
  unchanged.

- **v1.14.0 (#742 opt into strict contiguous invariant numbering; #724 follow-up):**
  rabbit-spec opts into the contract feature's strict CONTIGUOUS
  invariant-numbering tier introduced in #724. Set `"contiguous_invariants":
  true` at the top level of `feature.json` and added `docs/spec.md` Inv 8
  documenting the opt-in. rabbit-spec's invariants were already contiguous
  1..7, so NO reflow was required — this is a flag-only opt-in plus its
  documenting invariant. New E2E guard
  `test/test-contiguous-invariants-optin.py` asserts both the flag and 1..N
  contiguity through the live contract `_contiguous_opt_in` /
  `check_invariant_monotonic_order` surfaces; wired into `test/run.py`. No
  invariant was retired (no tombstone). Behaviour of the skills is unchanged.

- **v1.13.0 (#688 housekeeping round 2 — measured line-removal pass; under #639):**
  Removal pass, not a reword. `docs/spec.md` 221 -> 175 lines (-46): deleted the
  dead stage/relocation narration from `## Purpose` ("After Stage 2 it hosts ...
  Stage 3 will add ... absorbs the former `spec-seeder` / `rabbit-feature-spec`"
  — both predecessor feature directories are gone and both skills are on disk),
  removed the `## Mode awareness` section (fully duplicated by both SKILL.md
  `## Modes` tables and Inv 5/6), trimmed the verbose `## Surface` sub-bullets
  (the dispatcher glob/cap detail is restated verbatim in Inv 3(b)), collapsed
  the `## Tests` per-test prose to a pointer (each test's docstring and each
  invariant's "Enforced by" clause already carry it), and dropped the
  "(or its successor `rabbit-feature-scaffold` in Stage 4)" hedge (the
  successor has landed). `docs/contract.md` 66 -> 62 lines (-4): removed the
  trailing `## Tech Stack` prose (not part of the JSON contract; duplicated in
  spec.md; no contract scanner requires it). `skills/rabbit-spec-create/SKILL.md`
  (v1.6.0 -> v1.6.1, net-zero lines): replaced dead references to the
  nonexistent `rabbit-feature-new` skill and the dead `(Stage 3)` hedge with
  the live `rabbit-feature-scaffold` / `rabbit-spec-update`. New regression
  guard `test/test-no-relocation-narration.py` forbids the dead stage/relocation
  narration from returning to spec.md; wired into `test/run.py`. #639 checks per
  deletion: `find` confirmed `spec-seeder` and `rabbit-feature-spec`
  directories absent; `find` confirmed no `rabbit-feature-new` SKILL.md exists
  and `rabbit-feature-scaffold` does; both spec-lifecycle skills present on
  disk; no contract test requires a `Tech Stack` section in contract.md.
  Three-way version alignment bumped spec.md/contract.md/feature.json
  1.12.0 -> 1.13.0. The deployed `.claude/skills/rabbit-spec-create/SKILL.md`
  requires a dispatcher republish (deployed-skill-match RED until then).
  Behaviour is unchanged.

- **v1.12.0 (retire legacy B/B terminology on live surfaces, #666; part of #420):**
  Replaced the legacy "bug-and-backlog (B/B)" / standalone "backlog"
  custom-store vocabulary on rabbit-spec's live surfaces with the current
  rabbit-issue terminology — "issue" / "bug or enhancement" /
  "rabbit-managed issue" (GitHub's bug/enhancement taxonomy). The only live
  hits were in `skills/rabbit-spec-update/SKILL.md` (v2.6.0 -> v2.7.0): the
  Inputs `request` bullet ("a bug/backlog item description in B/B mode" ->
  "a rabbit-managed issue description" — "B/B mode" was vestigial input
  framing, not a current operating mode; the skill's real modes are
  standalone/plugin), the Step 2 Specific request-class row ("backlog task"
  -> "enhancement task"), and the What-You-Do-NOT-Do bullet ("File bugs or
  backlog items" -> "File bugs or enhancements"). `docs/spec.md`,
  `docs/contract.md`, `skills/rabbit-spec-create/SKILL.md`, and
  `feature.json` carried no legacy vocabulary. spec.md gains Inv 7 (live
  surfaces carry current issue vocabulary), worded so it does not itself
  reintroduce the banned tokens. New content guard
  `test/test-bb-terminology.py` scans every live surface
  (`docs/spec.md`, `docs/contract.md`, both SKILL.md, `feature.json`) for the
  `B/B` abbreviation, the `bug-and-backlog`/`bug/backlog` phrase family, and
  the standalone `backlog` request-class noun (the literal
  `bug-backlog-files` branch name is exempt as a historical artifact); wired
  into `test/run.py`. Three-way version alignment bumped
  spec.md/contract.md/feature.json 1.11.0 -> 1.12.0 (contract.md content
  unchanged this cycle — version-only bump to satisfy the lockstep assertion
  in `test/test-docs-layout.py`). Behaviour is unchanged. The deployed `.claude/skills/rabbit-spec-update/SKILL.md`
  requires a dispatcher republish (deployed-skill-match RED until then);
  `rabbit-spec-create` was not touched.

- **v1.11.0 (drop dead spec-path fallbacks, #633):** The `specs/` -> flat `docs/` spec migration is COMPLETE — all 11 features carry `docs/spec.md`; a repo-wide `find` for `specs/spec.md` and `docs/spec/spec.md` returns zero matches, so the triple-fallback resolution (flat `docs/` preferred → `specs/` → legacy `docs/spec/`) was unreachable dead code. Applying prove-it-dead (coding-rules §6) the dead branches were deleted and the surfaces collapsed to the single canonical flat `docs/spec.md` / `docs/contract.md`. spec.md Inv 6 rewritten from "dual-read" to "canonical flat docs/ only" (no `specs/`/`docs/spec/` fallback); Purpose, Surface, and Tests sections updated. `skills/rabbit-spec-create/SKILL.md` (v1.5.0 -> v1.6.0): description, body intro, the `Spec-file layout` subsection, Step 3, and the "When to use" bullet collapsed to canonical-only. `skills/rabbit-spec-update/SKILL.md` (v2.5.0 -> v2.6.0): the `Spec-file layout` subsection, Step 1, and Step 4 path references collapsed to canonical `docs/spec.md` / `docs/contract.md`. `docs/contract.md` never-clause simplified (was "resolved layout: flat docs/spec.md preferred, then specs/spec.md, then legacy docs/spec/spec.md"). `agents/rabbit-spec-creator.md` already targeted canonical `docs/spec.md` only — no change. The dispatch script implements no fallback resolution — no change. Test `test/test-spec-path-layout-dual-read.py` -> `test/test-spec-path-layout-canonical.py` (v2.1.0 -> v3.0.0): inverted to assert both SKILL bodies and the agent name `docs/spec.md` ONLY and do NOT mention `specs/spec.md` or `docs/spec/spec.md`. Four-way version alignment bumped spec.md/contract.md/feature.json 1.10.0 -> 1.11.0. Deployed `.claude/skills/rabbit-spec-create/SKILL.md` and `.claude/skills/rabbit-spec-update/SKILL.md` require a dispatcher republish (deployed-skill-match RED until then). The `docs/`/`specs/` resolver in the contract feature is out of scope for this issue (it carries its own coexistence window).

- **v1.10.0 (housekeeping Phase 2 — history-free doc surfaces + Inv 49 strict-tier opt-in, #553):** Scrubbed the historical-burden framing from rabbit-spec's doc surfaces so they describe only the CURRENT design. spec.md Inv 6's heading lost the `(issue #399 Phase 2a coexistence window)` parenthetical and the body's `During the specs/ -> docs/ flatten migration coexistence window, features migrate one-by-one` clause was rephrased to the present-tense `Features may carry any of these three layouts`; the deprecation-criterion sentence dropped the `(tracked by issue #399)` pointer. Both layout subsections in `skills/rabbit-spec-create/SKILL.md` and `skills/rabbit-spec-update/SKILL.md` had the same `specs/ -> docs/ flatten migration (issue #399) runs feature-by-feature` historical clause replaced with present-tense `A feature may carry any of the flat docs/, specs/, or legacy docs/spec/ layouts`. The live three-layout dual-read BEHAVIOUR (flat `docs/` preferred → `specs/` → legacy `docs/spec/`) is unchanged — only the historical wrapper and `#399` issue refs were removed; the migration history those refs pointed to is preserved here in this CHANGELOG (see the v1.5.0–v1.8.0 notes below). Opted into the Inv 49 strict tier by adding top-level `"housekeeping_clean": true` to `feature.json`. No invariants renumbered or retired; no contract-owned file edited. Four-way version alignment bumped spec.md/contract.md/feature.json 1.9.0 -> 1.10.0; source `skills/rabbit-spec-create/SKILL.md` (v1.4.0 -> v1.5.0) and `skills/rabbit-spec-update/SKILL.md` (v2.4.0 -> v2.5.0) each took a minor bump. The deployed `.claude/skills/rabbit-spec-create/SKILL.md` and `.claude/skills/rabbit-spec-update/SKILL.md` require a dispatcher republish (deployed-skill-match RED until then).

- **v1.9.0 (no silent file-cap truncation, #472):** `scripts/dispatch-spec-create.py` previously did `sorted(set(resolved))[:MAX_FILES]`, silently dropping every file past the 50th alphabetically — producing incomplete `## Public surface` / `## Current behaviour` spec sections with NO warning (reachable in plugin mode for features with >50 matched files). Fix (chosen approach: surface, do not silently slice — the cap itself is kept since the prompt template's slot budget is the real constraint, but the loss is now reported): the dispatcher counts the deduped resolved files BEFORE slicing and, when the count exceeds the cap, writes a structured `NOTE: resolved <N> files; capped at <MAX_FILES>, <M> dropped` line to STDERR. STDOUT stays a single prompt-file path so the skill's Step 1 parse is unaffected; the skill's Step 4 surfaces the dropped count to the user. When the count is <= the cap, no note is emitted. Inv 3(b) amended to require the non-silent behavior; contract `provides.scripts[dispatch-spec-create.py]` gains a `stderr` field. New `test/test-dispatch-truncation-not-silent.py` (>cap reports dropped count on stderr while stdout is a single existing file path; <=cap emits no note) wired into `test/run.py`. Source `skills/rabbit-spec-create/SKILL.md` (v1.3.0 -> v1.4.0) Step 1/Step 4 updated to document and surface the stderr note; `scripts/dispatch-spec-create.py` docstring (v1.1.1 -> v1.2.0) updated. The dispatch script is a skill-local script invoked from source (NOT in the publish manifest), so it needs no republish; the SKILL.md body/version DID change, so the deployed `.claude/skills/rabbit-spec-create/SKILL.md` requires a dispatcher republish (deployed-skill-match RED until then).

- **v1.8.0 (flat docs/ file move, #399 Phase 2b):** Moved rabbit-spec's own doc artifacts onto the flat `docs/` layout: `git mv`d `specs/spec.md` -> `docs/spec.md`, `specs/contract.md` -> `docs/contract.md`, and root `CHANGELOG.md` -> `docs/CHANGELOG.md`; removed the now-empty `specs/` directory. Spec/contract bodies unchanged except the Surface, Inv 6 self-reference, and Tests sections, which now name the flat `docs/` layout (was `specs/`). Four-way version alignment for the spec/contract/feature.json lineage bumped 1.7.0 -> 1.8.0; source `skills/rabbit-spec-create/SKILL.md` (v1.2.0 -> v1.3.0), `skills/rabbit-spec-update/SKILL.md` (v2.3.0 -> v2.4.0), and `agents/rabbit-spec-creator.md` (v1.1.0 -> v1.2.0) each took an independent minor bump (their bodies are unchanged; the skill/agent dual-read coexistence window stays open). New on-disk E2E `test/test-docs-layout.py` asserts the flat layout, resolver resolution, and `validate_feature`; `test/test-spec-path-layout-dual-read.py` (v2.0.0 -> v2.1.0) flipped its self-layout assertion from `specs/` to flat `docs/`. Deployed `.claude/skills/rabbit-spec-*` and `.claude/agents/rabbit-spec-creator.md` NOT touched per scope; they require a dispatcher republish (deployed-skills/agent-match RED until then). The `docs/` vs `specs/` resolver fallback in the contract feature keeps cross-feature consumers green through the coexistence window.

- **v1.7.0 (flat docs/ resolver, #399 Phase 2a):** Updated rabbit-spec's spec-path resolvers to PREFER the flat `docs/spec.md` (and `docs/contract.md`) layout, FALL BACK to `specs/`, then to legacy `docs/spec/`, mirroring the contract feature's `resolve_spec_path` precedence (#399 Phase 1a). No files move (rabbit-spec itself stays on `specs/` so the fallback hits and the repo stays green). Inv 6 rewritten for the three-layout precedence order and now also constrains the drafting agent. `rabbit-spec-update` (v2.2.0 -> v2.3.0) and `rabbit-spec-create` (v1.1.1 -> v1.2.0) rewrote their `Spec-file layout` subsections and every Step 1/3/4 path reference to the flat-docs-preferred order; `agents/rabbit-spec-creator.md` (v1.0.0 -> v1.1.0) now names the flat `docs/spec.md` draft target (was `docs/spec/spec.md`). Inv 2 relaxed the agent version pin to `1.1.0 or later`. `test/test-spec-path-layout-dual-read.py` (v1.0.0 -> v2.0.0) now asserts all three layouts are named, the flat `docs/` is preferred across both SKILL bodies, and the agent targets the flat path. Deprecation criterion for the fallbacks: issue #399 final phase (every feature on flat `docs/`). Deployed skills/agent require republish.

- **v1.6.0 (rename agent spec-creator -> rabbit-spec-creator, #471):** The drafting subagent's base name violated `contract.lib.checks.check_naming` (Inv 10/15), which requires every artifact under `.claude/agents/` to start with `rabbit-` (the deployed `.claude/agents/spec-creator.md` was flagged). `git mv`d the source `agents/spec-creator.md` -> `agents/rabbit-spec-creator.md` and rewrote its frontmatter `name:` and body self-reference. Inv 2 now pins `name: rabbit-spec-creator` at `agents/rabbit-spec-creator.md` and states the rabbit- prefix is required for check_naming. Updated every in-feature reference: `feature.json` surface/manifest entries, `specs/contract.md` `provides.agents`/`invokes.agents.subagent_type` and prose, `skills/rabbit-spec-create/SKILL.md` dispatch call `subagent_type` (v1.1.0 -> v1.1.1), and `scripts/dispatch-spec-create.py` docstring/argparse (v1.1.0 -> v1.1.1). Deployed via `publish_agent` to `.claude/agents/rabbit-spec-creator.md` and removed the stale `.claude/agents/spec-creator.md`. `test/test-agent-restriction.py` (v1.0.0 -> v1.1.0) now asserts the new source name, that the old source is gone, that the deployed copy exists under the rabbit- name with no stale deployment, and (end-to-end) that `check_naming` no longer flags spec-creator.

- **v1.5.0 (spec-path layout migration + dual-read, #399 Phase 2):** Migrated rabbit-spec's own spec/contract from `docs/spec/` to `specs/` (`git mv`; empty `docs/` removed). Added Inv 6: both spec-lifecycle skills now resolve any feature's spec-file layout INDEPENDENTLY of the mode prefix, preferring the canonical `specs/spec.md` and falling back to legacy `docs/spec/spec.md` so they keep working for features not yet migrated. `rabbit-spec-update` (v2.1.0 -> v2.2.0) gained a "Spec-file layout" subsection defining `<spec_path>`/`<contract_path>` resolution and rewired Step 1 / Step 4 to the resolved paths; `rabbit-spec-create` (v1.0.0 -> v1.1.0) gained the same layout subsection and rewired Step 3 to write to `specs/spec.md` when canonical (or the existing legacy layout, or — for a brand-new scaffold — the canonical `specs/spec.md`). Inv 4 relaxed the create-skill version pin to `1.1.0 or later`. New source-inspection test `test/test-spec-path-layout-dual-read.py` proves both SKILL.md bodies document the dual-read and asserts rabbit-spec's own `docs/` is gone. This rides the coexistence window opened by contract v2.3.0 (#399 Phase 1); Phase 3 drops the legacy fallback once every feature has migrated. Deprecation criterion for the fallback: issue #399 Phase 3 (every feature migrated to `specs/`).

## Retired invariants

(none yet)
