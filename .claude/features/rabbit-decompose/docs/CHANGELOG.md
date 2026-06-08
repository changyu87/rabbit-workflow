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

- **v0.15.0 (greenfield dirs are not orphans — fix #1040 false positive,
  #1042):** The #1040 orphan detector flagged EVERY feature dir on disk but
  absent from `project-map.json` as an orphan. But a greenfield feature has
  `paths: []` in its `feature.json`, and the project-map schema requires
  non-empty paths, so `scaffold-feature.py` INTENTIONALLY never registers a
  greenfield feature in `project-map.json`. The detector therefore emitted every
  greenfield dir as an orphan — a guaranteed false positive on an all-greenfield
  project, surfacing the misleading "partial/aborted decompose" message when no
  inconsistency exists. Fixed: a dir absent from the map is a TRUE orphan ONLY
  when its `feature.json` declares NON-EMPTY `paths`; a `paths: []` dir is
  excluded from `orphan_feature_dirs`. A dir whose `feature.json` is absent,
  unreadable, or malformed cannot be proven greenfield, so it stays an orphan
  (the safe classification) and the scan never crashes. `feature_dirs_on_disk`
  still enumerates every dir; only `orphan_feature_dirs` carries the
  greenfield-aware filter. Extended `test-detect-orphan-feature-dirs.py` with
  the greenfield-exclusion and missing/malformed-`feature.json` cases; updated
  Invariant 8's orphan clause. Additive — all prior `--detect-existing` fields
  unchanged. Four-way version bump 0.14.0 → 0.15.0 (lockstep).

- **v0.14.0 (surface orphan feature dirs in --detect-existing, #1040):** After
  a partial/aborted decompose the project can reach an inconsistent state —
  feature directories exist on disk under the resolved `features/` root but are
  NOT represented in `project-map.json` (or `project-map.json` is entirely
  absent while dirs exist). In that state `handoff-scaffold.py --features` failed
  at scaffold time ("scaffold target .../features/<name> already exists") with no
  recovery path, and `--detect-existing` did not surface the inconsistency at
  all. Extended `--detect-existing` to SCAN the on-disk `features/` root (the
  sibling dir next to `project-map.json`) and add two additive report fields:
  `feature_dirs_on_disk` (sorted names of all dirs under `features/`) and
  `orphan_feature_dirs` (sorted names present on disk but absent from the
  `features` map, treating an absent map as empty). Detection + surfacing only —
  no auto-delete, no auto-adopt; the adopt-vs-proceed decision stays the
  caller's. All prior `--detect-existing` fields and behavior are unchanged
  (additive). New E2E test `test-detect-orphan-feature-dirs.py`. Four-way
  version bump 0.13.0 → 0.14.0 (lockstep).

- **v0.13.0 (dual-accept the EMITTED mode field in the test suite — complete
  the #988 coverage gap, #997, unblocks #990):** #988 dual-accepted
  `handoff-scaffold.py`'s five INTERNAL branch comparisons, so the script
  ROUTES a `"vendored"`-mode run down the vendored path. But the script emits
  `detect_mode`'s value VERBATIM into its output `mode` field, and the feature's
  own E2E suite still STRICTLY asserted that emitted field == `"plugin"` at
  seven sites across four tests — the LAST consumers that would RED the moment
  `detect_mode` flips its vendored value `"plugin"` → `"vendored"` (the #980
  rename, owned by rabbit-meta, tracked as #990). Relaxed each emitted-`mode`
  assertion to the dual-accept `mode not in ("vendored", "plugin")` mirroring
  #988: `test-default-rabbit-root.py` (Checks ~136/147),
  `test-step1-source-root.py` (Checks ~133/162), `test-step4-script-backed.py`
  (Checks ~126/185), and `test-step4-skill-batch-interface.py` (Check ~209). On
  the two toggle assertions the `"standalone"` arm stays STRICT (it proves the
  toggle actually flipped the mode); only the vendored-value arm is relaxed.
  Extended spec Invariant 10 with the emitted-field clause and added a new E2E
  `test-emitted-mode-dual-accept.py` that stands up a temp `.claude/features/`
  tree with a COPY of `handoff-scaffold.py` plus a FAKE
  `rabbit-meta/lib/mode_detection.py` returning `"vendored"` — simulating the
  rename WITHOUT touching the real detector — drives the three emitted-`mode`
  consumers (`--source-root`, `--plan-only`, `--detect-existing`) confirming
  each emits `"vendored"` with the vendored behaviour preserved, and greps the
  whole `test/` suite to confirm no strict emitted-`mode == "plugin"` field
  assertion remains. `detect_mode` is NOT changed here (rabbit-meta owns it; the
  value flip is #990); the value stays `"plugin"` now so the contract gate stays
  green. Coexistence-window end-of-life unchanged: the `"plugin"` arm (in the
  script comparisons AND the emitted-field assertions) is dropped only after the
  rename completes and the legacy value is fully retired. Four-way version
  lockstep bumped to 0.13.0. Deployed surface: only the `SKILL.md` frontmatter
  version changed (body unchanged) — the dispatcher republishes the deployed
  `rabbit-decompose` skill so the deployed frontmatter version stays consistent.
  Part of the four-feature #980 migration barrier (the decompose test-suite
  child; the rabbit-meta value flip is gated on the prep children landing
  first).

- **v0.12.0 (dual-accept vendored/plugin mode in handoff-scaffold — prep for
  the #980 rename, #988):** Gate-safe preparation for the #980 migration that
  renames the vendored-mode value resolved by
  `rabbit-meta.lib.mode_detection.detect_mode` from `"plugin"` to `"vendored"`.
  `scripts/handoff-scaffold.py` had 5 `mode == "plugin"` comparison sites — the
  source-root resolver, the project-map path resolver, the decompose-marker
  path resolver, and the two main-dispatch branch sites — that would SILENTLY
  fall through to the standalone path the moment the value flipped to
  `"vendored"`, mis-routing every vendored install to the wrong (per-feature,
  no-batch, wrong project-map / marker) branch. Each comparison is now a
  dual-accept `mode in ("vendored", "plugin")` (inline, NOT a cross-feature
  helper import), so BOTH values take the vendored path; the script is correct
  before AND after the rename. The value is NOT flipped here (it stays
  `"plugin"`, so the contract gate stays green now), and `detect_mode` is NOT
  changed (rabbit-meta owns it; the value flip is the blocked-on-this #990
  child). The four affected E2E tests (`test-decompose-context-marker`,
  `test-step1-source-root`, `test-step4-script-backed`,
  `test-step4-skill-batch-interface`) had their docstrings/notes updated to the
  dual-accept truth, and a new E2E `test-dual-accept-vendored-mode.py` drives
  each of the five comparison sites with BOTH `"vendored"` and `"plugin"`,
  asserting they resolve to the SAME vendored result and diverge from
  `"standalone"`. New spec Invariant 10 pins the dual-accept contract and names
  its coexistence-window deprecation criterion (the `"plugin"` arm is removed
  only after the rename completes and the legacy value is fully retired).
  Four-way version lockstep bumped to 0.12.0. Deployed surface: only
  `handoff-scaffold.py` (the script body) and the `SKILL.md` frontmatter
  version changed — the dispatcher republishes the deployed `rabbit-decompose`
  skill so the deployed frontmatter version stays consistent. Part of the
  four-feature #980 migration barrier (this is the decompose child; the
  rabbit-meta value flip is gated on the four prep children landing first).

- **v0.11.0 (adopt the decompose-context scope-guard pass-through, #923 piece
  2/2):** Step 4's batch scaffold + spec-seed work writes across SEVERAL
  feature directories at once, which previously required the undiscoverable
  manual `.rabbit/.rabbit-scope-override = 'session'` workaround to get past
  the repo-wide default-deny scope guard. #923 piece 1 added a principled,
  bounded, auto-cleared pass-through to rabbit-cage's `scope-guard.py`: a
  `.rabbit/.runtime/decompose-active` marker carrying
  `{operation, features, expires?}` that, while present, AUTHORIZES writes
  inside any named feature's directory (Inv 47). This piece adopts that
  pass-through. `scripts/handoff-scaffold.py` gained a `--decompose-context
  set|clear` subcommand: `set` (with `--features <accepted.json>`) writes the
  marker at the mode-correct path (plugin →
  `<rabbit_root>/.runtime/decompose-active`; standalone →
  `<rabbit_root>/.rabbit/.runtime/decompose-active`, mirroring the project-map
  path resolution) recording `operation` plus the EXACT accepted feature
  NAMES; `clear` deletes it idempotently. The script's own plugin-mode batch
  dispatch now wraps the scaffolder invocation in set-before / clear-after via
  a try/finally, so a FAILING scaffolder still clears the marker. `SKILL.md`
  Step 4 was restructured (A open the pass-through → B scaffold → C seed specs
  → D close the pass-through → E report): it SETS the marker before any batch
  work and CLEARS it after all batch work (success OR failure), and no longer
  references the manual `.rabbit-scope-override` session workaround. New spec
  Invariant 9 pins the set/clear contract, the marker JSON schema, the
  mode-correct path, and the try/finally clear-on-failure. `docs/contract.md`
  declares the marker under `provides.files` and narrows the `never` clause to
  exclude this one orchestration write. New E2E
  `test-decompose-context-marker.py` asserts the set writes the mode-correct
  marker with piece-1's schema, the clear deletes it idempotently, the batch
  dispatch sets-before / clears-after even on scaffolder failure, and the
  `SKILL.md` body invokes `--decompose-context` and drops the manual override.
  Four-way version lockstep bumped to 0.11.0. Deployed surface changed (source
  `SKILL.md` body + `handoff-scaffold.py`) — the dispatcher republishes the
  deployed `rabbit-decompose` skill before the final #923 PR; the deployed
  rabbit-cage `scope-guard.py` hook from piece 1 is also republished by the
  dispatcher.

- **v0.10.0 (Step 4-B retires the spec-create skill wrapper; dispatch
  rabbit-spec-creator directly, #922 piece 4/5):** Step 4-B previously seeded
  each accepted feature's spec by invoking the `rabbit-spec-create` skill as
  sequential `Skill(...)` calls, with a paragraph explaining the old
  two-level-nesting workaround (the skill was a subagent-dispatching wrapper,
  so it could not be wrapped in `Agent(...)`). #922 retired that skill wrapper:
  the `rabbit-spec-creator` SUBAGENT now drafts AND writes its own
  `docs/spec.md` and is dispatched DIRECTLY, with its prompt assembled by
  `rabbit-spec`'s renamed input assembler `scripts/dispatch-spec-creator.py`.
  Rewrote Step 4-B to the new model: for each accepted feature with globs, run
  `dispatch-spec-creator.py --feature-name <name> --paths <globs>` (no
  `--paths` for a greenfield skeleton) to print the assembled prompt-file path,
  then dispatch `Agent(subagent_type: "rabbit-spec-creator", prompt: <prompt>)`
  directly. Because the subagent is now a level-1 dispatch (decompose is a
  main-session orchestration with no intermediate subagent-dispatching skill),
  the N per-feature dispatches MAY run in parallel — the old sequential
  constraint is gone. Deleted the obsolete two-level-nesting workaround prose.
  `docs/contract.md` `invokes` now declares the `rabbit-spec-creator` subagent
  (new `invokes.agents` entry, mirroring rabbit-spec's contract) plus the
  `dispatch-spec-creator.py` script invoke, and drops the retired
  `rabbit-spec-create` skill invoke; `docs/spec.md` Purpose/Surface/Protocol,
  Invariant 3, Invariant 4, the Tests entry, and Out of Scope were updated to
  the direct-dispatch model. `test-step4b-no-nested-dispatch.py` was rewritten
  to assert the NEW truth: both surfaces reference neither the retired
  `rabbit-spec-create` skill nor the old `dispatch-spec-create.py` name, both
  name the new direct-dispatch path, and Step 4-B dispatches
  `rabbit-spec-creator` directly via `Agent(subagent_type: ...)` at level-1 and
  states the dispatches may run in parallel. Four-way version lockstep bumped
  to 0.10.0. Deployed surface changed (source `SKILL.md` body) — the dispatcher
  republishes the deployed `rabbit-decompose` skill before the final #922 PR.
  Part of the five-feature #922 barrier (piece 4/5; pieces 1-3 landed
  rabbit-spec/policy/rabbit-cage, piece 5 lands rabbit-feature); the
  cross-feature contract gate stays red until piece 5 lands AND the dispatcher
  syncs deployed surfaces (expected).

- **v0.9.0 (detect an existing decomposition before re-proposing, #925):**
  rabbit-decompose previously re-proposed the FULL feature set on every run,
  even when the project was already decomposed — redundant and confusing
  output. Added a deterministic, script-backed pre-Step-2 detection: a new
  `--detect-existing` mode on `scripts/handoff-scaffold.py` resolves mode via
  `rabbit-meta`'s `detect_mode` and reads the project's `project-map.json`
  (plugin → `<rabbit-root>/rabbit-project/project-map.json`; standalone →
  `<rabbit-root>/.rabbit/rabbit-project/project-map.json`). When the `features`
  map is non-empty it emits `existing: true` with the existing-feature SUMMARY
  (`existing_features`) and the three-way branch `options`
  (`skip` / `add` / `re-decompose`); a missing/unparseable/empty project-map
  collapses to `existing: false`, leaving the first-run propose flow unchanged.
  When a candidate list is supplied via `--features`, candidates are classified
  into `already_rabbified` vs `new` so the "add" branch proposes ONLY the
  new/unrabbified features. The `SKILL.md` gained a pre-check section documenting the
  detection and the three-way escalation; `docs/spec.md` gained Invariant 8 and
  the new test entry; `docs/contract.md`'s `mode_detection` invoke note now
  cites the detection path (the `project-map.json` read was already declared in
  `reads`). New E2E `test-detect-existing-project-map.py` asserts the detection,
  the SUMMARY, the three-way branch, the candidate classification, the
  first-run-unchanged path, and the mode-driven project-map path resolution.
  Four-way version lockstep bumped to 0.9.0.

- **v0.8.0 (route Step 4 scaffold dispatch through the rabbit-feature-scaffold
  skill batch interface — layering fix, #921):** plugin-mode Step 4 previously
  shelled out to rabbit-feature's `scripts/scaffold-feature.py --batch`
  directly — a layering violation, since the skill (not its implementation
  script) is rabbit-feature's declared cross-feature interface. Piece 1 of
  #921 published a skill-level batch surface
  (`skills/rabbit-feature-scaffold/scripts/scaffold-batch.py`, exit codes
  0/1/2 mirrored). `handoff-scaffold.py._resolve_scaffolder` now resolves and
  dispatches that skill batch interface (`scaffold-batch.py --batch <file>`)
  instead; the batch-JSON authoring and exit-code propagation are unchanged.
  `docs/contract.md` `invokes.scripts` now references `scaffold-batch.py`,
  Invariant 5 gained a layering clause, and `SKILL.md` Step 4 prose names the
  skill batch interface. New E2E `test-step4-skill-batch-interface.py` asserts
  the dispatch goes through the skill interface and not the scaffolder script
  directly. Part of the two-feature #921 barrier (piece 2/2; piece 1 was
  rabbit-feature 1.40.0).

- **v0.7.2 (contract `reads.files` accuracy fix — stale `.rabbit/.runtime/mode`
  read removed, #908):** `docs/contract.md` `reads.files` still listed
  `.rabbit/.runtime/mode` as a read. Since #890/#901/#906,
  `handoff-scaffold.py` resolves plugin-vs-standalone mode by reusing
  rabbit-meta's canonical `detect_mode` — a STRUCTURAL check on the
  rabbit-root's basename, NOT a file read of that marker path. The
  `reads.files` entry was therefore stale (proven dead: `grep` finds no
  genuine read of `.rabbit/.runtime/mode` in any rabbit-decompose script; the
  only mention is a docstring noting what the script does NOT do). Removed the
  stale `reads.files` entry. The real cross-feature dependency — the
  `detect_mode` INVOKE — was already correctly declared under
  `invokes.scripts` (`rabbit-meta/lib/mode_detection.py`, from #901), so no
  duplication was added. Contract-accuracy fix only; NO behavior change.
  New E2E `test-contract-reads-accurate.py` locks the corrected block in.
  Deployed surface: `SKILL.md` body unchanged (frontmatter `version` bumped
  in four-way lockstep); the dispatcher republishes the deployed `SKILL.md`
  copy so the deployed frontmatter version stays consistent.

- **v0.7.1 (default rabbit-root for mode detection is now the cwd, not the
  git toplevel, #906):** `handoff-scaffold.py._default_rabbit_root()` (used
  when `--rabbit-root` is not supplied) returned
  `git rev-parse --show-toplevel`. In a plugin install the vendored
  `.rabbit/` dir lives INSIDE the user project's git repo, so the git
  toplevel is the user-project root (the PARENT of `.rabbit`), whose
  basename is not `.rabbit`. `detect_mode` requires `basename == '.rabbit'`
  to return `plugin`, so the default invocation mis-detected plugin installs
  as `standalone` and silently took the wrong scaffold branch (per-feature
  instead of plugin `--batch`). Fix (issue option (a)):
  `_default_rabbit_root()` now returns `os.getcwd()`. In a rabbit session
  the cwd IS the mode-correct rabbit root — the `.rabbit/` dir in plugin
  mode, the repo root in standalone mode — exactly what `detect_mode`
  expects, so the default invocation from `cwd=.rabbit` detects `plugin` and
  from a repo root detects `standalone`. The #901 `_resolve_source_root`
  stays correct: with `rabbit_root = cwd = .rabbit`, plugin source_root =
  `.rabbit`.parent = the project root. The `SKILL.md` Step 1 and Step 4 bash
  blocks (which invoke the resolver WITHOUT `--rabbit-root`) now rely on the
  corrected cwd default and resolve the mode-correct root. New spec
  Invariant 7 and E2E `test-default-rabbit-root.py` lock this in. Deployed
  surface changed: `handoff-scaffold.py` (script body); `SKILL.md` body
  unchanged in wording but bumped in lockstep — dispatcher republishes both
  deployed copies.

- **v0.7.0 (Step 1 source-root guidance folded into the canonical resolver,
  #901):** Step 1 (Gather inputs) gave NO guidance on WHERE the decomposition
  SOURCE lives in plugin mode. In plugin mode the cwd / rabbit-root is the
  vendored `.rabbit/` install dir, but the project to decompose is its PARENT
  (`rabbit_root.parent`); without guidance a no-args plugin-mode run could
  point Glob/Read at the `.rabbit` workflow tooling itself and "decompose" the
  workflow instead of the user project. Fix: extended the #890 canonical
  resolver `scripts/handoff-scaffold.py` to ALSO resolve the decomposition
  SOURCE ROOT — plugin → `rabbit_root.parent` (the user project, matching
  `scaffold-feature.py._detect_plugin_mode`), standalone → the repo root —
  exposed via a new `--source-root` mode (prints `{mode, source_root}`) and
  added to the Step 4 plan JSON as `source_root`, so Step 1 and Step 4 share
  one resolver and cannot disagree. Mode detection still reuses
  `rabbit-meta.lib.mode_detection.detect_mode` (NOT a hard-coded
  `.rabbit/.runtime/mode` path read, post-#891). The `SKILL.md` Step 1 body
  now references the canonical resolver and the plugin-mode parent-of-`.rabbit`
  source root instead of hand-resolving an ambiguous `<repo>`. New spec
  Invariant 6 and E2E `test-step1-source-root.py` lock this in. Deployed
  surface changed (SKILL.md + handoff-scaffold.py) — dispatcher must
  republish.

- **v0.6.0 (Step 4 hand-off made script-tier, #890):** Step 4's scaffold
  hand-off was prose-tier orchestration: the `SKILL.md` body did the mode
  detection (read `<repo>/.rabbit/.runtime/mode`), the batch temp-file
  authoring (`--batch /tmp/decompose-batch-<ts>.json` — a model-assembled
  `<ts>`), and the plugin-vs-standalone scaffolder branch inline, violating
  spec-rules §4 Script-Backed Orchestration. The `<repo>` placeholder was
  also ambiguous — a model could resolve it to the decomposition SOURCE or
  git-toplevel and read the wrong/absent mode marker, taking the wrong
  scaffold branch silently. Fix: added `scripts/handoff-scaffold.py`, a
  SCRIPT-tier orchestrator that (a) resolves the rabbit root and detects mode
  deterministically by REUSING `rabbit-meta.lib.mode_detection.detect_mode`
  (lazy-import, mirroring the established `contract.lib.runtime.write_mode_marker`
  pattern) instead of a single hard-coded mode-path read; (b) authors the
  batch temp file with a script-owned timestamp (no model-assembled `<ts>`);
  and (c) dispatches the scaffolder on the mode-correct branch (plugin →
  `scaffold-feature.py --batch <file>`; standalone → emits the per-feature
  `rabbit-feature-scaffold` plan, batch being plugin-only). `SKILL.md` Step 4
  was rewritten to a single clean script invocation (the only remaining bash
  is read-only/illustrative per the §4 exception); the prose mode-branch and
  placeholder blocks are gone. New spec Invariant 5 pins the script-tier
  requirement and the `detect_mode` reuse; the cross-feature INVOKE is
  declared in `docs/contract.md` `invokes.scripts`. New E2E test
  `test/test-step4-script-backed.py` runs the script end-to-end against temp
  plugin and standalone trees (asserting `detect_mode`-driven branching, a
  script-owned timestamped batch file, and no single hard-coded mode path)
  and asserts the `SKILL.md` Step 4 body carries no prose mode-branch and no
  runtime-placeholder bash block. New surface (`scripts/handoff-scaffold.py`)
  declared in `feature.json` `surface.scripts`. Frontmatter `version` bumped
  to 0.6.0 across `feature.json`, `docs/spec.md`, `docs/contract.md`, and the
  source `SKILL.md` (four-way alignment); the deployed `.claude/` copy needs a
  dispatcher republish because the source SKILL.md AND the new `scripts/` tree
  changed the deployed surface. Cross-feature boundary respected: `detect_mode`
  is IMPORTED/INVOKED, never edited.

- **v0.5.4 (spec<->artifact prompts coherence fix, #825):** Resolved a
  spec<->artifact mismatch discovered during #811: spec Invariant 1 required
  the `prompts` array to "contain exactly one entry with `id:
  rabbit-decompose`, `kind: skill`, ...", but `feature.json` shipped
  `prompts: []`. The contract gate's `check_prompts_section` validates only
  *present* prompt entries and treats an empty `prompts` as vacuously valid,
  so the mismatch went uncaught. rabbit-decompose is an inline,
  dispatcher-orchestrated skill with no backing subagent, dispatch script, or
  slot-filled prompt template (spec Surface: "No backing agent or dispatch
  script in this MVP"), and no `templates/prompts/rabbit-decompose.txt`
  exists — so the coherent state is `prompts: []`. Picked the
  artifact-matches-reality resolution: rewrote Invariant 1 to require the
  `prompts` array be empty (documenting the absent prompt-contract surface)
  rather than require a prompt entry that has never existed. Had the inverse
  resolution been taken (add the entry), the contract gate would have failed
  on the missing convention-resolved template — confirming the spec
  requirement, not the artifact, was wrong. New E2E test
  `test/test-prompts-spec-artifact-agree.py` pins the coherence: `prompts` is
  empty, Invariant 1 documents the empty surface (and no longer requires an
  entry), and no `rabbit-decompose.txt` prompt template exists; it is the
  canonical flip point if a backing prompt is ever genuinely added.
  Discovered (out of scope, filed separately): the contract gate's
  empty-`prompts` vacuous pass is the structural reason this drift went
  uncaught; tightening it to validate spec<->prompts coherence cross-feature
  lives in the contract feature, not here. Frontmatter `version` bumped to
  0.5.4 across `feature.json`, `docs/spec.md`, `docs/contract.md`, and the
  source `SKILL.md` (four-way alignment); the deployed `.claude/skills/` copy
  needs a dispatcher republish because the source SKILL.md frontmatter
  version changed (body otherwise unchanged).

- **v0.5.3 (housekeeping round 3 — measured line removal, #811 / #794):**
  Removal-not-reword pass over the feature's doc surfaces under coding-rules
  §6 (prove-it-dead-or-flag), §2 (Simplicity First), §7 (Parenthetical
  Clarity). Cuts in `docs/spec.md`, each verified: (1) the Purpose section
  restated the greenfield/existing-codebase scenarios in full bullet detail,
  duplicating Interactive Protocol Step 1 — collapsed to a one-line scenario
  summary that defers to the protocol, and dropped the decorative rhetorical
  question. (2) Removed the `## Tech Stack` section ("No Python script in this
  MVP — the skill is dispatcher-orchestrated"), a verbatim restatement of the
  Surface note immediately above it; no contract check requires the section
  (`grep "Tech Stack"` over the contract feature returns only its own spec).
  (3) Dropped the parenthetical "(rabbit-decompose proposes; it does not
  modify code)" in Invariant 3, which restated the `never` clause it quotes.
  All named load-bearing tokens preserved: invariants stay contiguous 1..4,
  the two-level-nesting constraint and "sequential" wording stay on both
  surfaces (`test-step4b-no-nested-dispatch.py` green), and the
  decomposition-shape + cross-feature `invokes`/`reads` tokens are unchanged.
  Cross-feature claims re-verified LIVE and KEPT (`scaffold-feature.py
  --batch`, `rabbit-feature-scaffold`, `rabbit-spec-create`,
  `.rabbit/.runtime/mode` all present). `SKILL.md` body unchanged (no reword
  to manufacture a diff); only its frontmatter `version` moved in lockstep.
  Frontmatter `version` bumped to 0.5.3 across `feature.json`, `docs/spec.md`,
  `docs/contract.md`, and the source `SKILL.md` (four-way alignment); the
  deployed `.claude/skills/` copy needs a dispatcher republish because the
  source SKILL.md frontmatter version changed. spec.md 130 -> 117 lines.

- **v0.5.2 (opt into contiguous-invariants strict tier, #740 / #724
  follow-up):** Declared `"contiguous_invariants": true` at the top level of
  `feature.json`, opting rabbit-decompose into the contract suite's Inv 30
  strict tier (#724): its `## Invariants` section must now number contiguously
  1..N with no holes, not merely strictly increasing. No reflow was needed —
  the section was already contiguous 1..4 (verified via
  `reflow-invariants.py --dry-run`). Flag-flip only; no SKILL.md body change,
  so the four-way version lockstep (feature.json + docs/spec.md +
  docs/contract.md + SKILL.md frontmatter) bumps 0.5.1 → 0.5.2. New E2E test
  `test/test-contiguous-invariants-optin.py` asserts the flag is set and that
  the live contract check (`check_invariant_monotonic_order`) passes for the
  feature under the strict tier.

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
