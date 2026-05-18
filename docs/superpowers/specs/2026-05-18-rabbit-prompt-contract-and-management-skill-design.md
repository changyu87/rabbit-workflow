# Rabbit Prompt Contract and Management Skill — Design

**Status:** Draft
**Date:** 2026-05-18
**Owner:** rabbit-self (contract feature for cross-cutting infra; rabbit-cage for user surface)
**Version (of this design):** 0.1.0
**Tracked under:** CONTRACT-BACKLOG-1
**Supersedes:** CONTRACT-BACKLOG-11, TDD-SUBAGENT-BACKLOG-1, TDD-SUBAGENT-BACKLOG-5,
TDD-SUBAGENT-BACKLOG-8 (all closed 2026-05-18 as superseded by this work)

---

## Goal

Make every subagent / managed-agent dispatch in rabbit-workflow operate on a
**versioned schema-defined payload** rather than free-form text assembled in
prose. Provide a structured human surface (the `/rabbit-prompt` skill) for
inspecting, editing, and auditing those payloads. Aligns with `philosophy.md`
(Machine First) and `spec-rules.md` sections 2-3 (schemas at every boundary,
versioned contracts).

## Motivation

Today each dispatch script (`dispatch-tdd-subagent.py`, `dispatch-feature-edit.py`,
`dispatch-spec-update.py`, `resolve-scope.py`, and the inline eval-subagent
prose in `rabbit-file/SKILL.md`) constructs its subagent prompt by interpolating
strings. There is:

- No schema for what sections a prompt MUST/MAY contain
- No validation that the assembled prompt is well-formed
- No structured representation that a human can inspect or edit
- No contract for the subagent's response (HANDOFF is implicit free text)
- No mechanism to audit a prompt for internal consistency before dispatch

A user-suggested implementation note on CONTRACT-BACKLOG-1 frames the fix:
*"Model this as a contract — define a versioned schema for what constitutes
a subagent prompt payload, so each injected section is a named, typed field.
The human interface operates on the schema, not on raw text. This makes
inspection and editing structured and auditable rather than free-form string
manipulation."*

This design implements that note, extends it to handoff (response) schemas,
and adds a mandatory audit step for the human-facing workflow.

## Research: Anthropic-blessed prompt contract?

Official Anthropic documentation (Claude Code subagents, Skill tool, Managed
Agents API, tool-context-management) defines **no schema or structured
format** for subagent / skill prompt context. All such handoffs are
free-form text composed by the caller. Conclusion: we are inventing our own
convention; no upstream standard to align with. This is consistent with
philosophy.md and spec-rules.md, which already mandate schema-bound boundaries
for every cross-component handoff.

## Inventory of dispatch points (the "prompt engineering work points")

Today rabbit has **5 dispatch points**. This design adds one more (audit),
bringing the total to **6**:

| # | Dispatch | Owning feature | Today's prompt source | Subagent model |
|---|---|---|---|---|
| 1 | tdd-subagent          | tdd-subagent          | dispatch-tdd-subagent.py     | Opus    |
| 2 | feature-edit          | contract              | dispatch-feature-edit.py     | Default |
| 3 | spec-update           | contract              | dispatch-spec-update.py      | Opus    |
| 4 | scope-resolve         | rabbit-feature-scope  | resolve-scope.py             | Default |
| 5 | eval-subagent         | rabbit-file           | **inline prose in SKILL.md** | Default |
| 6 | audit-prompt (**new**)| contract              | dispatch-audit-prompt.py (new) | Default |

Notes:
- **#5 is the immediate violator** — its prompt lives as markdown prose in
  `rabbit-file/SKILL.md`, not as code. This refactor brings it into the
  same pattern as #1-4 (a dedicated `dispatch-eval-subagent.py`).
- **#6 is new** — the audit subagent operates on the rendered text of
  any other dispatch's prompt and returns a structured verdict.

## Architectural choices

### 1. Base + extension schema model

Schemas split by file location:

- **`base.payload.schema.yaml`** — shared invariant content/fields that
  apply to every dispatch (policy block, scope-marker instructions,
  schema_version, owner, dispatch_target, generated_at metadata, etc.).
  Ships with rabbit. User does not edit. Drift-check covers it.
- **`<dispatch>.payload.schema.yaml`** — per-dispatch editable content/fields
  (defaults, options, knobs specific to one dispatch point). Ships with
  rabbit but is the field of user customization. Edits commit to the
  user project's `.rabbit/` and take effect for that project only.

Same split applies to handoff (response) schemas:

- **`base.handoff.schema.yaml`** — invariant response envelope
  (schema_version, dispatch_name, status, generated_at).
- **`<dispatch>.handoff.schema.yaml`** — per-dispatch response body shape.

