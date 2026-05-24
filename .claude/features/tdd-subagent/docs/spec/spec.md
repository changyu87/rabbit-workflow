---
feature: tdd-subagent
version: 3.3.0
owner: rabbit-workflow team
template_version: 2.1.0
deprecation_criterion: When subagent dispatch is replaced by a different orchestration mechanism (e.g., direct rabbit-CLI orchestration without a dispatch-prompt assembler).
status: active
---

# tdd-subagent — Spec

## Purpose

Provides `dispatch-tdd-subagent.py` (a prompt assembler) and the
`tdd-subagent` agent definition. The assembled prompt drives a single
feature through the 9-step TDD cycle
(SPEC-READ → HUMAN-APPROVAL → LOCK → TEST-WRITE → TEST-RED → IMPLEMENT →
CODE-REVIEW → TEST-GREEN → UNLOCK).

The TDD state machine (`tdd-step.py`, `tdd-context.py`,
`tdd-drift-check.py`) is owned by `tdd-state-machine`. The
`rabbit-feature-touch` orchestration skill that consumes this feature's
dispatch prompt is owned by `rabbit-feature`.

## Scripting Tech Stack

All scripts in this feature are Python 3 standard library. Bash is not
used in runtime scripts, test harnesses, or fixtures. The sole test
runner is `test/run.py`.

## Surface

- `scripts/dispatch-tdd-subagent.py` — assembles a per-feature TDD-cycle
  prompt to stdout; the script itself does not invoke any agent.
- `agents/tdd-subagent.md` — the agent definition dispatched by callers
  using the assembled prompt.

## Pre-Conditions

`dispatch-tdd-subagent.py`'s STEP 1 SPEC-READ diffs the spec against
`HEAD~1` (Inv 13). Callers MUST commit the spec file referenced by
`--spec` BEFORE invocation; otherwise the diff returns the wrong delta.
Codification of the upstream commit obligation lives in the caller's
spec (`rabbit-feature`).

## Invariants

### Surface scope

1. **Owned surface.** This feature owns exactly two surface entries:
   `scripts/dispatch-tdd-subagent.py` and `agents/tdd-subagent.md`.
   No state-machine script (`tdd-step.py`, `tdd-context.py`,
   `tdd-drift-check.py`) appears under
   `.claude/features/tdd-subagent/scripts/`. References to a state-machine
   script from within this feature resolve to its path under
   `.claude/features/tdd-state-machine/scripts/`.

2. **`feature.json` surface fields.** `surface.hooks`, `surface.commands`,
   and `surface.skills` in `feature.json` are each `[]`. This feature
   exposes no hooks, commands, or skills.

### Dispatch script — CLI shape

3. **Output mode.** `dispatch-tdd-subagent.py` writes the assembled
   prompt to stdout and exits without invoking any agent. Exit codes:
   `0` success, `2` invocation error (missing required flag, missing
   `--spec` file, malformed `--linked-items` triple, missing
   `--item-type` paired with `--linked-item` or vice versa,
   `--max-iterations < 1`, unknown `--scope` feature, malformed
   `--linked-item` path layout — see Inv 30).

4. **Flag set.** `dispatch-tdd-subagent.py` accepts exactly these flags:
   `--scope` (required), `--spec` (required),
   `--impl-suggestion` (optional path),
   `--linked-item` + `--item-type bug|backlog` (optional primary item),
   `--linked-items <feature>:<type>:<id>[,...]` (optional secondary items;
   `<type>` ∈ {`bug`, `backlog`}),
   `--human-approval-gate true|false` (default `true`),
   `--code-review-full-loop` (boolean flag),
   `--max-iterations N` (default `3`, minimum `1`).

5. **Boolean flag vocabulary.** Boolean values for `--human-approval-gate`
   are exactly `true` or `false`. No other vocabulary
   (`enabled`/`disabled`, `yes`/`no`, etc.) is accepted.

6. **`--linked-items` validation.** Each comma-separated entry MUST have
   exactly two colons separating non-empty `<feature>`, `<type>`, `<id>`
   fields, with `<type>` ∈ {`bug`, `backlog`}. Any malformed entry causes
   exit `2` with a diagnostic on stderr BEFORE any stdout is emitted.

### Dispatch script — prompt content

7. **Scope marker convention.** The assembled prompt instructs the
   subagent to use `.rabbit-scope-active-<feature-name>` as its sole
   scope marker, written at LOCK and removed at UNLOCK. Distinct
   per-feature markers permit simultaneous dispatch across features.

8. **9-step section banners.** The assembled prompt contains a labelled
   section per step using the names `SPEC-READ`, `HUMAN-APPROVAL`,
   `LOCK`, `TEST-WRITE`, `TEST-RED`, `IMPLEMENT`, `CODE-REVIEW`,
   `TEST-GREEN`, `UNLOCK`, in that order.

