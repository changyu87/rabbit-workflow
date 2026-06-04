---
feature: rabbit-decompose
version: 0.5.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native feature-decomposition assistance that supersedes this skill
status: active
---

# rabbit-decompose — Spec

## Purpose

rabbit-decompose proposes a feature decomposition for the user to review,
edit, and accept. It is the "upstream scoper" that addresses the question
the rest of the rabbit workflow can't answer on its own: *given a high-level
intent or an existing codebase, what should the features actually be?*

Two scenarios drive the design:

- **Greenfield** — user supplies a spec, design doc, or natural-language
  description of the system. rabbit-decompose proposes a feature list
  with names, purposes, and (optionally) path globs the future scaffolds
  should govern.
- **Existing codebase** — user points at a directory or supplies a
  project root. rabbit-decompose analyzes the surface and proposes a
  feature decomposition: each feature with a name, a one-line purpose,
  and the path globs it should govern.

In both cases the output is the same: an *accepted feature list* that
feeds the downstream pipeline (`rabbit-feature-scaffold --batch` then
`rabbit-spec-create` per feature).

## Surface

- `skills/rabbit-decompose/SKILL.md` — the user-invocable skill
- `docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`, `feature.json`,
  `test/run.py` — feature scaffolding

No backing agent or dispatch script in this MVP — the dispatcher Claude
runs the interactive protocol inline. A `decomposer` subagent for batch
analysis of large codebases is a deferred follow-up.

## Interactive Protocol

The skill is interactive by design. The dispatcher MUST:

1. **Gather inputs** — confirm with the user which scenario applies
   (greenfield vs existing codebase) and gather the source material
   (spec text, design doc path, or codebase root).
2. **Analyze and propose** — produce a proposed feature list as a
   structured table the user can review:
   `[{"name": "<kebab>", "purpose": "<one line>", "globs": ["..."]}, ...]`.
   In greenfield mode `globs` MAY be empty (features will be authored
   from scratch).
3. **Iterate with the user** — the user reviews, suggests additions /
   removals / boundary changes; the dispatcher updates the proposal
   and re-presents until the user accepts.
4. **Hand off** — once accepted, the dispatcher:
   - In plugin mode, writes the accepted list to a tmp file and runs
     `scaffold-feature.py --batch <file>` to scaffold all features
     and register them in `project-map.json`.
   - In standalone mode, invokes `rabbit-feature-scaffold` per
     accepted feature individually (batch form is plugin-only).
   - Then for each accepted feature with non-empty `globs`, invokes
     `rabbit-spec-create` to seed the initial spec body. `rabbit-spec-create`
     is itself a subagent-dispatching skill — it internally dispatches the
     `rabbit-spec-creator` subagent via the Agent tool. It MUST therefore be
     invoked as a sequential `Skill("rabbit-spec-create", ...)` call from the
     main session, never wrapped inside an `Agent(...)` call: wrapping a
     subagent-dispatching skill in an Agent dispatch produces an illegal
     two-level subagent nesting chain that Claude Code does not support. The
     spec-create calls run sequentially, one per accepted feature.

The protocol's exact prompt wording is owned by SKILL.md; this spec
constrains only the structural shape.

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "0.1.0"` or
   later, `owner: "rabbit-workflow team"`, `tdd_state: "test-green"`,
   non-empty `summary`, non-empty `deprecation_criterion`. The `surface`
   block MUST list the skill at `skills/rabbit-decompose/SKILL.md`. The
   `manifest` MUST contain a `publish_skill` entry sourcing the skill.
   The `prompts` array MUST contain exactly one entry with
   `id: "rabbit-decompose"`, `kind: "skill"`, `inject` listing
   philosophy + spec-rules, and `slots: ["args"]`.

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
   code" (rabbit-decompose proposes; it does not modify code).

4. The spec-create hand-off MUST invoke `rabbit-spec-create` as a
   sequential `Skill(...)` call from the main session and MUST NOT wrap
   it in an `Agent(...)` dispatch. `rabbit-spec-create` is itself a
   subagent-dispatching skill (it dispatches the `rabbit-spec-creator`
   subagent via the Agent tool); wrapping it in an `Agent(...)` call
   would create a two-level subagent nesting chain
   (decompose -> Agent level-1 -> rabbit-spec-creator level-2), which
   Claude Code does not support. Neither `SKILL.md` nor this spec may
   claim the spec-create calls can be parallelized via the Agent tool.

## Tech Stack

No Python script in this MVP — the skill is dispatcher-orchestrated.
Future enhancement: add a `decomposer` subagent and `dispatch-decompose.py`
for parallel large-codebase analysis.

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

## Out of Scope

- The actual analysis algorithm that turns a codebase into a feature
  list — encoded in the skill prose, not the spec. Iteration on the
  prompt happens in the SKILL.md, not here.
- Writing the user's source code or modifying it in any way.
- Replacing rabbit-feature-scaffold or rabbit-spec-create — those skills
  remain the building blocks rabbit-decompose orchestrates.
- A decomposer subagent — deferred. The MVP uses dispatcher-level
  cognition for the analysis step.
