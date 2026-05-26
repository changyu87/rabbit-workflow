---
feature: tdd-subagent
version: 5.0.0
owner: rabbit-workflow team
template_version: 2.1.0
deprecation_criterion: When subagent dispatch is replaced by a different orchestration mechanism (e.g., direct rabbit-CLI orchestration without a dispatch-prompt assembler).
status: active
---

# tdd-subagent — Spec

## Purpose

Provides `dispatch-tdd-subagent.py` (a prompt assembler), `tdd-step.py`
(the forward-only TDD state machine), and the `tdd-subagent` agent
definition. The assembled prompt drives a single feature through the
7-step TDD cycle (LOCK → TEST-WRITE → TEST-RED → IMPLEMENT →
CODE-REVIEW → TEST-GREEN → UNLOCK), invoking `tdd-step.py` at each
state transition. Spec context-loading and the human-approval gate are
the dispatcher's responsibility, not the subagent's.

The `rabbit-feature-touch` orchestration skill that consumes this
feature's dispatch prompt is owned by `rabbit-feature`. The retired
`tdd-state-machine` feature was absorbed into this one at v4.0.0; its
14 invariants now appear below renumbered as Inv 31–44.

## Scripting Tech Stack

All scripts in this feature are Python 3 standard library. Bash is not
used in runtime scripts, test harnesses, or fixtures. The sole test
runner is `test/run.py`.

## Surface

- `scripts/dispatch-tdd-subagent.py` — assembles a per-feature TDD-cycle
  prompt to stdout; the script itself does not invoke any agent.