9. **E2E test rule.** The assembled prompt declares that every spec
   behaviour MUST have a corresponding end-to-end test, and that the
   subagent adds missing e2e tests in TEST-WRITE.

10. **Scope-boundary red flag.** The assembled prompt forbids the
    subagent from creating any `.rabbit-scope-active-<X>` marker where
    `<X>` differs from the declared scope feature. If implementation
    requires writing under another feature's directory, the subagent
    STOPS and emits a blocked HANDOFF with fields `tdd_state: blocked`,
    `test_result: not_run`, `cross_feature_dependency: <X>`,
    `unwritten_paths: [<path>, ...]`, and `notes: <one sentence>`.

11. **SKILL.md routing rule.** The assembled prompt's IMPLEMENT step
    instructs the subagent to invoke
    `Skill("skill-creator:skill-creator")` before editing any file whose
    basename is `SKILL.md`. Direct Write/Edit on a `SKILL.md` is
    forbidden.

12. **LOCK / UNLOCK marker discipline.** The assembled prompt's LOCK
    step writes only `touch <repo_root>/.rabbit-scope-active-<feature>`
    and registers no shell trap. The UNLOCK step removes the marker
    explicitly via `rm -f <repo_root>/.rabbit-scope-active-<feature>`
    after the chore commit and before HANDOFF.

13. **SPEC-READ diff target.** The assembled prompt's SPEC-READ step
    runs `git diff HEAD~1 -- <feature_dir>/docs/spec/`.

14. **IMPLEMENT commit ordering.** Within the IMPLEMENT step, the
    assembled prompt instructs the subagent to commit
    (`git add <feature_dir>/ && git commit -m
    "fix|feat(<feature>): <summary>"`) inside the iteration loop and
    BEFORE the `tdd-step.py transition <feature_dir> impl` call.

15. **TEST-GREEN impl-SHA capture.** The assembled prompt's TEST-GREEN
    step captures `IMPL_SHA=$(git rev-parse HEAD)` and writes
    `<repo_root>/.rabbit/tdd-report-<feature>.json` with `impl_commit`
    bound to that SHA, BEFORE the UNLOCK chore commit advances HEAD.

16. **UNLOCK chore commit.** The assembled prompt's UNLOCK step commits
    the `feature.json` `tdd_state: test-green` transition with message
    pattern `chore(<feature>): advance tdd_state to test-green` BEFORE
    emitting HANDOFF.

17. **CODE-REVIEW skill invocation.** The assembled prompt's CODE-REVIEW
    step invokes `Skill("superpowers:requesting-code-review")`. The
    skill name is exact and case-sensitive.

18. **Read-before-Edit warning.** The assembled prompt's IMPLEMENT step
    states that any `Edit`/`Write` against an existing file MUST be
    preceded by a `Read` in the same session, as the Claude Code Edit
    tool rejects edits on un-Read files.

### Linked-item closure

19. **Primary linked-item closure.** When invoked with `--linked-item
    <dir> --item-type <type>`, the assembled prompt instructs the
    subagent to close the item after test-green via:
    `python3 .claude/features/rabbit-file/scripts/item-status.py set
    --feature <feature> --type <type> --id <id> --status close
    --reason 'TDD cycle complete' --fix-commits <IMPL_SHA>`.
    `<feature>` and `<id>` are derived from the `--linked-item` path
    (penultimate-two segments and final segment respectively).

20. **Secondary linked-items closure.** Each `--linked-items` entry
    triggers an additional `item-status.py set ... --status close
    --reason 'TDD cycle complete (secondary item resolved by same
    commit)' --fix-commits <IMPL_SHA>` invocation in the assembled
    prompt.

21. **HANDOFF closed-items listing.** The assembled prompt's HANDOFF
    block lists every closed item (primary + secondaries) under
    `closed_items`. When no items are closed, `closed_items` is an empty
    list in the JSON HANDOFF and omitted from the YAML block.

### `--linked-item` path-layout validation

30. **`--linked-item` path layout.** When `--linked-item <path>` is
    provided, `dispatch-tdd-subagent.py` validates that the path
    conforms to the rabbit-file storage layout
    `.../rabbit/features/<feature>/<bugs|backlogs>/<id>/` BEFORE any
    stdout is emitted. The path is resolved (via `Path.resolve()`),
    and the resolved path's segments are checked: the segment at
    position `-4` MUST equal `features`, and the segment at position
    `-2` MUST equal `bugs` or `backlogs` (matching the rabbit-file
    storage layout, where `<type>` ∈ {`bug`, `backlog`} and the
    containing directory is the pluralised form). A non-conforming
    path causes exit `2` with a stderr diagnostic naming both the
    expected layout and the observed path tail. The validated feature
    name (the segment at position `-3`) is used wherever the assembled
    prompt's close-call block derives `<feature>` from the
    `--linked-item` path (Inv 19), replacing any prior unvalidated
    slicing.

