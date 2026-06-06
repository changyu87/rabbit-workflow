---
feature: rabbit-decompose
version: 0.12.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native feature-decomposition assistance that supersedes this skill
status: active
---

# rabbit-decompose — Spec

## Purpose

rabbit-decompose proposes a feature decomposition for the user to review,
edit, and accept. It is the upstream scoper that decides, given a high-level
intent or an existing codebase, what the features should be.

Two scenarios drive the design — **greenfield** (a spec, design doc, or
natural-language description) and **existing codebase** (a directory or
project root) — detailed in the Interactive Protocol below. In both cases
the output is the same: an accepted feature list that feeds the downstream
pipeline (the `rabbit-feature-scaffold` skill's `--batch` interface then a
direct `rabbit-spec-creator` subagent dispatch per feature).

## Surface

- `skills/rabbit-decompose/SKILL.md` — the user-invocable skill
- `scripts/handoff-scaffold.py` — the single canonical mode/root resolver and
  Step 4 hand-off orchestrator: resolves the rabbit root, detects mode
  deterministically (reusing `rabbit-meta.lib.mode_detection.detect_mode`),
  resolves the Step 1 decomposition source root (plugin → `rabbit_root.parent`,
  standalone → the repo root) via `--source-root`, authors the batch temp file
  with a script-owned timestamp, and dispatches the scaffolder on the
  mode-correct branch (plugin → the `rabbit-feature-scaffold` skill batch
  interface `scaffold-batch.py --batch <file>`, NOT a direct shell-out to
  rabbit-feature's `scaffold-feature.py`; standalone → emits the per-feature
  `rabbit-feature-scaffold` plan). It also owns the decompose-context
  scope-guard pass-through via `--decompose-context set|clear`: the bounded,
  auto-cleared marker that authorizes batch writes across the accepted
  features' directories (see Interactive Protocol Step 4 and Invariant 9)
- `docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`, `feature.json`,
  `test/run.py` — feature scaffolding

The interactive protocol (Steps 1–3) runs inline in the dispatcher session.
Step 4's mode detection, batch-file authoring, and scaffolder dispatch are
SCRIPT-tier: the SKILL invokes `scripts/handoff-scaffold.py` rather than
assembling mode branches and runtime placeholders in prose (spec-rules §4
Script-Backed Orchestration). The spec seeding dispatches the
`rabbit-spec-creator` subagent DIRECTLY at level-1 — the prompt assembled by
`rabbit-spec`'s `dispatch-spec-creator.py` input assembler — per Invariant 4.

## Interactive Protocol

The skill is interactive by design. The dispatcher MUST:

1. **Gather inputs** — confirm with the user which scenario applies
   (greenfield vs existing codebase) and gather the source material
   (spec text, design doc path, or codebase root). When no explicit source
   path is supplied, the decomposition source root is resolved by the same
   canonical resolver Step 4 uses (`scripts/handoff-scaffold.py
   --source-root`, reusing `rabbit-meta.lib.mode_detection.detect_mode`):
   in plugin mode it is the PARENT of the `.rabbit` install (the user
   project — NOT the `.rabbit/` tooling), in standalone mode the repo root.
   The dispatcher MUST NOT hand-resolve an ambiguous `<repo>` source root.
   - **Detect an existing decomposition (pre-check before step 2)** — before proposing,
     run the same resolver in `--detect-existing` mode to read the
     project's `project-map.json`. When it reports `existing: false` (no
     project-map or an empty features map), proceed unchanged (first run).
     When it reports `existing: true`, present a SUMMARY of the existing
     features and ask the user which of the three-way branch to take:
     (a) skip, (b) add only the new/unrabbified features, (c) re-decompose
     (full). The detector classifies a supplied candidate list into
     `already_rabbified` vs `new` so the "add" branch proposes only the new
     features (Invariant 8).
2. **Analyze and propose** — produce a proposed feature list as a
   structured table the user can review:
   `[{"name": "<kebab>", "purpose": "<one line>", "globs": ["..."]}, ...]`.
   In greenfield mode `globs` MAY be empty (features will be authored
   from scratch).
3. **Iterate with the user** — the user reviews, suggests additions /
   removals / boundary changes; the dispatcher updates the proposal
   and re-presents until the user accepts.
