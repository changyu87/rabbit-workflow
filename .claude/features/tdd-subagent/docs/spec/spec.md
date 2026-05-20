---
feature: tdd-subagent
version: 2.1.0
owner: rabbit-workflow team
template_version: 2.1.0
deprecation_criterion: When subagent dispatch is replaced by a different orchestration mechanism (e.g., direct rabbit-CLI orchestration without a dispatch-prompt assembler).
status: active
---

# tdd-subagent — Spec

## Purpose

Provides the `dispatch-tdd-subagent.py` prompt assembler and the
`tdd-subagent` agent definition that runs the 9-step TDD cycle for a
single feature.

The TDD state machine itself (`tdd-step.py`, `tdd-context.py`,
`tdd-drift-check.py`) is owned by the `tdd-state-machine` feature; this
feature READS those scripts at runtime (cross-feature dependency,
declared in `contract.md`). The `rabbit-feature-touch` orchestration
skill that consumes this feature's dispatch prompt is owned by the
`rabbit-feature` feature.

## Scripting Tech Stack

All scripts in this feature are Python 3. Bash is not used anywhere in
this feature — not in runtime scripts, test harnesses, or fixtures. The
sole test runner is `test/run.py`.

## Surface

- `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py` —
  assembles a per-feature full-TDD-cycle subagent prompt; the dispatched
  subagent runs spec-update → test-red → impl → test-green autonomously
  for ONE feature, using `.rabbit-scope-active-<feature>` as its scope
  marker so multiple features can be dispatched in parallel; accepts
  optional `--linked-item <item-dir>` and `--item-type <bug|backlog>` for
  a single primary item, AND an optional
  `--linked-items <feature>:<type>:<id>,...` for additional secondary
  items resolved by the same cycle — after the subagent reaches
  test-green the orchestrator captures the impl commit SHA and closes
  ALL linked items accordingly; prompt goes to stdout for caller
  dispatch.
- `.claude/features/tdd-subagent/agents/tdd-subagent.md` — the named
  subagent dispatched by `dispatch-tdd-subagent.py`.

## Invariants

1. **Surface scope (post-extraction).** This feature owns exactly two
   surface entries: `scripts/dispatch-tdd-subagent.py` and
   `agents/tdd-subagent.md`. The forward-only TDD state machine
   (`tdd-step.py`, `tdd-context.py`, `tdd-drift-check.py`) was extracted
   to the `tdd-state-machine` feature and MUST NOT reappear under
   `.claude/features/tdd-subagent/scripts/`. Any reference inside this
   feature's own scripts to a state-machine script path MUST resolve
   under the `tdd-state-machine` feature's scripts directory.
2. `dispatch-tdd-subagent.py` emits a prompt to stdout only; it does not
   call any agent itself. The assembled prompt instructs the per-feature
   subagent to run the full TDD cycle
   (spec-update → test-red → impl → test-green) for ONE feature, using
   `.rabbit-scope-active-<feature-name>` as its scope marker. Distinct
   per-feature scope markers enable simultaneous dispatch across
   features without scope collision. The subagent writes
   `tdd-report.json` to `.rabbit/tdd-report.json` (a hidden folder at
   repo root); the `.rabbit/` directory is created automatically if it
   doesn't exist and is listed in `.gitignore`.