- `scripts/tdd-step.py` — the forward-only TDD state machine
  (`show | next | transitions | transition`); invoked by the assembled
  prompt at each state transition (and directly by any other caller that
  needs to advance a feature's `tdd_state`).
- `agents/tdd-subagent.md` — the agent definition dispatched by callers
  using the assembled prompt.

## Pre-Conditions

Callers MUST commit the spec file referenced by `--spec` BEFORE
invocation; the dispatcher's spec-authoring step must produce a clean
committed baseline so the embedded `{spec_content}` interpolation in
the assembled prompt reflects the post-edit state. Codification of the
upstream commit obligation lives in the caller's spec
(`rabbit-feature`).

## Invariants

**Note on the prompt-contract migration.** As of the CONTRACT-BACKLOG-1
Phase B cycle, `dispatch-tdd-subagent.py` no longer assembles its
output via an inline Python f-string. Instead it builds a slot dict and
delegates assembly to `.claude/features/contract/scripts/build-prompt.py`,
which substitutes against the template at
`.claude/features/contract/templates/prompts/tdd-subagent.txt` (landed
by contract Inv 57) and prepends the policy block from the entry's
`inject` list. Every invariant below whose constraint applies to the
content of the dispatched prompt (Inv 7–22, plus the assembled output
referenced by Inv 23/24) MUST be read as constraining the template
file's content rather than any inline f-string in the dispatch script.
Invariants 23 and 24 retain their script-level constraint on how the
`bypass_preamble_note` slot value is COMPUTED (via `rabbit_print`),
but where that value APPEARS in the dispatched output is governed by
the template's `{{bypass_preamble_note}}` placeholder.

### Surface scope

1. **Owned surface.** This feature owns exactly three surface entries:
   `scripts/dispatch-tdd-subagent.py`, `scripts/tdd-step.py`, and
   `agents/tdd-subagent.md`. The state-machine script `tdd-step.py`
   lives at `.claude/features/tdd-subagent/scripts/tdd-step.py`
   (absorbed from the retired `tdd-state-machine` feature at v4.0.0).
   The `.claude/features/tdd-state-machine/` directory MUST NOT exist.

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
   `--code-review-full-loop` (boolean flag),
   `--max-iterations N` (default `3`, minimum `1`).

5. *(Retired — see CHANGELOG.md.)*

6. **`--linked-items` validation.** Each comma-separated entry MUST have
   exactly two colons separating non-empty `<feature>`, `<type>`, `<id>`
   fields, with `<type>` ∈ {`bug`, `backlog`}. Any malformed entry causes
   exit `2` with a diagnostic on stderr BEFORE any stdout is emitted.

### Dispatch script — prompt content

7. **Scope marker convention.** The assembled prompt instructs the
   subagent to use `.rabbit-scope-active-<feature-name>` as its sole
   scope marker, written at LOCK and removed at UNLOCK. Distinct
   per-feature markers permit simultaneous dispatch across features.

8. **7-step section banners.** The assembled prompt contains a labelled
   section per step using the names `LOCK`, `TEST-WRITE`, `TEST-RED`,
   `IMPLEMENT`, `CODE-REVIEW`, `TEST-GREEN`, `UNLOCK`, in that order,
   numbered STEP 1 through STEP 7. Spec context-loading and human
   approval are owned by the dispatcher (`rabbit-feature-touch`) and
   absent from the assembled prompt.

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

13. *(Retired — see CHANGELOG.md.)*

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

### `--human-approval-gate` branch (retired)

25. *(Retired — see CHANGELOG.md.)*

26. *(Retired — see CHANGELOG.md.)*

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

29. **Meta-contract sections.** `feature.json` MUST
    declare the meta-contract sections `manifest`, `runtime`, and
    `configuration`. The shapes are exactly:

    - `manifest` is a list of length 3 whose entries are, in order:
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
      3. `{"api": "publish_file", "args": {"source":
         "scripts/tdd-step.py", "dest":
         ".claude/agents/tdd-subagent/scripts/tdd-step.py"}}` — deploys
         the state-machine script into the agent's adjacent scripts
         directory so the dispatched subagent can invoke `tdd-step.py`
         from a colocated path. (Pre-v4.0.0 this entry lived on
         `tdd-state-machine`'s manifest as a cross-feature publish_file;
         post-absorption the source path is intra-feature.)
    - `runtime` is `{}` — tdd-subagent owns no Claude Code event hook
      handlers (consistent with `surface.hooks: []`).
    - `configuration` is `[]` — tdd-subagent exposes no
      user-configurable toggles.

    The manifest is the meta-contract source of truth for what
    tdd-subagent deploys. The `publish_file` entries use `dest` to match
    the canonical `publish_file` shape.

### State machine — schema/behaviour

The 14 invariants in this section were absorbed from the retired
`tdd-state-machine` feature at v4.0.0. They constrain
`scripts/tdd-step.py`.

31. **Valid state set.** The valid `tdd_state` values are exactly:
    `spec`, `spec-update`, `test-red`, `impl`, `test-green`,
    `deprecated`. `transition` rejects any other target value with exit
    `1`.

32. **Primary forward order.** The primary forward order is:
    `spec -> spec-update -> test-red -> impl -> test-green ->
    deprecated`. Without `--force`, a transition is accepted only when
    the new state is the primary forward target of the current state
    (or the alternate target defined in Inv 33).

33. **Alternate forward edge.** From `test-green`, the alternate forward
    target `spec-update` is accepted without `--force`. This is the only
    alternate forward edge in the state machine and lets a feature start
    a fresh cycle without going through `deprecated`.

34. **Backward transitions require `--force`.** Any transition that is
    not a forward edge (per Inv 32 or Inv 33) is rejected with exit `1`
    unless `--force` is supplied. With `--force`, a transition between
    any two non-terminal states is accepted.

35. **`deprecated` is terminal.** From `deprecated`, every transition is
    rejected with exit `1`, including when `--force` is supplied.

36. **`tdd-step.py` location.** `scripts/tdd-step.py` MUST be present at
    `.claude/features/tdd-subagent/scripts/tdd-step.py`. The retired
    `.claude/features/tdd-state-machine/` directory MUST NOT exist.

37. **Executable bit.** `scripts/tdd-step.py` is stored with the
    user-executable bit set (any mode satisfying `mode & 0o100`; in
    practice `0o755` or `0o775` depending on the contributor's umask).

38. **`spec-update -> test-red` precondition.** The transition
    `spec-update -> test-red` is accepted only when at least one of the
    following holds:

    - `git diff HEAD` under `<feature-dir>/docs/spec/` is non-empty, OR
    - `--spec-no-change-reason <reason>` is supplied with a non-empty
      reason; the reason is persisted on `feature.json` as
      `spec_no_change_reason`.

    When neither holds, the transition is denied with exit `1`.

39. **Branding render via `rabbit_print`.** `tdd-step.py` MUST render
    every transition message through the centralised `rabbit_print`
    module loaded from `.claude/features/contract/scripts/rabbit_print.py`.
    Accepted transitions emit
    `rabbit_print("{CUR} -> {NEW}", "🔧", "green")` on stdout (ANSI
    green, `[🐇 rabbit 🐇]` brand). Forced transitions additionally
    emit `rabbit_print("FORCED: {CUR} -> {NEW}", "🔧", "red")` on
    stderr (ANSI red). State names are uppercased at the call site.

40. **`test-green` enforcement-check hook.** After a successful
    transition into `test-green`, `tdd-step.py` calls each of the
    following functions from `contract.lib.checks` in-process:

    - `check_tests_non_interactive`
    - `check_sentinel`
    - `check_naming`
    - `check_imports_resolve`
    - `check_symlinks_resolve`
    - `check_template_producer_consistency`

    A non-passed `CheckResult` from any of these emits a non-empty
    warning via `rabbit_print` on stderr. The hook is best-effort and
    never blocks the transition.

41. **`test-green` project-consolidate hook.** After a successful
    transition into `test-green`, when `project-map.json` exists in the
    enclosing project directory (the parent of `<feature-dir>`'s
    parent), `tdd-step.py` invokes `rabbit-project.py consolidate
    <project-name>`. The hook is best-effort: any failure (missing
    script, broken project layout) is swallowed and never blocks the
    transition.

42. **`spec-update -> test-red` numbered-list check.** After a
    successful transition `spec-update -> test-red`, `tdd-step.py`
    calls `contract.lib.checks.check_numbered_lists` against
    `<feature-dir>/docs/spec/`. A non-passed `CheckResult` emits a
    warning via `rabbit_print` on stderr but does NOT block the
    transition. The Inv 38 gate remains the only blocking precondition
    for this transition.

43. **In-process library imports (no subprocess to CLI shims).** The
    check functions used by Inv 40 and Inv 42 are imported from the
    `contract.lib.checks` library module at
    `.claude/features/contract/lib/checks.py` and invoked in-process.
    `tdd-step.py` MUST NOT fan out via `subprocess` to the
    `.claude/features/contract/scripts/enforcement/check-*.py` CLI
    shims for any of these checks.

44. **`tdd-step.py` manifest entry.** `feature.json`'s `manifest` (per
    Inv 29) contains the third entry that publishes `tdd-step.py` to
    the agent's adjacent scripts directory. The intra-feature source
    path (`scripts/tdd-step.py`) and the agent-adjacent dest
    (`.claude/agents/tdd-subagent/scripts/tdd-step.py`) together
    declare the deployment of this script.

45. **`feature.json` `prompts` section + dispatcher uses `build-prompt.py`.**
    `feature.json` MUST declare a `prompts` array containing EXACTLY ONE
    entry with these field values:
    - `id: "tdd-subagent"`
    - `kind: "subagent"`
    - `inject: [".claude/features/policy/philosophy.md", ".claude/features/policy/spec-rules.md", ".claude/features/policy/coding-rules.md"]`
    - `slots: ["feature_name", "spec_content", "impl_suggestion_block", "bypass_preamble_note", "feature_dir", "tdd_step_py", "repo_root", "max_iterations", "code_review_loop_note", "linked_item_value", "item_type_value", "close_calls_block", "handoff_closed_items_block", "handoff_closed_items_json"]`

    The matching template at
    `.claude/features/contract/templates/prompts/tdd-subagent.txt`
    (landed by contract Inv 57) supplies the body. `scripts/dispatch-tdd-subagent.py`
    MUST NOT assemble the prompt inline via Python f-string — it MUST
    instead build a dict mapping each declared slot name to its
    computed value, invoke
    `python3 .claude/features/contract/scripts/build-prompt.py
    --callable-id tdd-subagent --slot <name>=<value>` (one `--slot`
    per slot) via subprocess, read the resulting prompt file from the
    path printed to stdout by the assembler, and write that file's
    contents to its own stdout. The dispatcher's existing CLI shape
    (`--scope`, `--spec`, `--impl-suggestion`, `--linked-item`,
    `--item-type`, `--linked-items`, `--code-review-full-loop`,
    `--max-iterations`) and existing argument validation (every check
    up through the parsing of `secondary_items` and the close-call
    block construction) MUST remain unchanged. The previous
    `_policy_block` helper function and its call site (which
    subprocessed to `policy-block.py`) MUST be removed — the policy
    block is now prepended by `build-prompt.py` from the entry's
    `inject` list per contract Inv 54. Enforced by
    `test/test-dispatch-uses-build-prompt.py`; the existing 23
    prompt-content tests (test-prompt-structure.py,
    test-prompt-lock-unlock.py, test-prompt-scope-boundary.py,
    test-prompt-implement-rules.py, test-prompt-commit-order.py,
    test-prompt-code-review.py, test-bypass-marker-note.py, etc.) act
    as the regression net confirming the dispatched output is
    byte-equivalent to the prior f-string assembly.

## Out of Scope

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