4. **Hand off** — once accepted, the dispatcher:
   - SETS the decompose-context scope-guard pass-through BEFORE any batch
     work: `scripts/handoff-scaffold.py --decompose-context set` writes the
     bounded, auto-cleared marker recording the exact accepted feature NAMES,
     so the cross-feature scaffold + spec-seed writes are authorized without
     a per-feature scope marker (Invariant 9). After ALL batch work completes
     — success OR failure — the dispatcher CLEARS it with
     `--decompose-context clear`, so the marker never lingers.
   - Runs `scripts/handoff-scaffold.py` with the accepted feature list.
     The script resolves the rabbit root, detects mode deterministically
     (reusing `rabbit-meta.lib.mode_detection.detect_mode` — NOT a single
     hard-coded `<repo>/.rabbit/.runtime/mode` read), authors the batch
     temp file with a script-owned timestamp, and dispatches the scaffolder
     on the mode-correct branch: plugin → the `rabbit-feature-scaffold` skill
     batch interface `scaffold-batch.py --batch <file>` (one
     `project-map.json` mutation, the declared cross-feature interface rather
     than a direct shell-out to rabbit-feature's `scaffold-feature.py`);
     standalone → emits the per-feature `rabbit-feature-scaffold` plan (batch
     form is plugin-only).
   - Then for each accepted feature, seeds the initial spec body by
     dispatching the `rabbit-spec-creator` subagent DIRECTLY (the prompt
     assembled by `rabbit-spec`'s `scripts/dispatch-spec-creator.py`:
     `--feature-name <name>` plus `--paths <globs>`, or no `--paths` for a
     greenfield skeleton). The subagent writes its own `docs/spec.md` and
     returns a `{path_written, summary}` handoff. Because the subagent is
     dispatched at level-1 (Invariant 4), the per-feature dispatches MAY run
     in parallel.

The protocol's exact prompt wording is owned by SKILL.md; this spec
constrains only the structural shape.

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "0.1.0"` or
   later, `owner: "rabbit-workflow team"`, `tdd_state: "test-green"`,
   non-empty `summary`, non-empty `deprecation_criterion`. The `surface`
   block MUST list the skill at `skills/rabbit-decompose/SKILL.md`. The
   `manifest` MUST contain a `publish_skill` entry sourcing the skill.
   The `prompts` array MUST be empty: rabbit-decompose runs its protocol
   inline in the dispatcher session, with no backing subagent, dispatch
   script, or slot-filled prompt template, so it owns no prompt-contract
   surface.

2. `skills/rabbit-decompose/SKILL.md` MUST exist with YAML frontmatter
   declaring `name: rabbit-decompose`, a description naming both the
   greenfield and existing-codebase scenarios, a `version` in lockstep
   with `feature.json`, `owner: rabbit-workflow team`, and a
   `deprecation_criterion`. The body documents the 4-step interactive
   protocol above.

3. `docs/contract.md` MUST exist with proper frontmatter and a
   JSON block declaring the cross-feature relationships: `invokes`
   names `rabbit-feature-scaffold` (with the `--batch` form) and the
   `rabbit-spec-creator` subagent (dispatched directly via the
   `dispatch-spec-creator.py` input assembler); `never` includes "edits the
   user's source code".

4. The spec-seeding hand-off MUST dispatch the `rabbit-spec-creator` subagent
   DIRECTLY via `Agent(subagent_type: "rabbit-spec-creator", ...)`, with the
   prompt assembled by `rabbit-spec`'s `scripts/dispatch-spec-creator.py`
   (`--feature-name <name>`, plus `--paths <globs>` for features with globs or
   no `--paths` for a greenfield skeleton). Because rabbit-decompose is a
   main-session orchestration with no intermediate subagent-dispatching skill,
   the subagent is a level-1 dispatch (main session -> rabbit-spec-creator),
   so the N per-feature dispatches MAY run in parallel. Neither `SKILL.md` nor
   this spec references a spec-create skill wrapper or a standalone input
   assembler other than `dispatch-spec-creator.py`; spec seeding dispatches the
   `rabbit-spec-creator` subagent directly.

5. Step 4's scaffold hand-off MUST be SCRIPT-tier (spec-rules §4
   Script-Backed Orchestration). The mode-aware branching, the batch
   temp-file authoring, and the scaffolder dispatch MUST live in
   `scripts/handoff-scaffold.py`; the `SKILL.md` Step 4 body invokes that
   script and MUST NOT carry a bash block with a runtime placeholder
   (e.g. `<ts>`, `<repo>`) that the model assembles at invocation time,
   nor a prose mode-branch the model executes. The script MUST detect mode
   by reusing `rabbit-meta.lib.mode_detection.detect_mode` (a cross-feature
   INVOKE declared in `docs/contract.md`), NOT by reimplementing a single
   hard-coded `<repo>/.rabbit/.runtime/mode` path read, and MUST own the
   batch file's timestamp/path (no model-assembled `<ts>`). Read-only
   informational commands in the body are exempt (§4 read-only exception).
   In plugin mode the scaffolder dispatch MUST go through the
   `rabbit-feature-scaffold` skill's batch interface
   (`skills/rabbit-feature-scaffold/scripts/scaffold-batch.py --batch <file>`,
   a contract INVOKE of rabbit-feature's published skill interface), NOT a
   direct shell-out to rabbit-feature's `scaffold-feature.py` implementation
   detail; `scaffold-batch.py` mirrors `scaffold-feature.py`'s exit codes
   0/1/2 and runs in the same cwd, so the exit-code propagation and batch-file
   authoring are preserved unchanged.

6. Step 1's decomposition SOURCE ROOT MUST be resolved by the same canonical
   resolver Step 4 uses (`scripts/handoff-scaffold.py`), so Step 1 and Step 4
   cannot disagree. The resolver detects mode via
   `rabbit-meta.lib.mode_detection.detect_mode` and returns the source root:
   in plugin mode the PARENT of the `.rabbit` install (`rabbit_root.parent`,
   matching `scaffold-feature.py._detect_plugin_mode`), in standalone mode the
   repo root itself; `--source-root` prints `{mode, source_root}` and the Step
   4 plan JSON carries the same `source_root`. The `SKILL.md` Step 1 body MUST
   reference this resolver and the plugin-mode parent-of-`.rabbit` source root,
   and MUST NOT hand-resolve an ambiguous `<repo>` source root in a live
   (non-`<!-- example -->`) bash block.

7. The default rabbit-root used for mode detection (when `--rabbit-root`
   is not supplied) MUST be the current working directory
   (`os.getcwd()`), NOT the git toplevel. In a rabbit session the cwd IS
   the mode-correct rabbit root: the vendored `.rabbit/` install dir in
   plugin mode and the repo root in standalone mode — exactly what
   `detect_mode` requires (it returns `plugin` only when the rabbit-root's
   basename is `.rabbit`). The git toplevel is WRONG for a plugin install:
   `.rabbit/` lives inside the user project's git repo, so
   `git rev-parse --show-toplevel` returns the user-project root (the
   PARENT of `.rabbit`), whose basename is not `.rabbit`, causing
   `detect_mode` to mis-classify the plugin install as `standalone` and the
   scaffolder to take the wrong (per-feature instead of plugin `--batch`)
   branch. The `SKILL.md` Step 1 and Step 4 bash blocks invoke the
   resolver WITHOUT `--rabbit-root`, relying on this corrected default, so
   they MUST resolve the mode-correct root from the cwd.

8. Before Step 2, the dispatcher MUST detect an EXISTING decomposition
   rather than blindly re-proposing the full feature set. The
   detection MUST be SCRIPT-tier: `scripts/handoff-scaffold.py
   --detect-existing` resolves mode via
   `rabbit-meta.lib.mode_detection.detect_mode` and reads the project's
   `project-map.json` (plugin → `<rabbit-root>/rabbit-project/project-map.json`;
   standalone → `<rabbit-root>/.rabbit/rabbit-project/project-map.json`,
   matching the `.rabbit/rabbit-project/project-map.json` read declared in
   `docs/contract.md`). It emits `existing: true` iff the `features` map is
   present and non-empty; a missing project-map, unparseable JSON, or an empty
   `features` map all collapse to `existing: false` (the first-run signal,
   which leaves the existing propose flow unchanged). When `existing: true` the
   JSON carries `existing_features` (the sorted SUMMARY of existing feature
   names) and `options: ["skip", "add", "re-decompose"]` (the three-way
   branch). When a candidate feature list is supplied via `--features`, the
   detector classifies candidates into `already_rabbified` (name present in the
   existing map) and `new` (absent), so the "add" branch proposes ONLY the
   new/unrabbified features. The `SKILL.md` body MUST reference the
   `--detect-existing` step, name `project-map.json`, and document the
   three-way skip / add / re-decompose branch.

9. The batch scaffold flow MUST authorize its cross-feature writes through the
   decompose-context scope-guard pass-through, NOT through the manual
   `.rabbit-scope-override` session workaround. The set/clear MUST be
   SCRIPT-tier: `scripts/handoff-scaffold.py --decompose-context set
   --features <accepted.json>` writes
   `<repo_root>/.rabbit/.runtime/decompose-active` BEFORE the batch scaffold
   and spec-seed work, and `--decompose-context clear` deletes it AFTER the
   work completes (success OR failure), so the marker never lingers. The
   marker JSON matches the scope-guard contract: a non-empty string
   `operation` (a decompose label), a non-empty list `features` carrying the
   EXACT accepted feature NAMES authorized this batch, and an OPTIONAL
   ISO-8601 `expires` defense-in-depth bound. The marker path is mode-correct
   (mirroring the project-map path resolution): plugin →
   `<rabbit_root>/.runtime/decompose-active`; standalone →
   `<rabbit_root>/.rabbit/.runtime/decompose-active`. The script's own batch
   dispatch wraps the scaffolder invocation in set-before / clear-after so a
   FAILING scaffolder still clears the marker (try/finally). That self-guard
   is OWN-ONLY: when a marker is ALREADY present (the `SKILL.md` Step 4-A set
   it to span the later spec-seed step too), the batch dispatch leaves it
   untouched — it only sets and clears a marker it itself created, so it never
   clears the outer orchestration's marker out from under the spec-seed step.
   The `SKILL.md`
   Step 4 body MUST invoke the `--decompose-context set|clear` subcommand and
   MUST NOT reference the manual `.rabbit-scope-override` session workaround
   as the recommended path.

10. `scripts/handoff-scaffold.py`'s mode-aware comparison sites MUST
    DUAL-ACCEPT both the vendored-mode values `"vendored"` and `"plugin"` —
    each `mode` comparison that selects the vendored path is written
    `mode in ("vendored", "plugin")` (inline, NOT a cross-feature helper
    import), so BOTH values take the vendored path. This covers all five
    sites: the source-root resolver (vendored → `rabbit_root.parent`), the
    project-map path resolver (vendored → `<rabbit_root>/rabbit-project/...`),
    the decompose-marker path resolver (vendored →
    `<rabbit_root>/.runtime/decompose-active`), and the two main-dispatch
    branch sites (vendored → the batch branch authoring the batch file). It is
    a forward-compatibility measure: the canonical mode value resolved by
    `rabbit-meta.lib.mode_detection.detect_mode` is currently `"plugin"`, and
    a coordinated rename to `"vendored"` is planned; dual-accepting both keeps
    this script correct before AND after that rename, so it never silently
    falls through to the standalone path when the value flips. The
    `detect_mode` resolver itself is NOT changed here; it is owned by
    rabbit-meta. Coexistence-window end-of-life: the `"plugin"` arm of each
    dual-accept is dropped only after the rename completes and the old value is
    no longer emitted anywhere, leaving the comparisons checking `"vendored"`
    alone.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Current
coverage:

- `test-docs-layout.py` (E2E — pins the feature to the flat `docs/`
  layout: `docs/spec.md` + `docs/contract.md` + `docs/CHANGELOG.md`
  present, no legacy `specs/` dir, no root `CHANGELOG.md`, four-way version
  alignment, and resolution via the contract resolver).
- `test-step4b-no-nested-dispatch.py` (E2E — asserts the spec-seeding
  hand-off, in both `SKILL.md` and `docs/spec.md`, names only the
  direct-dispatch path (the `dispatch-spec-creator.py` input assembler and a
  direct `rabbit-spec-creator` Agent dispatch) and carries no spec-create
  skill-wrapper reference and no standalone non-`creator` dispatch-script name;
  and that the `SKILL.md` Step 4-B dispatches `rabbit-spec-creator`
  directly via `Agent(subagent_type: ...)` at level-1 and states the
  per-feature dispatches may run in parallel).
- `test-prompts-spec-artifact-agree.py` (E2E — asserts Invariant 1 and the
  `feature.json` `prompts` artifact agree: `prompts` is empty, Invariant 1
  documents the empty/absent prompt-contract surface rather than requiring
  an entry, and no `templates/prompts/rabbit-decompose.txt` template exists).
- `test-step4-script-backed.py` (E2E — asserts Invariant 5: runs
  `scripts/handoff-scaffold.py` end-to-end against a temp plugin tree and a
  temp standalone tree, confirming it resolves mode via `detect_mode`
  (plugin → batch branch, standalone → per-feature plan), authors the batch
  file with a script-owned timestamp, and never reads a single hard-coded
  `<repo>/.rabbit/.runtime/mode` path; and asserts the `SKILL.md` Step 4
  body carries no prose mode-branch and no runtime-placeholder bash block,
  invoking the script instead).
- `test-step4-skill-batch-interface.py` (E2E — asserts the Invariant 5
  layering clause: runs `scripts/handoff-scaffold.py` end-to-end against a
  temp plugin tree whose rabbit-feature surface is replaced by recording
  shims, confirming the plugin-mode dispatch goes through the
  `rabbit-feature-scaffold` skill batch interface `scaffold-batch.py --batch
  <file>` and NOT a direct shell-out to `scaffold-feature.py`, that the
  authored batch JSON is preserved and handed to the skill interface
  unchanged, and that exit codes 0/1 propagate from the skill interface to
  `handoff-scaffold.py`).
- `test-step1-source-root.py` (E2E — asserts Invariant 6: runs
  `scripts/handoff-scaffold.py --source-root` end-to-end against a temp plugin
  tree and a temp standalone tree, confirming the decomposition source root is
  the parent of the `.rabbit` install in plugin mode and the repo root in
  standalone mode, that the resolution is `detect_mode`-driven, that the Step 4
  plan JSON carries the same `source_root`, and that the `SKILL.md` Step 1 body
  references the canonical resolver and no longer hand-resolves an ambiguous
  `<repo>` source root in a live bash block).
- `test-detect-existing-project-map.py` (E2E — asserts Invariant 8: runs
  `scripts/handoff-scaffold.py --detect-existing` end-to-end against temp
  plugin and standalone trees, confirming a non-empty `project-map.json`
  features map yields `existing: true` with the existing-feature SUMMARY and
  the three-way skip / add / re-decompose `options`; that a supplied candidate
  list is classified into `already_rabbified` vs `new` so "add" proposes only
  the new/unrabbified features; that a missing or empty project-map yields
  `existing: false` (first-run unchanged); that the project-map path is
  `detect_mode`-driven (plugin `rabbit-project/...` vs standalone
  `.rabbit/rabbit-project/...`); and that the `SKILL.md` body references
  `--detect-existing`, names `project-map.json`, and documents the three-way
  branch).
- `test-decompose-context-marker.py` (E2E — asserts Invariant 9: runs
  `scripts/handoff-scaffold.py --decompose-context set` end-to-end against
  temp plugin and standalone trees, confirming the bounded marker is written
  at the mode-correct path with the scope-guard schema (`operation` plus the
  exact accepted feature NAMES in `features`); that `--decompose-context
  clear` deletes it idempotently; that the script's own batch dispatch sets
  the marker before the scaffolder runs and clears it after even when the
  scaffolder FAILS (try/finally), so it never lingers; and that the `SKILL.md`
  Step 4 body invokes `--decompose-context` and no longer references the
  manual `.rabbit-scope-override` session workaround).
- `test-default-rabbit-root.py` (E2E — asserts Invariant 7: the default
  rabbit-root resolver returns the cwd; running `handoff-scaffold.py
  --source-root` WITHOUT `--rabbit-root` from a simulated plugin cwd
  (`.../.rabbit` inside a git repo) detects `plugin` and the batch branch,
  and from a repo root detects `standalone`; the corrected default keeps the
  `source_root` resolution correct (plugin → parent-of-`.rabbit`); and
  the `SKILL.md` Step 1 and Step 4 bash blocks invoke the resolver without a
  `--rabbit-root` flag, relying on the cwd default).
- `test-dual-accept-vendored-mode.py` (E2E — asserts Invariant 10: loads
  `scripts/handoff-scaffold.py` and drives each of the five vendored-mode
  comparison sites with BOTH `"vendored"` and `"plugin"`, confirming the three
  path resolvers return the SAME vendored path for both values and a different
  path for `"standalone"`, and that a `"vendored"`-mode `--plan-only` run takes
  the same batch branch as a `"plugin"`-mode run while `"standalone"` takes the
  per-feature branch).

## Out of Scope

- The actual analysis algorithm that turns a codebase into a feature
  list — encoded in the skill prose, not the spec. Iteration on the
  prompt happens in the SKILL.md, not here.
- Writing the user's source code or modifying it in any way.
- Replacing rabbit-feature-scaffold or the rabbit-spec-creator subagent —
  those remain the building blocks rabbit-decompose orchestrates.