### HANDOFF schema

22. **Dual HANDOFF emission.** The assembled prompt instructs the
    subagent to emit two HANDOFF blocks at completion: a YAML-style
    `HANDOFF:` block (the human-readable view) followed immediately by
    a fenced JSON block prefixed `HANDOFF_JSON:` (the machine-first
    source of truth). The JSON block includes
    `handoff_schema_version: "1.0.0"` and the fields `feature`,
    `tdd_state`, `test_result`, `spec_compliance`, `tdd_report_path`,
    `closed_items`, `notes`.

### Bypass-marker preamble note

23. **Bypass-marker note emission.** When `.rabbit-human-approval-bypass`
    exists at the repo root, the assembled prompt's preamble (before
    STEP 1) contains the exact string returned by
    `rabbit_print(_BYPASS_NOTE_TEXT, "📢", "yellow")` (the canonical
    preamble body lives in `dispatch-tdd-subagent.py` as the module-level
    `_BYPASS_NOTE_TEXT` constant). When the marker is absent, no such
    note appears.

24. **Bypass-marker note channel.** `dispatch-tdd-subagent.py` emits the
    bypass preamble note solely by calling `rabbit_print` from
    `.claude/features/contract/scripts/rabbit_print.py`. The script
    contains no inline ANSI escape codes and no inline brand strings.

### `--human-approval-gate` branch

25. **`--human-approval-gate true` branch.** With
    `--human-approval-gate true` (default), the assembled prompt
    contains a STEP 2 HUMAN-APPROVAL section instructing the subagent
    to invoke `Skill("superpowers:writing-plans")`, present the
    implementation summary to the user, and wait for explicit approval
    before STEP 3 LOCK.

26. **`--human-approval-gate false` branch.** With
    `--human-approval-gate false`, the assembled prompt's STEP 2
    HUMAN-APPROVAL section is a one-line stub stating the step is
    skipped.

### Agent definition

27. **Single state-machine path in agent doc.** `agents/tdd-subagent.md`
    instructs the subagent to use the absolute `tdd-step.py` path
    supplied by the dispatched prompt. It does not describe a dual-path
    layout (agent-local OR feature-local).

### `feature.json` schema

28. **`feature.json` schema source.** The canonical `feature.json`
    schema lives at
    `.claude/features/contract/schemas/feature.json.schema.json`. This
    feature's `feature.json` conforms to that schema. Test fixtures in
    this feature use the same flat field shape (`name`, `version`,
    `owner`, `tdd_state`, `summary`, `surface`, `deprecation_criterion`).

29. **Meta-contract sections (Plan E.* migration).** `feature.json` MUST
    declare the meta-contract sections `manifest`, `runtime`, and
    `configuration`. The shapes are exactly:

    - `manifest` is a list of length 2 whose entries are, in order:
      1. `{"api": "publish_agent", "args": {"source":
         "agents/tdd-subagent.md"}}` — deploys the agent definition.
         `publish_agent` is a convenience wrapper that auto-derives the
         dest as `.claude/agents/<basename of source>`, yielding
         `.claude/agents/tdd-subagent.md`.
      2. `{"api": "publish_file", "args": {"source":
         "scripts/dispatch-tdd-subagent.py", "dest":
         ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py"}}`
         — deploys the dispatch script into the agent's adjacent scripts
         directory. `publish_file` requires explicit `dest` because the
         deployment path is NOT the `.claude/agents/<basename>` location
         that `publish_agent` would derive.
    - `runtime` is `{}` — tdd-subagent owns no Claude Code event hook
      handlers (consistent with `surface.hooks: []`).
    - `configuration` is `[]` — tdd-subagent exposes no
      user-configurable toggles.

    The manifest is the meta-contract source of truth for what
    tdd-subagent deploys. The `publish_file` entry uses `dest` to match
    the canonical `publish_file` shape.

## Out of Scope

- The TDD state machine itself (`tdd-step.py`, `tdd-context.py`,
  `tdd-drift-check.py`) — owned by `tdd-state-machine`.
- Deployment of the assembled scripts into `.claude/agents/` — owned by
  the `contract` feature.
- The `rabbit-feature-touch` orchestration skill and its SKILL.md
  content — owned by `rabbit-feature`.
- Validation of the `feature.json` schema (this feature relies on the
  schema; the contract feature owns and validates it).
- The confirm-token bypass authorization protocol (writing
  `.rabbit-scope-override` and `.rabbit-scope-active`) — implemented by
  the `rabbit-cage` scope-guard and documented in `rabbit-feature`'s
  SKILL.md.
