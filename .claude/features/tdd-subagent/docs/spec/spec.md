---
feature: tdd-subagent
version: 1.13.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When the TDD step model is replaced by a different lifecycle model; or when state tracking moves out of feature.json into a dedicated event log.
status: active
---

# tdd-subagent — Spec

## Purpose

Provides the `tdd-step.py` CLI for forward-only TDD state transitions, drift detection, and enforcement gates at `test-green`. Owns the `rabbit-feature-touch` user-facing skill that ensures every feature touch advances the TDD state machine.

## Scripting Tech Stack

All scripts in this feature are Python 3. Bash is not used anywhere in this feature — not in runtime scripts, test harnesses, or fixtures. The sole test runner for each feature is `test/run.py`.

## Surface

- `.claude/features/tdd-subagent/scripts/tdd-step.py`
- `.claude/features/tdd-subagent/scripts/tdd-drift-check.py`
- `.claude/features/tdd-subagent/scripts/tdd-context.py`
- `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py` (assembles a per-feature full-TDD-cycle subagent prompt; the dispatched subagent runs spec-update → test-red → impl → test-green autonomously for ONE feature, using `.rabbit-scope-active-<feature>` as its scope marker so multiple features can be dispatched in parallel; accepts optional `--linked-item <item-dir>` and `--item-type <bug|backlog>` for a single primary item, AND an optional `--linked-items <feature>:<type>:<id>,...` for additional secondary items resolved by the same cycle — after the subagent reaches test-green the orchestrator captures the impl commit SHA and closes ALL linked items accordingly; prompt goes to stdout for caller dispatch)
- `.claude/features/tdd-subagent/skills/rabbit-feature-touch/` (self-contained TDD orchestration reference; triggers on any feature write/edit/delete/add and orchestrates via parallel per-feature subagents — Step 1 resolves scope by invoking the `rabbit-feature-scope` Skill via the Skill tool, Step 3 invokes `rabbit-spec` inline to author/update the spec and produce an impl-suggestion, Step 4 surfaces the impl-suggestion to the user for explicit approval (bypass via `.rabbit-human-approval-bypass` marker file at repo root, managed by `/rabbit-config human-approval bypass|gated`), Step 5 dispatches one `dispatch-tdd-subagent.py` subagent per resolved feature in parallel; the main session only orchestrates and never reads feature code itself)

## Invariants