Invariance is determined by file location, not by markers within a file.
Base = invariant by definition; extension = editable by definition.

### 2. No user override file

Earlier drafts proposed `.rabbit/rabbit-project/prompt-overrides/<dispatch>.yaml`
as a persistent user-customization layer. **Dropped.** Users edit the
extension schema yaml directly. Because the full `.rabbit/` is committed to
the user project (per CONTRACT-BACKLOG-17), per-project scope is automatic
and side-effect-free across projects.

### 3. No `.runtime/prompts/` ephemeral payload files

Earlier drafts proposed writing a runtime payload instance to
`.rabbit/.runtime/prompts/<dispatch>-<ts>.yaml` per dispatch call.
**Dropped.** Rendering happens in memory: a common `render-prompt.py`
script takes (base schema, extension schema, dispatcher-computed dynamics)
and returns the prompt text. The dispatcher pipes the text directly to
the Agent call. Nothing on disk per call.

### 4. Common renderer in contract

A single `render-prompt.py` (in `contract/scripts/`) is the only thing
that produces prompt text from schemas. All 6 dispatchers call it. Pure
function: `(schemas + dynamics) → text`.

Parallel script for handoff validation: `validate-handoff.py` checks
subagent responses against the dispatch's handoff schema.

### 5. Audit is a first-class dispatch (the 6th)

The audit step is itself a subagent call, so it gets the same contract
treatment as the other five:

- `audit-prompt.payload.schema.yaml` — input fields: target rendered
  prompt, target dispatch name, checklist of concerns (internal consistency,
  self-contradiction, mis-interpreted terms, ambiguous goals).
- `audit-prompt.handoff.schema.yaml` — output fields: overall verdict,
  list of issues with `{category, severity, location, recommendation}`.

Lives in `contract/` (cross-cutting infra, not bound to any single
dispatch).

### 6. Advisory, never blocking

Audit verdicts are surfaced to the user but never block dispatch. Severity
in the handoff schema drives UI emphasis only. Rationale: an LLM in the
critical path of every dispatch is brittle; the user retains the decision.

### 7. Skill in rabbit-cage; cross-cutting infra in contract

Clean Bounded-Scope split:

- **contract** owns: base schemas, render-prompt.py, validate-handoff.py,
  dispatch-audit-prompt.py and its schemas, the Stop-hook drift checker.
  All cross-cutting infrastructure.
- **rabbit-cage** owns: the new `/rabbit-prompt` skill (user-facing
  inspect/edit/audit workflow). Matches today's pattern where all
  user-facing skills (rabbit-config, rabbit-workspace-map, etc.) live
  in rabbit-cage.
- **Each dispatch's owning feature** owns: its own dispatch script and
  the two extension schemas (payload + handoff).

### 8. No new `/rabbit-config` subcommands

Zero new config toggles. The minimal interface is intentional:

- Drift warning is informative (one-shot per Stop hook); no toggle needed.
- Audit is mandatory inside the skill; if you want to skip audit, don't
  use the skill (edit yaml directly). No disarm flag.
- No restore action — drift is warn-only, no auto-restore.
- No manual snapshot refresh — drift baseline is the on-disk file
  content as of the last Stop hook (see Drift detection below).

### 9. Per-call edits are text-level, ephemeral

