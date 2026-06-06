---
feature: rabbit-decompose
version: 0.8.0
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
pipeline (the `rabbit-feature-scaffold` skill's `--batch` interface then
`rabbit-spec-create` per feature).

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
  `rabbit-feature-scaffold` plan)
- `docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`, `feature.json`,
  `test/run.py` — feature scaffolding

The interactive protocol (Steps 1–3) runs inline in the dispatcher session.
Step 4's mode detection, batch-file authoring, and scaffolder dispatch are
SCRIPT-tier: the SKILL invokes `scripts/handoff-scaffold.py` rather than
assembling mode branches and runtime placeholders in prose (spec-rules §4
Script-Backed Orchestration). The spec-create seeding remains inline
sequential `Skill(...)` calls under the nesting constraint of Invariant 4.

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
2. **Analyze and propose** — produce a proposed feature list as a
   structured table the user can review:
   `[{"name": "<kebab>", "purpose": "<one line>", "globs": ["..."]}, ...]`.
   In greenfield mode `globs` MAY be empty (features will be authored
   from scratch).
3. **Iterate with the user** — the user reviews, suggests additions /
   removals / boundary changes; the dispatcher updates the proposal
   and re-presents until the user accepts.
4. **Hand off** — once accepted, the dispatcher:
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
   - Then for each accepted feature with non-empty `globs`, invokes
     `rabbit-spec-create` (one sequential `Skill(...)` call per feature)
     to seed the initial spec body, under the nesting constraint of
     Invariant 4.

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
   names `rabbit-feature-scaffold` (with the `--batch` form) and
   `rabbit-spec-create`; `never` includes "edits the user's source
   code".

4. The spec-create hand-off MUST invoke `rabbit-spec-create` as a
   sequential `Skill(...)` call from the main session and MUST NOT wrap
   it in an `Agent(...)` dispatch: `rabbit-spec-create` itself dispatches
   the `rabbit-spec-creator` subagent, so wrapping it in `Agent(...)`
   creates an unsupported two-level subagent nesting chain. Neither
   `SKILL.md` nor this spec may claim the spec-create calls can be
   parallelized via the Agent tool.

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

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Current
coverage:

- `test-docs-layout.py` (E2E — pins the feature to the flat `docs/`
  layout: `docs/spec.md` + `docs/contract.md` + `docs/CHANGELOG.md`
  present, no legacy `specs/` dir, no root `CHANGELOG.md`, four-way version
  alignment, and resolution via the contract resolver).
- `test-step4b-no-nested-dispatch.py` (E2E — asserts the spec-create
  hand-off, in both `SKILL.md` and `docs/spec.md`, never claims
  `rabbit-spec-create` can be Agent-parallelized, states the calls run
  sequentially, and names the two-level subagent-nesting constraint that
  makes the sequential level-1 hand-off mandatory).
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
- `test-default-rabbit-root.py` (E2E — asserts Invariant 7: the default
  rabbit-root resolver returns the cwd; running `handoff-scaffold.py
  --source-root` WITHOUT `--rabbit-root` from a simulated plugin cwd
  (`.../.rabbit` inside a git repo) detects `plugin` and the batch branch,
  and from a repo root detects `standalone`; the corrected default keeps the
  `source_root` resolution correct (plugin → parent-of-`.rabbit`); and
  the `SKILL.md` Step 1 and Step 4 bash blocks invoke the resolver without a
  `--rabbit-root` flag, relying on the cwd default).

## Out of Scope

- The actual analysis algorithm that turns a codebase into a feature
  list — encoded in the skill prose, not the spec. Iteration on the
  prompt happens in the SKILL.md, not here.
- Writing the user's source code or modifying it in any way.
- Replacing rabbit-feature-scaffold or rabbit-spec-create — those skills
  remain the building blocks rabbit-decompose orchestrates.
