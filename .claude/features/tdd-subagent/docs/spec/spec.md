---
feature: tdd-subagent
version: 1.19.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When the TDD step model is replaced by a different lifecycle model; or when state tracking moves out of feature.json into a dedicated event log.
status: active
---

# tdd-subagent — Spec

## Purpose

Provides the `tdd-step.py` CLI for forward-only TDD state transitions, drift
detection, and enforcement gates at `test-green`. Provides the
`dispatch-tdd-subagent.py` prompt assembler and the `tdd-subagent` agent
definition that runs the 9-step TDD cycle for a single feature. The
`rabbit-feature-touch` orchestration skill that consumes these scripts is now
owned by the `rabbit-feature` feature (Cycle B of the re-home migration).

## Scripting Tech Stack

All scripts in this feature are Python 3. Bash is not used anywhere in this feature — not in runtime scripts, test harnesses, or fixtures. The sole test runner for each feature is `test/run.py`.

## Surface

- `.claude/features/tdd-subagent/scripts/tdd-step.py`
- `.claude/features/tdd-subagent/scripts/tdd-drift-check.py`
- `.claude/features/tdd-subagent/scripts/tdd-context.py`
- `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py` (assembles a per-feature full-TDD-cycle subagent prompt; the dispatched subagent runs spec-update → test-red → impl → test-green autonomously for ONE feature, using `.rabbit-scope-active-<feature>` as its scope marker so multiple features can be dispatched in parallel; accepts optional `--linked-item <item-dir>` and `--item-type <bug|backlog>` for a single primary item, AND an optional `--linked-items <feature>:<type>:<id>,...` for additional secondary items resolved by the same cycle — after the subagent reaches test-green the orchestrator captures the impl commit SHA and closes ALL linked items accordingly; prompt goes to stdout for caller dispatch)
- `.claude/features/tdd-subagent/agents/tdd-subagent.md` (the named subagent dispatched by `dispatch-tdd-subagent.py`)

## Invariants

1. `tdd_state` transitions are forward-only without `--force`.
2. `test-green` transition triggers enforcement checks.
3. All four scripts are executable.
4. `test-green` transition auto-closes any in-progress backlog items (stored on the `bug-backlog-files` branch per rabbit-file consolidation) via `python3 .claude/features/rabbit-file/scripts/item-status.py set --feature <feature> --type backlog --id <ID> --status close --reason 'auto-closed by tdd-step.py test-green' --fix-commits HEAD` (best-effort). The legacy `backlog-item-status.py` script no longer exists; tdd-step.py must use the unified `item-status.py` interface.
5. `tdd-step.py transition` output uses the named-wrapper API from
   `rabbit_print` (contract Inv 35, v1.12.0). The format is
   `[🐇 rabbit 🐇] 🔧 ━━━ FROM_STATE -> TO_STATE ━━━ 🔧` (green) for
   normal transitions, `[🐇 rabbit 🐇] 🔧 ━━━ FORCED: FROM_STATE -> TO_STATE ━━━ 🔧`
   (red) for forced transitions. State names render UPPERCASE because
   `tdd_transition()` / `tdd_forced()` upcase their `from_state` and
   `to_state` args internally — callers pass internal lowercase names
   directly. Concrete call shape:
     sys.stdout.write(rabbit_block(tdd_transition(cur, new)) + "\n")
     sys.stderr.write(rabbit_block(tdd_forced(cur, new)) + "\n")
   `rabbit_block` is the single source of the leading newline (contract
   Inv 36); manual `"\n" + ...` patterns are forbidden. Direct calls to
   `rabbit_print("tdd-transition", ...)` or `rabbit_print("tdd-forced", ...)`
   at call sites are forbidden — use the named wrappers. Enforcement
   WARNING messages (R3 check failed, naming check failed, etc.) use
   `rabbit_block(rabbit_subline(msg, color='red'))` for the brand
   prefix + red coloring without banner bars. The `show`, `next`, and
   `transitions` subcommands remain plain-text (consumed by tests and
   downstream parsers — they MUST NOT be styled). Direct ANSI escape
   codes (`\x1b[3...`), the literal `[rabbit]` or `[🐇 rabbit 🐇]` brand
   string, and the bar character (`━━━`) MUST NOT appear in `tdd-step.py`
   source outside of import statements or comments — consumer-side
   enforcement of contract Inv 36.