The skill's EDIT action opens the rendered prompt text in `$EDITOR`,
captures the edited string, sends it. Per-call edits are NOT persisted
and NOT schema-validated (they're an escape hatch). For persistent
customization, edit the extension schema yaml.

## File inventory

```
.rabbit/.claude/features/

contract/
├── payload-schemas/
│   ├── base.payload.schema.yaml             [shared invariant input fields]
│   └── base.handoff.schema.yaml             [shared invariant response envelope]
└── scripts/
    ├── render-prompt.py                     [common renderer: (schemas, dynamics) → text]
    ├── validate-handoff.py                  [common handoff validator]
    ├── dispatch-audit-prompt.py             [audit dispatcher]
    ├── audit-prompt.payload.schema.yaml
    ├── audit-prompt.handoff.schema.yaml
    ├── dispatch-feature-edit.py             [existing; refactor to use renderer]
    ├── feature-edit.payload.schema.yaml     [new]
    ├── feature-edit.handoff.schema.yaml     [new]
    ├── dispatch-spec-update.py              [existing; refactor]
    ├── spec-update.payload.schema.yaml      [new]
    └── spec-update.handoff.schema.yaml      [new]

tdd-subagent/scripts/
├── dispatch-tdd-subagent.py                 [existing; refactor]
├── tdd-subagent.payload.schema.yaml         [new]
└── tdd-subagent.handoff.schema.yaml         [new]

rabbit-feature-scope/scripts/
├── resolve-scope.py                         [existing; refactor]
├── scope-resolve.payload.schema.yaml        [new]
└── scope-resolve.handoff.schema.yaml        [new]

rabbit-file/scripts/
├── dispatch-eval-subagent.py                [new — replaces inline prose in SKILL.md]
├── eval-subagent.payload.schema.yaml        [new]
└── eval-subagent.handoff.schema.yaml        [new]

rabbit-cage/
└── skills/rabbit-prompt/SKILL.md            [new skill]

.rabbit/.claude/hooks/
└── prompt-drift-check.py                    [new Stop hook — pure filesystem]

.rabbit/.runtime/
└── prompt-checksums.json                    [hook state, gitignored]
```

**Source-controlled count:** 2 base schemas + 12 extension schemas
(6 payload + 6 handoff) + 4 contract scripts + 6 dispatch scripts +
1 hook + 1 skill = **~26 source files**, distributed by ownership.

**Ephemeral count:** 1 (checksums cache for the Stop hook).

## Flows

### Default dispatch flow (no skill involvement)

```
[dispatcher-X.py]
   │ computes dynamic fields (current TDD state, find-feature output, etc.)
   │
   ├─► render-prompt.py(base.payload.schema, X.payload.schema, {dynamics})
   │       │ validates merged data against {base + extension}
   │       └─► returns prompt text
   │
   ├─► Agent(prompt: text)
   │       │
   │       └─► returns raw response text
   │
   └─► validate-handoff.py(base.handoff.schema, X.handoff.schema, response)
           │ parses + validates
           └─► returns structured handoff or raises
```

No state on disk per call. No user prompts. The skill is not involved.

### Persistent customization flow

```
1. User opens .rabbit/.claude/features/<feature>/scripts/<dispatch>.payload.schema.yaml
2. Edits a field (e.g., changes a default value)
3. Saves
4. Next Stop hook detects drift, prints one-time warning naming the file
5. User runs /rabbit-prompt (optional) to inspect and audit the new state
6. User commits .rabbit/ — change travels with their project repo
```

### `/rabbit-prompt` skill flow (opt-in)

```
User invokes /rabbit-prompt for some dispatch <X>:

1. Skill calls render-prompt.py for X with current schemas + plausible dynamics
2. Shows rendered prompt text
3. User picks: SEND / EDIT / CANCEL
4. If EDIT:
     - Open $EDITOR with rendered text
     - Capture edited string
5. Mandatory AUDIT:
     - Dispatch audit-prompt subagent with (rendered text, dispatch name, checklist)
     - Show structured verdict + issues (advisory)
6. User picks: SEND / RE-EDIT / CANCEL
```

### Drift detection (Stop hook)

```
On every Claude Code Stop event:

1. Glob .rabbit/.claude/features/**/*.{payload,handoff}.schema.yaml
   + base.payload.schema.yaml + base.handoff.schema.yaml
2. Compute SHA-256 of each
3. Compare against .rabbit/.runtime/prompt-checksums.json (empty on first run)
4. If any differ: print "[rabbit] N prompt schemas changed since last check: …
                          Use /rabbit-prompt to inspect and audit."
5. Overwrite .rabbit/.runtime/prompt-checksums.json with current values
```

Pure filesystem. ~30 lines of stdlib Python. No git involvement. Works
on brownfield (non-git) projects. Concurrent-safe via standard `flock`
on the checksums file.

## Drift detection rationale

The question being answered is **"did this change since we last looked?"** —
which a filesystem checksum compare answers exactly. Git would answer a
different question (*"did this change since last commit?"*) and would have
false positives for unrelated stale-commit cases.

Storing the checksums file in `.rabbit/.runtime/` makes it per-machine and
gitignored — each user's hook tracks their own "last seen" state. When Alice
commits a schema edit and Bob pulls, Bob's next Stop hook compares his new
file content to his old last-known and warns once. No cross-machine
coordination needed.

## What this design does NOT do (out of scope)

- **Standard-workflow guidance for non-developer users.** Originally bundled
  in this brainstorm; carved out and filed as **CONTRACT-BACKLOG-18**
  ("Consolidate standard workflow guidance into rabbit-workspace-map").
  The `/rabbit-prompt` skill is for power users tuning prompts, not for
  onboarding.
- **Default-on dispatch-time pause.** The skill is opt-in; dispatches do
  NOT gate on inspect/edit by default.
- **Block-on-audit-failure.** Audit is advisory only.
- **Manual snapshot refresh, restore action, or any user-managed baseline.**
  Drift baseline is the last seen filesystem state; no manual checkpoints.
- **Cross-machine coordination of "drift seen."** Each machine maintains
  its own checksums file.
- **Multi-version prompt schemas in one project.** Each rabbit clone runs
  one version of all schemas (per CONTRACT-BACKLOG-17).
- **Audit-model selection or iteration tuning.** Audit dispatcher uses
  the default model; no per-call tuning.
- **Automatic re-render preview on every edit.** User explicitly invokes
  `/rabbit-prompt` for preview/audit.

## Deferred items (to v2 or follow-up)

| Item | Reason |
|---|---|
| Audit checklist content (specific concerns enumerated) | Implementation-level; will be defined when writing audit.payload.schema.yaml |
| Exact field set for each per-dispatch schema | Implementation-level; emerges from dispatcher refactor |
| Migration path for in-flight dispatchers being refactored | Implementation plan concern |
| Render template language (Jinja vs string.Template vs custom) | Implementation choice in render-prompt.py |
| Skill UX details (terminal rendering, syntax highlighting, etc.) | Implementation choice in SKILL.md |
| Test command discovery for tdd-subagent (project-map.json field) | Tied to CONTRACT-BACKLOG-17 implementation |

## Open implementation questions (for writing-plans phase)

1. **Schema definition format** — JSON Schema embedded in YAML?
   YAML-native schema dialect? Custom?
2. **Section ordering in rendered text** — declared by base schema or by
   each extension?
3. **How dispatcher passes "dynamics" to renderer** — CLI args? stdin
   JSON? environment?
4. **Handoff validation failure handling** — retry, surface error, fail
   loud?
5. **Hook event for drift check** — Stop only, or also SessionStart?
6. **Skill name finalization** — `/rabbit-prompt` is the working name;
   could be `/rabbit-prompts`, `/prompt`, etc.

## Coordination with CONTRACT-BACKLOG-17

This design assumes the plugin layout from CONTRACT-BACKLOG-17 (rabbit
installed at `<user-project>/.rabbit/`, fully committed, with
`.rabbit/.runtime/` gitignored for ephemerals). The two designs are
compatible but independent:

- **-17 must land before -1 implementation can fully realize the
  per-project-edit story.** Without -17, schema edits don't naturally
  travel with the user's project.
- **-1 can be implemented in part on rabbit-self today** (the dispatcher
  refactors, render-prompt.py, base schemas, audit dispatch, Stop hook,
  skill) without -17. Per-project benefits emerge once -17 ships.

## Lifecycle

- **Owner:** rabbit-self team (contract + rabbit-cage co-ownership).
- **Version of this design:** 0.1.0.
- **Deprecation criterion:** Superseded when (a) the v1 implementation
  lands and replaces this design with a `v1-as-built.md`, or (b) a
  fundamentally different prompt-contract model is chosen.

## Brainstorming history (key decision points)

Sequential pruning during a 2026-05-18 brainstorming session:

1. **Initial framing included UX-for-non-developers.** → Carved out:
   workflow guidance is a separate concern; backlogged as
   CONTRACT-BACKLOG-18. This spec is for power users.
2. **Researched whether Anthropic ships a prompt contract.** → No; we
   are inventing our own, which is consistent with rabbit philosophy.
3. **Inventoried 5 existing dispatch points; identified #5 (eval-subagent)
   as inline prose in SKILL.md.** → Refactor brings it into pattern.
4. **Cluster analysis of 13 "prompt"-tagged backlog items.** → Identified
   4 that collapse into -1 (BACKLOG-11, TDD-SUBAGENT-1, -5, -8); closed
   them as superseded.
5. **Picked schema scope: B (base + extensions).** → Per-dispatch (A)
   too fragmented; unified (C) invites drift.
6. **Dropped user override file.** → User edits payload schema directly;
   per-project scope via `.rabbit/` commit.
7. **Dropped `.runtime/prompts/` ephemeral payload files.** → Rendering
   in memory; common renderer in contract.
8. **Corrected invariance model.** → File location determines invariance
   (base = invariant, extension = editable), not markers within a file.
9. **Added handoff schemas.** → Symmetric to payload; folds in
   TDD-SUBAGENT-BACKLOG-7 concerns.
10. **Added audit as 6th dispatch point.** → Mandatory in skill flow.
11. **Audit is advisory, never blocks.** → LLM-in-critical-path is brittle.
12. **Skill in rabbit-cage; cross-cutting infra in contract.** → Clean
    Bounded-Scope split.
13. **Zero new `/rabbit-config` subcommands.** → Drift is one-shot
    informational; audit-disarm is a footgun; restore was already dropped.
14. **Stop hook for drift detection, pure filesystem.** → Answers the
    actual question ("changed since last look?"); no git dependency;
    works on brownfield projects.