3. When `--linked-item <item-dir> --item-type bug|backlog` is provided to
   `dispatch-tdd-subagent.py`, the orchestrator (after test-green) closes
   the linked item via the rabbit-file unified script:
   `python3 .claude/features/rabbit-file/scripts/item-status.py set --feature <feature> --type <type> --id <id> --status close --reason 'TDD cycle complete' --fix-commits <impl-sha>`.
   The `<feature>` and `<id>` are derived from the `--linked-item` path
   (e.g., `rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-8` →
   feature=`rabbit-cage`, id=`RABBIT-CAGE-BUG-8`). The legacy
   `bug-status.py` and `backlog-item-status.py` scripts no longer exist
   (consolidated into rabbit-file's `item-status.py`); any reference to
   them is a constitution violation. The HANDOFF block must include the
   linked item path and its new status. Additionally, when
   `--linked-items <feature>:<type>:<id>[,<feature>:<type>:<id>...]` is
   provided (a comma-separated list of triples), the orchestrator closes
   each listed item via the same `item-status.py set` invocation with
   `--reason 'TDD cycle complete (secondary item resolved by same commit)' --fix-commits <impl-sha>`
   after test-green. Each triple is validated for shape (exactly two
   colons, non-empty fields, type in {bug, backlog}); malformed triples
   cause dispatch-tdd-subagent.py to exit non-zero before emitting the
   prompt. The HANDOFF block must list all closed items (primary
   `--linked-item` plus every `--linked-items` entry).
4. `surface.skills` in `feature.json` MUST be `[]`. Skills are managed
   via explicit copy-file entries in `build-contract.json`; the
   `surface.skills` field is retired and must remain an empty array.
5. E2E tests are always required — every behaviour described in a
   feature spec MUST have a corresponding end-to-end test. Unit tests
   alone are insufficient. The TDD subagent enforces this rule in the
   TEST-WRITE step without exception.
6. The 9 named steps (SPEC-READ, HUMAN-APPROVAL, LOCK, TEST-WRITE,
   TEST-RED, IMPLEMENT, CODE-REVIEW, TEST-GREEN, UNLOCK) are labelled
   sections in the assembled subagent prompt. The underlying tdd-step.py
   state transitions (owned by tdd-state-machine) remain forward-only
   and unchanged.
7. `dispatch-tdd-subagent.py` interface: `--scope` (mandatory), `--spec`
   (mandatory), `--impl-suggestion` (optional),
   `--linked-item` / `--item-type` (B/B mode, primary item),
   `--linked-items` (optional, comma-separated `<feature>:<type>:<id>`
   triples for secondary items resolved by the same cycle),
   `--human-approval-gate true|false` (default `true`; `false` skips the
   subagent's HUMAN-APPROVAL step), `--code-review-full-loop`,
   `--max-iterations` (default 3, min 1). The legacy
   `--no-human-approval` flag is removed; all callers must use
   `--human-approval-gate false` instead. Boolean flag values follow the
   contract feature's CLI Naming Convention: exclusively `true` or
   `false`, never `enabled`/`disabled` or any other vocabulary.
8. After `rabbit-feature-spec` returns in Step 3 of `rabbit-feature-touch`
   (owned by rabbit-feature), the dispatcher MUST commit any
   modifications to the feature's `docs/spec/spec.md` (and any other
   files in `.claude/features/<feature>/` that `rabbit-feature-spec` edited)
   BEFORE proceeding to Step 5 (Dispatch TDD Subagents). The commit
   message follows the pattern
   `spec(<feature>): update spec for <one-line request summary>`. This
   prevents spec changes from falling through uncommitted and ensures
   the TDD subagent reads a clean committed baseline. If `rabbit-feature-spec`
   made no changes (or only wrote the impl-suggestion artifact), the
   commit is skipped. The dispatcher-side commit obligation is
   documented here because `dispatch-tdd-subagent.py` reads the spec via
   the committed file and relies on this invariant.
9. In Step 9 (UNLOCK) of the per-feature TDD subagent prompt assembled
   by `dispatch-tdd-subagent.py`, the subagent MUST commit
   `feature.json` (which holds the final `tdd_state: test-green`
   transition written by the tdd-state-machine `tdd-step.py`) BEFORE
   emitting the HANDOFF block. The commit message follows the pattern
   `chore(<feature>): advance tdd_state to test-green`. This prevents
   the state transition from falling through uncommitted and ensures
   the dispatcher does not need to commit `feature.json` manually after
   collecting HANDOFFs.
10. The TDD subagent for declared scope feature `F` MUST NOT create any
    `.rabbit-scope-active-<X>` marker where `X != F`. The only scope
    marker it may write is its own (`.rabbit-scope-active-<F>`) at LOCK.
    If implementation work requires a write to a file outside `F`'s
    directory (i.e., inside another feature's `.claude/features/<X>/`
    subtree), the subagent MUST STOP, set `tdd_state: blocked`, and emit
    a HANDOFF with:
    - `tdd_state: blocked`
    - `test_result: not_run`
    - `cross_feature_dependency: <X>` — the other feature
    - `unwritten_paths: [<path1>, <path2>, ...]` — the files the
      subagent could not write
    - `notes: <one sentence explaining the cross-feature dependency>`

    The dispatcher reads the HANDOFF and surfaces the cross-feature
    dependency to the user, who decides whether to split the work into a
    separate `rabbit-feature-touch` cycle for `<X>` or to abort. The
    subagent NEVER attempts to bypass scope-guard by writing an
    out-of-scope marker, even temporarily.
    `dispatch-tdd-subagent.py` MUST include this rule verbatim in the
    assembled prompt's Red Flags section.
11. The assembled TDD subagent prompt (produced by
    `dispatch-tdd-subagent.py`) MUST include a rule in its IMPLEMENT
    step: if the implementation requires editing any file whose
    basename is `SKILL.md`, the subagent MUST invoke
    `Skill("skill-creator:skill-creator")` instead of using Write or
    Edit directly. Direct edits to SKILL.md bypass skill-creator's eval
    loop and description optimization. This rule is non-negotiable; a
    subagent that writes a SKILL.md without going through skill-creator
    commits a constitution violation.
12. The assembled TDD subagent prompt's STEP 3 LOCK section MUST NOT use
    `trap '... rm -f ...' EXIT` to clean up the scope marker. Each
    Claude Code `Bash` tool invocation runs in a separate shell process;
    the trap fires immediately when that shell exits, deleting the
    marker before subsequent steps run. Cleanup MUST be explicit: STEP 9
    UNLOCK executes
    `rm -f /<repo_root>/.rabbit-scope-active-<feature>` as one of its
    commands, after the chore commit and before HANDOFF. LOCK does only
    `touch /<repo_root>/.rabbit-scope-active-<feature>` and nothing
    else.
13. The assembled prompt's STEP 7 CODE-REVIEW MUST invoke
    `Skill("superpowers:requesting-code-review")`, not
    `Skill("superpowers:code-reviewer")`. The latter does not exist;
    using it silently no-ops the review step. The skill name is exact
    and case-sensitive.
14. The assembled prompt's STEP 6 IMPLEMENT loop MUST include an
    explicit commit of the implementation files after the test suite
    passes within an iteration: `git add <feature_dir>/` followed by
    `git commit -m "fix/feat(<feature>): <one-line summary>"` (verb
    chosen by the subagent based on whether this is a bugfix or new
    feature). The commit MUST happen INSIDE the iteration loop, BEFORE
    the `tdd-step.py transition <feature_dir> impl` call, so that the
    impl SHA captured by `git rev-parse HEAD` after the impl transition
    points at the actual implementation commit (not at the prior test
    commit from STEP 4).
15. The assembled prompt's STEP 8 TEST-GREEN MUST capture
    `git rev-parse HEAD` and substitute it into the `impl_commit` field
    of `tdd-report-<feature>.json` BEFORE STEP 9 UNLOCK runs its
    `chore(...)` commit. The chore commit advances HEAD past the
    implementation; if `impl_commit` is captured lazily (after the chore
    commit), it points at the chore commit, not the implementation. The
    prompt MUST make the capture order explicit and the tdd-report MUST
    be fully written before the UNLOCK chore commit begins.
16. The assembled prompt's STEP 1 SPEC-READ MUST diff the spec against
    the PARENT commit, not against HEAD. Use
    `git diff HEAD~1 -- <feature_dir>/docs/spec/` (or equivalent ref to
    the pre-spec-commit state). `git diff HEAD` shows only uncommitted
    changes; since `rabbit-feature-touch` Step 3 commits the spec change
    BEFORE dispatching the subagent (Inv 8), the working tree is clean
    at subagent start and `git diff HEAD` is always empty. Using
    `HEAD~1` ensures the subagent actually sees the spec delta it is
    expected to implement.
17. When `dispatch-tdd-subagent.py` runs and the file
    `.rabbit-human-approval-bypass` exists at the repo root, the
    assembled prompt MUST include a distinct yellow-coloured
    `[🐇 rabbit 🐇]` note (`\x1b[33m`, distinct from sync-check's red
    bypass alert) in the prompt preamble. The brand prefix MUST be the
    canonical emoji-framed form per contract Inv 35/36 and tdd-subagent
    Inv 5; the bare `[rabbit]` form is a constitution violation. The
    note MUST name both the marker path
    (`.rabbit-human-approval-bypass`) and the revoke skill invocation
    (`/rabbit-config human-approval true`) so the dispatched subagent
    (and any reviewer of the prompt) sees that the approval gate is
    currently disabled. The note is emitted EVERY dispatch while the
    marker exists; it does not consume or delete the marker. When the
    marker is absent, no such note appears (baseline prompt is
    unchanged).
18. `feature.json` for every rabbit feature conforms to the schema at
    `.claude/features/contract/schemas/feature.json.schema.json`, which
    is the canonical declaration. The fields the tdd-subagent feature
    relies on are: `name` (string), `version` (semver string),
    `owner` (string), `tdd_state` (string), `summary` (string),
    `surface` (object), and the flat `deprecation_criterion` (string).
    Test fixtures in this feature MUST use this flat shape; the legacy
    nested form is retired except where an explicit backward-
    compatibility test exercises it. The contract feature owns the
    schema file.
19. The assembled TDD subagent prompt MUST include a structured JSON
    HANDOFF schema at the top of its HANDOFF block. The schema is
    declared inline in the prompt with `handoff_schema_version: "1.0.0"`
    and lists the required fields (`feature`, `tdd_state`,
    `test_result`, `spec_compliance`, `tdd_report_path`, `closed_items`
    (array), `notes`). The subagent emits BOTH the legacy YAML-like
    HANDOFF block (for human readability and backward-compatible
    dispatchers) AND a fenced JSON HANDOFF block immediately after,
    prefixed `HANDOFF_JSON:` so downstream parsers can locate and
    validate it without ambiguity. The JSON HANDOFF is the machine-first
    source of truth per philosophy.md.
20. `agents/tdd-subagent.md` MUST NOT describe a dual-path layout for
    `scripts/tdd-step.py` (i.e., no "agent-local OR
    .claude/features/<X>/scripts" fork). The dispatched prompt always
    provides the absolute path to the state-machine scripts; the agent
    must use exactly that path. The agent file may name the deployed
    scripts directory (`.claude/agents/tdd-subagent/scripts/`) once for
    reference, but MUST NOT instruct the subagent to choose between two
    paths.

## Cross-Feature Dependencies

This feature READS the following scripts from `tdd-state-machine`
(declared in `contract.md`):

- `.claude/features/tdd-state-machine/scripts/tdd-step.py` — referenced
  in the assembled prompt for STEP 5 / STEP 6 / STEP 8 state
  transitions.

Deployment of the state-machine scripts into
`.claude/agents/tdd-subagent/scripts/` is handled by
`build-contract.json` (owned by the contract feature). This feature
does NOT copy or vendor the scripts.

## Migrated Invariants (history)

Earlier versions of this spec (v1.x) bundled state-machine invariants
and SKILL.md content invariants here. Two re-home migrations have since
moved them out:

- **BACKLOG-12** (v1.20.0): SKILL.md content invariants for
  `rabbit-feature-touch` moved to the `rabbit-feature` spec.
- **Slim after extraction** (v2.0.0): state-machine invariants
  (forward-only chain, transition output format, drift-check semantics,
  `tdd-context.py` field selection, etc.) moved to the
  `tdd-state-machine` spec when the scripts themselves were extracted.

These re-homings are listed here purely as a migration trace; the
authoritative declarations live in the new owners.

## Contract Schema References

The canonical `feature.json` schema is
`.claude/features/contract/schemas/feature.json.schema.json` (owned by
the contract feature). The tdd-subagent feature reads only the fields
listed in Inv 18; it does not own the schema and changes to it follow
the contract feature's versioning policy.

The HANDOFF JSON schema (Inv 19) is declared inline in the assembled
prompt because the dispatcher is the only consumer; if a third consumer
appears, the schema MUST be promoted to a file under
`.claude/features/contract/schemas/`.

## Confirm-Token Bypass Path

The full TDD cycle may be bypassed for a single edit when the main
session obtains explicit in-conversation user approval via a confirm
token. This path does NOT skip user authorization — the user's
in-conversation approval IS the authorization.

**Protocol:**

1. Main session presents a confirm token to the user, offering two
   choices:
   - `one-time` — bypass applies to the next single edit only; the
     override file is consumed and deleted after one use.
   - `session` — bypass applies for the remainder of the current
     session until manually removed.
2. User selects a choice in-conversation.
3. Main session writes `.rabbit-scope-override` at the repo root
   containing either `one-time` or `session` (no other content).
4. Main session writes `.rabbit-scope-active` containing the feature
   name.
5. Main session makes the edit directly (no TDD cycle, no subagent
   dispatch).
6. Scope-guard reads `.rabbit-scope-override` and allows the write; for
   `one-time` mode it deletes `.rabbit-scope-override` and creates
   `.rabbit-scope-override-used` as an audit trace.

**Constraints:**

- The override file MUST be written by the main session after receiving
  user approval; it MUST NOT be written speculatively or pre-emptively.
- The confirm token MUST be presented as a visible, explicit choice —
  never as an implicit default.
- The `SKILL.md` for `rabbit-feature-touch` (owned by rabbit-feature)
  documents this path under "Override Path — Bypassing TDD with User
  Approval".
- Audit: `.rabbit-scope-override-used` (created by scope-guard after
  one-time consumption) serves as the post-hoc audit trace.

## Out of Scope

- The TDD state machine itself (`tdd-step.py`, `tdd-context.py`,
  `tdd-drift-check.py`) — owned by `tdd-state-machine`.
- Deployment of the state-machine scripts to
  `.claude/agents/tdd-subagent/scripts/` — owned by
  `build-contract.json` (contract feature).
- Validating the schema of `feature.json` beyond the `tdd_state` field.
- Enforcing branch or PR rules around state transitions.
- Writing `feature.json` in locked-down environments — callers use
  `breeder` for that.
- The `rabbit-feature-touch` orchestration skill itself — owned by
  `rabbit-feature`.
- SKILL.md content invariants for `rabbit-feature-touch` — owned by
  `rabbit-feature`.
