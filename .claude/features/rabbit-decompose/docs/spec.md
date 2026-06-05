---
feature: rabbit-decompose
version: 0.5.4
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
pipeline (`rabbit-feature-scaffold --batch` then `rabbit-spec-create` per
feature).

## Surface

- `skills/rabbit-decompose/SKILL.md` — the user-invocable skill
- `docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`, `feature.json`,
  `test/run.py` — feature scaffolding

No backing agent or dispatch script in this MVP — the dispatcher Claude
runs the interactive protocol inline.

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

## Out of Scope

- The actual analysis algorithm that turns a codebase into a feature
  list — encoded in the skill prose, not the spec. Iteration on the
  prompt happens in the SKILL.md, not here.
- Writing the user's source code or modifying it in any way.
- Replacing rabbit-feature-scaffold or rabbit-spec-create — those skills
  remain the building blocks rabbit-decompose orchestrates.