6. `dispatch-tdd-subagent.py` emits a prompt to stdout only; it does not call any agent itself. The assembled prompt instructs the per-feature subagent to run the full TDD cycle (spec-update → test-red → impl → test-green) for ONE feature, using `.rabbit-scope-active-<feature-name>` as its scope marker. Distinct per-feature scope markers enable simultaneous dispatch across features without scope collision. The subagent writes `tdd-report.json` to `.rabbit/tdd-report.json` (a hidden folder at repo root); the `.rabbit/` directory is created automatically if it doesn't exist and is listed in `.gitignore`.
7. When `--linked-item <item-dir> --item-type bug|backlog` is provided to `dispatch-tdd-subagent.py`, the orchestrator (after test-green) closes the linked item via the rabbit-file unified script: `python3 .claude/features/rabbit-file/scripts/item-status.py set --feature <feature> --type <type> --id <id> --status close --reason 'TDD cycle complete' --fix-commits <impl-sha>`. The `<feature>` and `<id>` are derived from the `--linked-item` path (e.g., `rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-8` → feature=`rabbit-cage`, id=`RABBIT-CAGE-BUG-8`). The legacy `bug-status.py` and `backlog-item-status.py` scripts no longer exist (consolidated into rabbit-file's `item-status.py` per RABBIT-FILE feature); any reference to them is a constitution violation. The HANDOFF block must include the linked item path and its new status. Additionally, when `--linked-items <feature>:<type>:<id>[,<feature>:<type>:<id>...]` is provided (a comma-separated list of triples), the orchestrator closes each listed item via the same `item-status.py set` invocation with `--reason 'TDD cycle complete (secondary item resolved by same commit)' --fix-commits <impl-sha>` after test-green. Each triple is validated for shape (exactly two colons, non-empty fields, type in {bug, backlog}); malformed triples cause dispatch-tdd-subagent.py to exit non-zero before emitting the prompt. The HANDOFF block must list all closed items (primary `--linked-item` plus every `--linked-items` entry).
8. `surface.skills` in `feature.json` MUST be `[]`. Skills are now managed via explicit copy-file entries in `build-contract.json`; the `surface.skills` field is retired and must remain an empty array.
9. E2E tests are always required — every behaviour described in a feature spec MUST
    have a corresponding end-to-end test. Unit tests alone are insufficient. The TDD
    subagent enforces this rule in the TEST-WRITE step without exception.
10. The 9 named steps (SPEC-READ, HUMAN-APPROVAL, LOCK, TEST-WRITE, TEST-RED,
    IMPLEMENT, CODE-REVIEW, TEST-GREEN, UNLOCK) are labelled sections in the assembled
    subagent prompt. tdd-step.py state transitions remain forward-only and unchanged.
11. dispatch-tdd-subagent.py interface: --scope (mandatory), --spec (mandatory),
    --impl-suggestion (optional), --linked-item / --item-type (B/B mode, primary item),
    --linked-items (optional, comma-separated `<feature>:<type>:<id>` triples for
    secondary items resolved by the same cycle), --human-approval-gate `true|false`
    (default `true`; `false` skips the subagent's HUMAN-APPROVAL step),
    --code-review-full-loop, --max-iterations (default 3, min 1). The legacy
    `--no-human-approval` flag is removed; all callers must use
    `--human-approval-gate false` instead. Boolean flag values follow the
    contract feature's CLI Naming Convention (Inv 15 of contract): exclusively
    `true` or `false`, never `enabled`/`disabled` or any other vocabulary.
12. After `rabbit-spec` returns in Step 3 of `rabbit-feature-touch` (owned by
    rabbit-feature), the dispatcher MUST commit any modifications to the
    feature's `docs/spec/spec.md` (and any other files in
    `.claude/features/<feature>/` that `rabbit-spec` edited) BEFORE proceeding
    to Step 5 (Dispatch TDD Subagents). The commit message follows the pattern
    `spec(<feature>): update spec for <one-line request summary>`. This
    prevents spec changes from falling through uncommitted and ensures the
    TDD subagent reads a clean committed baseline. If `rabbit-spec` made no
    changes (or only wrote the impl-suggestion artifact), the commit is
    skipped. The dispatcher-side commit obligation is documented here because
    `dispatch-tdd-subagent.py` reads the spec via the committed file and
    relies on this invariant.
13. In Step 9 (UNLOCK) of the per-feature TDD subagent prompt assembled by
    `dispatch-tdd-subagent.py`, the subagent MUST commit `feature.json`
    (which holds the final `tdd_state: test-green` transition written by
    `tdd-step.py`) BEFORE emitting the HANDOFF block. The commit message
    follows the pattern `chore(<feature>): advance tdd_state to test-green`.
    This prevents the state transition from falling through uncommitted and
    ensures the dispatcher does not need to commit `feature.json` manually
    after collecting HANDOFFs.
14. The TDD subagent for declared scope feature `F` MUST NOT create any
    `.rabbit-scope-active-<X>` marker where `X != F`. The only scope marker
    it may write is its own (`.rabbit-scope-active-<F>`) at LOCK. If
    implementation work requires a write to a file outside `F`'s directory
    (i.e., inside another feature's `.claude/features/<X>/` subtree), the
    subagent MUST STOP, set `tdd_state: blocked`, and emit a HANDOFF with:
    - `tdd_state: blocked`
    - `test_result: not_run`
    - `cross_feature_dependency: <X>` — the other feature
    - `unwritten_paths: [<path1>, <path2>, ...]` — the files the subagent
      could not write
    - `notes: <one sentence explaining the cross-feature dependency>`
    The dispatcher reads the HANDOFF and surfaces the cross-feature
    dependency to the user, who decides whether to split the work into a
    separate `rabbit-feature-touch` cycle for `<X>` or to abort. The
    subagent NEVER attempts to bypass scope-guard by writing an
    out-of-scope marker, even temporarily. This rule is non-negotiable; it
    closes a constitution violation observed in PR #107 where the subagent
    wrote `.rabbit-scope-active-contract` while scoped to rabbit-cage.
    `dispatch-tdd-subagent.py` MUST include this rule verbatim in the
    assembled prompt's Red Flags section.
15. The dispatcher-side Step 4 check for `.rabbit-human-approval-bypass` MUST
    be documented in `rabbit-feature-touch` SKILL.md (owned by rabbit-feature)
    as the first action of Step 4 (Human Approval), BEFORE any in-conversation
    wait or impl-suggestion surfacing. When the marker is found, the warning
    emitted to the user MUST name the marker path
    (`.rabbit-human-approval-bypass`) and the revoke command
    (`/rabbit-config human-approval true`) so the user can audit and revoke
    without searching. (Cross-feature: behaviour owned by
    rabbit-feature Inv 8; this invariant constrains the SKILL.md
    documentation requirement.)
16. The assembled TDD subagent prompt (produced by `dispatch-tdd-subagent.py`)
    MUST include a rule in its IMPLEMENT step: if the implementation requires
    editing any file whose basename is `SKILL.md`, the subagent MUST invoke
    `Skill("skill-creator:skill-creator")` instead of using Write or Edit
    directly. Direct edits to SKILL.md bypass skill-creator's eval loop and
    description optimization. This rule is non-negotiable; a subagent that
    writes a SKILL.md without going through skill-creator commits a
    constitution violation.
17. `rabbit-feature-touch` SKILL.md (owned by rabbit-feature) Red Flags
    section MUST include the rule: the main session orchestrator MUST NOT use
    Write or Edit tools on any file under `.claude/features/`. All
    feature-code edits are the TDD subagent's job, performed under an active
    scope marker. The main session role is orchestration only — resolve
    scope, create branch, invoke rabbit-spec, surface impl-suggestion,
    dispatch subagent, verify HANDOFF. Exceptions exist for explicit
    confirm-token overrides (see Confirm-Token Bypass Path) and for spec.md
    writes under the scope-guard path-pattern allowlist (Inv 20 of
    rabbit-cage) which are invoked by rabbit-spec during Step 3.
    (Cross-feature: SKILL.md content owned by rabbit-feature; this
    invariant constrains tdd-subagent's expectation of the consumer.)
18. `rabbit-feature-touch` SKILL.md (owned by rabbit-feature) Red Flags
    section MUST include the rule: the main session MUST NOT create
    `.rabbit-scope-active` (global) or `.rabbit-scope-active-<feature>`
    (per-feature) scope markers at the repo root. Scope markers are
    exclusively the TDD subagent's responsibility, written as the first
    action at LOCK (Step 3 of the subagent's named steps). Main-session-
    authored markers bypass scope-guard's intended boundary and have caused
    constitution violations (PR #93). This rule is distinct from Inv 14
    (which prohibits the SUBAGENT from creating out-of-scope markers):
    this invariant prohibits the MAIN SESSION from creating any marker at
    all. (Cross-feature: SKILL.md content owned by rabbit-feature.)
19. The assembled TDD subagent prompt's STEP 3 LOCK section MUST NOT use
    `trap '... rm -f ...' EXIT` to clean up the scope marker. Each Claude
    Code `Bash` tool invocation runs in a separate shell process; the trap
    fires immediately when that shell exits, deleting the marker before
    subsequent steps run. Cleanup MUST be explicit: STEP 9 UNLOCK
    executes `rm -f /<repo_root>/.rabbit-scope-active-<feature>` as one of
    its commands, after the chore commit and before HANDOFF. LOCK does only
    `touch /<repo_root>/.rabbit-scope-active-<feature>` and nothing else.
20. The assembled prompt's STEP 7 CODE-REVIEW MUST invoke
    `Skill("superpowers:requesting-code-review")`, not
    `Skill("superpowers:code-reviewer")`. The latter does not exist; using
    it silently no-ops the review step. The skill name is exact and
    case-sensitive.
21. The assembled prompt's STEP 6 IMPLEMENT loop MUST include an explicit
    commit of the implementation files after the test suite passes within an
    iteration: `git add <feature_dir>/` followed by
    `git commit -m "fix/feat(<feature>): <one-line summary>"` (verb chosen
    by the subagent based on whether this is a bugfix or new feature). The
    commit MUST happen INSIDE the iteration loop, BEFORE the `tdd-step.py
    transition <feature_dir> impl` call, so that the impl SHA captured by
    `git rev-parse HEAD` after the impl transition points at the actual
    implementation commit (not at the prior test commit from STEP 4).
22. The assembled prompt's STEP 8 TEST-GREEN MUST capture `git rev-parse
    HEAD` and substitute it into the `impl_commit` field of
    `tdd-report-<feature>.json` BEFORE STEP 9 UNLOCK runs its `chore(...)`
    commit. The chore commit advances HEAD past the implementation; if
    `impl_commit` is captured lazily (after the chore commit), it points at
    the chore commit, not the implementation. The prompt MUST make the
    capture order explicit and the tdd-report MUST be fully written before
    the UNLOCK chore commit begins.
23. The assembled prompt's STEP 1 SPEC-READ MUST diff the spec against the
    PARENT commit, not against HEAD. Use `git diff HEAD~1 -- <feature_dir>/docs/spec/`
    (or equivalent ref to the pre-spec-commit state). `git diff HEAD` shows
    only uncommitted changes; since `rabbit-feature-touch` Step 3 commits
    the spec change BEFORE dispatching the subagent (Inv 12), the working
    tree is clean at subagent start and `git diff HEAD` is always empty.
    Using `HEAD~1` ensures the subagent actually sees the spec delta it is
    expected to implement.
24. `tdd-context.py` MUST read `deprecation_criterion` (flat key) from
    `feature.json`, not `deprecation.criterion` (nested). The canonical
    schema across all rabbit features is the flat form; the nested form is
    legacy. For backward compatibility, read flat first; fall back to
    `deprecation.criterion` only if the flat key is absent. Tests MUST use
    the flat form in fixtures (the legacy nested form should appear only in
    explicit backward-compatibility tests).
25. `tdd-context.py` guidance text MUST reference `test/run.py` (the actual
    Python test runner) when describing how to verify tests pass at the
    `impl` state. References to `test/run.sh` are stale (no `.sh` files
    exist in any feature per the Python-only stack invariants in contract
    and rabbit-cage).
26. `rabbit-feature-touch` SKILL.md (owned by rabbit-feature) B/B mode MUST
    read the item JSON from `<item-dir>/item.json`, never from
    `<item-dir>/bug.json`. The rabbit-file schema uses `item.json` for both
    bug and backlog types (unified storage); `bug.json` is a legacy path
    that no longer exists. The B/B mode `related_feature` extraction MUST
    use Python 3 (always available; `jq` is not a declared dependency of
    this feature): `FEATURE=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('related_feature',''))" <item-dir>/item.json)`.
    (Cross-feature: SKILL.md content owned by rabbit-feature; this invariant
    constrains tdd-subagent's data contract with the B/B caller.)
27. The `tdd-step.py` state machine MUST permit cycle restart from
    `test-green` by adding the forward transition `test-green → spec-update`
    to its TRANSITIONS table. The current chain
    `spec → spec-update → test-red → impl → test-green → deprecated → ""`
    leaves `test-green` with only one forward transition (to `deprecated`,
    which is terminal). This is incompatible with the rabbit-feature-touch
    workflow, which runs multiple TDD cycles for the same feature across
    different bugs/backlogs; each cycle must be able to start fresh from
    a prior `test-green` state. The amended chain MUST allow
    `test-green → spec-update` (next cycle restart) AND
    `test-green → deprecated` (feature retirement) as the two valid
    forward transitions from `test-green`. The assembled TDD subagent
    prompt's STEP 5 (TEST-RED) MUST include an explicit transition
    `tdd-step.py transition <feature_dir> spec-update` BEFORE the
    `test-red` transition when the starting state is `test-green`;
    running it unconditionally also works because `spec-update →
    spec-update` is a self-no-op (or use `tdd-step.py show` to check
    first).
28. When `dispatch-tdd-subagent.py` runs and the file
    `.rabbit-human-approval-bypass` exists at the repo root, the assembled
    prompt MUST include a distinct yellow-coloured `[rabbit]` note
    (`\x1b[33m`, distinct from sync-check's red bypass alert) in the
    prompt preamble. The note MUST name both the marker path
    (`.rabbit-human-approval-bypass`) and the revoke skill invocation
    (`/rabbit-config human-approval true`) so the dispatched subagent
    (and any reviewer of the prompt) sees that the approval gate is
    currently disabled. The note is emitted EVERY dispatch while the
    marker exists; it does not consume or delete the marker. When the
    marker is absent, no such note appears (baseline prompt is
    unchanged). (BACKLOG-4)
29. `feature.json` for every rabbit feature conforms to the schema at
    `.claude/features/contract/schemas/feature.json.schema.json`, which
    is the canonical declaration. The fields the tdd-subagent feature
    relies on are: `name` (string), `version` (semver string),
    `owner` (string), `tdd_state` (string — the tdd-subagent state
    machine permits `spec`, `spec-update`, `test-red`, `impl`,
    `test-green`, `deprecated`), `summary` (string), `surface`
    (object), and the flat `deprecation_criterion` (string). Test
    fixtures in this feature MUST use this flat shape; the legacy
    nested form (`owner` as object, `deprecation.criterion` as nested
    object, top-level `contract` / `status` / `created`) is retired
    except where an explicit backward-compatibility test exercises it.
    The contract feature owns the schema file; if the `tdd_state` enum
    in the schema diverges from the tdd-subagent state machine, the
    fix lives in the contract feature (filed via a follow-up backlog
    in `rabbit/features/contract/backlogs/`) and is not in scope for
    tdd-subagent. (BACKLOG-6)
30. Shared test fixture helpers live at
    `.claude/features/tdd-subagent/test/test_helpers.py`. The module
    exposes at least `make_feature_dir(parent_dir, name, tdd_state,
    *, run_exit=0)` which writes a flat-schema feature.json (per Inv 29)
    plus the minimal `test/run.py`, `spec.md`, and `contract.md`
    siblings the tdd-subagent scripts expect. `test-tdd-step.py`,
    `test-context.py`, and `test-drift-check.py` MUST import this
    helper instead of redefining their own `fix(...)` function so the
    canonical fixture shape lives in one place. (BACKLOG-10)
31. The assembled TDD subagent prompt MUST include a structured JSON
    HANDOFF schema at the top of its HANDOFF block. The schema is
    declared inline in the prompt with `handoff_schema_version: "1.0.0"`
    and lists the required fields (`feature`, `tdd_state`, `test_result`,
    `spec_compliance`, `tdd_report_path`, `closed_items` (array),
    `notes`). The subagent emits BOTH the legacy YAML-like HANDOFF
    block (for human readability and backward-compatible dispatchers)
    AND a fenced JSON HANDOFF block immediately after, prefixed
    `HANDOFF_JSON:` so downstream parsers can locate and validate it
    without ambiguity. The JSON HANDOFF is the machine-first source
    of truth per philosophy.md. (BACKLOG-7)
32. `agents/tdd-subagent.md` MUST NOT describe a dual-path layout for
    `scripts/tdd-step.py` (i.e., no "agent-local OR
    .claude/features/tdd-subagent/scripts" fork). The dispatched
    prompt always provides the absolute feature-scripts path; the
    agent must use exactly that path. The agent file may name the
    canonical scripts directory (`.claude/features/tdd-subagent/scripts/`)
    once for reference, but MUST NOT instruct the subagent to choose
    between two paths. (BACKLOG-9)

## Contract Schema References

The canonical `feature.json` schema is
`.claude/features/contract/schemas/feature.json.schema.json` (owned by
the contract feature). The tdd-subagent feature reads only the fields
listed in Inv 29; it does not own the schema and changes to it follow
the contract feature's versioning policy.

The HANDOFF JSON schema (Inv 31) is declared inline in the assembled
prompt because the dispatcher is the only consumer; if a third
consumer appears, the schema MUST be promoted to a file under
`.claude/features/contract/schemas/`.

## Confirm-Token Bypass Path

The full TDD cycle may be bypassed for a single edit when the main session obtains explicit in-conversation user approval via a confirm token. This path does NOT skip user authorization — the user's in-conversation approval IS the authorization.

**Protocol:**

1. Main session presents a confirm token to the user, offering two choices:
   - `one-time` — bypass applies to the next single edit only; the override file is consumed and deleted after one use.
   - `session` — bypass applies for the remainder of the current session until manually removed.
2. User selects a choice in-conversation.
3. Main session writes `.rabbit-scope-override` at the repo root containing either `one-time` or `session` (no other content).
4. Main session writes `.rabbit-scope-active` containing the feature name.
5. Main session makes the edit directly (no TDD cycle, no subagent dispatch).
6. Scope-guard reads `.rabbit-scope-override` and allows the write; for `one-time` mode it deletes `.rabbit-scope-override` and creates `.rabbit-scope-override-used` as an audit trace.

**Constraints:**

- The override file MUST be written by the main session after receiving user approval; it MUST NOT be written speculatively or pre-emptively.
- The confirm token MUST be presented as a visible, explicit choice — never as an implicit default.
- The `SKILL.md` for `rabbit-feature-touch` (owned by rabbit-feature) documents this path under "Override Path — Bypassing TDD with User Approval".
- Audit: `.rabbit-scope-override-used` (created by scope-guard after one-time consumption) serves as the post-hoc audit trace.

## Out of Scope

- Validating the schema of `feature.json` beyond the `tdd_state` field.
- Enforcing branch or PR rules around state transitions.
- Writing `feature.json` in locked-down environments — callers use `breeder` for that.
- The `rabbit-feature-touch` orchestration skill itself — owned by `rabbit-feature` (post-Cycle B re-home).