1. `tdd_state` transitions are forward-only without `--force`.
2. `test-green` transition triggers enforcement checks.
3. All four scripts are executable.
4. `test-green` transition auto-closes any in-progress backlog items under `.claude/backlogs/<feature-name>/` via `backlog-item-status.py` with `fix_commits=HEAD` (best-effort).
5. `tdd-step.py transition` stdout uses the `[rabbit] ━━━ ... ━━━` format with ANSI colors — green (`\x1b[32m`) for normal transition messages on stdout, red (`\x1b[31m`) for FORCED/WARNING/ERROR messages on stderr. The `show`, `next`, and `transitions` subcommands remain plain-text (consumed by tests and downstream parsers).
6. In `rabbit-feature-touch` Step 1 (normal mode), scope resolution is performed by invoking the `rabbit-feature-scope` Skill via the Skill tool (`Skill("rabbit-feature-scope", args: "<request>")`), NOT by shelling out to `resolve-scope.sh` directly. The Skill emits a prompt for caller dispatch; the caller parses the JSON response `{"features": [...], "rationale": "..."}` to drive parallel dispatch.
7. `dispatch-tdd-subagent.py` emits a prompt to stdout only; it does not call any agent itself. The assembled prompt instructs the per-feature subagent to run the full TDD cycle (spec-update → test-red → impl → test-green) for ONE feature, using `.rabbit-scope-active-<feature-name>` as its scope marker. Distinct per-feature scope markers enable simultaneous dispatch across features without scope collision. The subagent writes `tdd-report.json` to `.rabbit/tdd-report.json` (a hidden folder at repo root); the `.rabbit/` directory is created automatically if it doesn't exist and is listed in `.gitignore`.
8. When `--linked-item <item-dir> --item-type bug|backlog` is provided to `dispatch-tdd-subagent.py`, the orchestrator (after test-green) closes the linked item via the rabbit-file unified script: `python3 .claude/features/rabbit-file/scripts/item-status.py set --feature <feature> --type <type> --id <id> --status close --reason 'TDD cycle complete' --fix-commits <impl-sha>`. The `<feature>` and `<id>` are derived from the `--linked-item` path (e.g., `rabbit/features/rabbit-cage/bugs/RABBIT-CAGE-BUG-8` → feature=`rabbit-cage`, id=`RABBIT-CAGE-BUG-8`). The legacy `bug-status.py` and `backlog-item-status.py` scripts no longer exist (consolidated into rabbit-file's `item-status.py` per RABBIT-FILE feature); any reference to them is a constitution violation. The HANDOFF block must include the linked item path and its new status. Additionally, when `--linked-items <feature>:<type>:<id>[,<feature>:<type>:<id>...]` is provided (a comma-separated list of triples), the orchestrator closes each listed item via the same `item-status.py set` invocation with `--reason 'TDD cycle complete (secondary item resolved by same commit)' --fix-commits <impl-sha>` after test-green. Each triple is validated for shape (exactly two colons, non-empty fields, type in {bug, backlog}); malformed triples cause dispatch-tdd-subagent.py to exit non-zero before emitting the prompt. The HANDOFF block must list all closed items (primary `--linked-item` plus every `--linked-items` entry).
9. `surface.skills` in `feature.json` MUST be `[]`. Skills are now managed via explicit copy-file entries in `build-contract.json`; the `surface.skills` field is retired and must remain an empty array.
10. E2E tests are always required — every behaviour described in a feature spec MUST
    have a corresponding end-to-end test. Unit tests alone are insufficient. The TDD
    subagent enforces this rule in the TEST-WRITE step without exception.
11. The 9 named steps (SPEC-READ, HUMAN-APPROVAL, LOCK, TEST-WRITE, TEST-RED,
    IMPLEMENT, CODE-REVIEW, TEST-GREEN, UNLOCK) are labelled sections in the assembled
    subagent prompt. tdd-step.py state transitions remain forward-only and unchanged.
12. dispatch-tdd-subagent.py interface: --scope (mandatory), --spec (mandatory),
    --impl-suggestion (optional), --linked-item / --item-type (B/B mode, primary item),
    --linked-items (optional, comma-separated `<feature>:<type>:<id>` triples for
    secondary items resolved by the same cycle), --human-approval-gate `true|false`
    (default `true`; `false` skips the subagent's HUMAN-APPROVAL step),
    --code-review-full-loop, --max-iterations (default 3, min 1). The legacy
    `--no-human-approval` flag is removed; all callers must use
    `--human-approval-gate false` instead. Boolean flag values follow the
    contract feature's CLI Naming Convention (Inv 15 of contract): exclusively
    `true` or `false`, never `enabled`/`disabled` or any other vocabulary.
13. `rabbit-feature-touch` SKILL.md describes a **seven-step** unified sequence
    (not six). The seven steps in order are: (1) Scope Resolution, (2) Create
    Branch, (3) Spec Authoring, (4) Human Approval, (5) Dispatch TDD Subagents,
    (6) Collect and Verify HANDOFFs, (7) PR / Hand Off. Both the overview heading
    and every step heading reflect this numbering.
14. Step 4 (Human Approval) is a **dispatcher-side** gate that lives in the main
    session, not inside the TDD subagent. The dispatcher reads the impl-suggestion
    JSON for each affected feature, surfaces a summary (request, spec changes,
    affected files, implementation approach) to the user, and waits for explicit
    approval before proceeding to Step 5 (Dispatch). The gate exists at the
    dispatcher because dispatched subagents run to completion and cannot pause
    for interactive user input.
15. Step 4 (Human Approval) is bypassable only when the user has explicitly
    requested autonomous execution. The bypass authorization is encoded as a
    hard file marker `.rabbit-human-approval-bypass` at the repo root, managed
    via the `/rabbit-config human-approval true|false` skill (owned by
    rabbit-cage; `false` writes the marker — gate disabled — and `true`
    deletes it). At Step 4, the dispatcher MUST check for this marker file:
    - If `.rabbit-human-approval-bypass` exists: skip the in-conversation
      wait, emit a visible `[rabbit]` warning naming the bypass marker and
      the path `/rabbit-config human-approval true` to revoke it, and pass
      `--human-approval-gate false` to the Step 5 `dispatch-tdd-subagent.py`
      invocation.
    - If the marker is absent: surface the impl-suggestion summary and wait
      for explicit in-conversation user approval. The dispatcher passes
      `--human-approval-gate true` (or omits the flag, since `true` is the
      default).
    In-conversation acknowledgements ("you have permission to bypass") are
    NOT a valid mechanism on their own — the marker file is the system of
    record. Silent bypass without either an explicit in-session direction
    backed by the marker, or a pre-existing marker, is prohibited.
16. After `rabbit-spec` returns in Step 3, the `rabbit-feature-touch` dispatcher
    MUST commit any modifications to the feature's `docs/spec/spec.md` (and any
    other files in `.claude/features/<feature>/` that `rabbit-spec` edited)
    BEFORE proceeding to Step 5 (Dispatch TDD Subagents). The commit message
    follows the pattern `spec(<feature>): update spec for <one-line request
    summary>`. This prevents spec changes from falling through uncommitted
    and ensures the TDD subagent reads a clean committed baseline. If
    `rabbit-spec` made no changes (or only wrote the impl-suggestion
    artifact), the commit is skipped.
17. In Step 9 (UNLOCK) of the per-feature TDD subagent prompt assembled by
    `dispatch-tdd-subagent.py`, the subagent MUST commit `feature.json`
    (which holds the final `tdd_state: test-green` transition written by
    `tdd-step.py`) BEFORE emitting the HANDOFF block. The commit message
    follows the pattern `chore(<feature>): advance tdd_state to test-green`.
    This prevents the state transition from falling through uncommitted and
    ensures the dispatcher does not need to commit `feature.json` manually
    after collecting HANDOFFs.
18. The TDD subagent for declared scope feature `F` MUST NOT create any
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
19. The dispatcher-side Step 4 check for `.rabbit-human-approval-bypass`
    (see Inv 15) MUST be documented in `rabbit-feature-touch` SKILL.md as
    the first action of Step 4 (Human Approval), BEFORE any in-conversation
    wait or impl-suggestion surfacing. When the marker is found, the
    warning emitted to the user MUST name the marker path
    (`.rabbit-human-approval-bypass`) and the revoke command
    (`/rabbit-config human-approval true`) so the user can audit and
    revoke without searching.
20. The assembled TDD subagent prompt (produced by `dispatch-tdd-subagent.py`)
    MUST include a rule in its IMPLEMENT step: if the implementation requires
    editing any file whose basename is `SKILL.md`, the subagent MUST invoke
    `Skill("skill-creator:skill-creator")` instead of using Write or Edit
    directly. Direct edits to SKILL.md bypass skill-creator's eval loop and
    description optimization. This rule is non-negotiable; a subagent that
    writes a SKILL.md without going through skill-creator commits a
    constitution violation.
21. `rabbit-feature-touch` SKILL.md's Red Flags section MUST include the
    rule: the main session orchestrator MUST NOT use Write or Edit tools on
    any file under `.claude/features/`. All feature-code edits are the TDD
    subagent's job, performed under an active scope marker. The main session
    role is orchestration only — resolve scope, create branch, invoke
    rabbit-spec, surface impl-suggestion, dispatch subagent, verify HANDOFF.
    Exceptions exist for explicit confirm-token overrides (see Confirm-Token
    Bypass Path) and for spec.md writes under the scope-guard path-pattern
    allowlist (Inv 20 of rabbit-cage) which are invoked by rabbit-spec
    during Step 3.
22. `rabbit-feature-touch` SKILL.md's Red Flags section MUST include the
    rule: the main session MUST NOT create `.rabbit-scope-active` (global) or
    `.rabbit-scope-active-<feature>` (per-feature) scope markers at the repo
    root. Scope markers are exclusively the TDD subagent's responsibility,
    written as the first action at LOCK (Step 3 of the subagent's named
    steps). Main-session-authored markers bypass scope-guard's intended
    boundary and have caused constitution violations (PR #93). This rule is
    distinct from Inv 18 (which prohibits the SUBAGENT from creating
    out-of-scope markers): Inv 22 prohibits the MAIN SESSION from creating
    any marker at all.
23. The assembled TDD subagent prompt's STEP 3 LOCK section MUST NOT use
    `trap '... rm -f ...' EXIT` to clean up the scope marker. Each Claude
    Code `Bash` tool invocation runs in a separate shell process; the trap
    fires immediately when that shell exits, deleting the marker before
    subsequent steps run. Cleanup MUST be explicit: STEP 9 UNLOCK
    executes `rm -f /<repo_root>/.rabbit-scope-active-<feature>` as one of
    its commands, after the chore commit and before HANDOFF. LOCK does only
    `touch /<repo_root>/.rabbit-scope-active-<feature>` and nothing else.
24. The assembled prompt's STEP 7 CODE-REVIEW MUST invoke
    `Skill("superpowers:requesting-code-review")`, not
    `Skill("superpowers:code-reviewer")`. The latter does not exist; using
    it silently no-ops the review step. The skill name is exact and
    case-sensitive.
25. The assembled prompt's STEP 6 IMPLEMENT loop MUST include an explicit
    commit of the implementation files after the test suite passes within an
    iteration: `git add <feature_dir>/` followed by
    `git commit -m "fix/feat(<feature>): <one-line summary>"` (verb chosen
    by the subagent based on whether this is a bugfix or new feature). The
    commit MUST happen INSIDE the iteration loop, BEFORE the `tdd-step.py
    transition <feature_dir> impl` call, so that the impl SHA captured by
    `git rev-parse HEAD` after the impl transition points at the actual
    implementation commit (not at the prior test commit from STEP 4).
26. The assembled prompt's STEP 8 TEST-GREEN MUST capture `git rev-parse
    HEAD` and substitute it into the `impl_commit` field of
    `tdd-report-<feature>.json` BEFORE STEP 9 UNLOCK runs its `chore(...)`
    commit. The chore commit advances HEAD past the implementation; if
    `impl_commit` is captured lazily (after the chore commit), it points at
    the chore commit, not the implementation. The prompt MUST make the
    capture order explicit and the tdd-report MUST be fully written before
    the UNLOCK chore commit begins.
27. The assembled prompt's STEP 1 SPEC-READ MUST diff the spec against the
    PARENT commit, not against HEAD. Use `git diff HEAD~1 -- <feature_dir>/docs/spec/`
    (or equivalent ref to the pre-spec-commit state). `git diff HEAD` shows
    only uncommitted changes; since `rabbit-feature-touch` Step 3 commits
    the spec change BEFORE dispatching the subagent (Inv 16), the working
    tree is clean at subagent start and `git diff HEAD` is always empty.
    Using `HEAD~1` ensures the subagent actually sees the spec delta it is
    expected to implement.
28. `tdd-context.py` MUST read `deprecation_criterion` (flat key) from
    `feature.json`, not `deprecation.criterion` (nested). The canonical
    schema across all rabbit features is the flat form; the nested form is
    legacy. For backward compatibility, read flat first; fall back to
    `deprecation.criterion` only if the flat key is absent. Tests MUST use
    the flat form in fixtures (the legacy nested form should appear only in
    explicit backward-compatibility tests).
29. `tdd-context.py` guidance text MUST reference `test/run.py` (the actual
    Python test runner) when describing how to verify tests pass at the
    `impl` state. References to `test/run.sh` are stale (no `.sh` files
    exist in any feature per the Python-only stack invariants in contract
    and rabbit-cage).
30. `rabbit-feature-touch` SKILL.md B/B mode MUST read the item JSON from
    `<item-dir>/item.json`, never from `<item-dir>/bug.json`. The
    rabbit-file schema uses `item.json` for both bug and backlog types
    (unified storage); `bug.json` is a legacy path that no longer exists.
    The B/B mode `related_feature` extraction MUST use
    `jq -r '.related_feature' <item-dir>/item.json`.

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
- The `SKILL.md` for `rabbit-feature-touch` documents this path under "Override Path — Bypassing TDD with User Approval".
- Audit: `.rabbit-scope-override-used` (created by scope-guard after one-time consumption) serves as the post-hoc audit trace.

## Out of Scope

- Validating the schema of `feature.json` beyond the `tdd_state` field.
- Enforcing branch or PR rules around state transitions.
- Writing `feature.json` in locked-down environments — callers use `breeder` for that.
