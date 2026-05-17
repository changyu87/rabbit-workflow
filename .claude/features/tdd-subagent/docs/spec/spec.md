---
feature: tdd-subagent
version: 1.6.0
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
- `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py` (assembles a per-feature full-TDD-cycle subagent prompt; the dispatched subagent runs spec-update → test-red → impl → test-green autonomously for ONE feature, using `.rabbit-scope-active-<feature>` as its scope marker so multiple features can be dispatched in parallel; accepts optional `--linked-item <item-dir>` and `--item-type <bug|backlog>` — after the subagent reaches test-green the orchestrator captures the impl commit SHA and closes the linked item accordingly; prompt goes to stdout for caller dispatch)
- `.claude/features/tdd-subagent/skills/rabbit-feature-touch/` (self-contained TDD orchestration reference; triggers on any feature write/edit/delete/add and orchestrates via parallel per-feature subagents — Step 1 resolves scope by invoking the `rabbit-feature-scope` Skill via the Skill tool, Step 3 invokes `rabbit-spec` inline to author/update the spec and produce an impl-suggestion, Step 4 surfaces the impl-suggestion to the user for explicit approval (bypassable via `--no-human-approval`), Step 5 dispatches one `dispatch-tdd-subagent.py` subagent per resolved feature in parallel; the main session only orchestrates and never reads feature code itself)

## Invariants

1. `tdd_state` transitions are forward-only without `--force`.
2. `test-green` transition triggers enforcement checks.
3. All four scripts are executable.
4. `test-green` transition auto-closes any in-progress backlog items under `.claude/backlogs/<feature-name>/` via `backlog-item-status.py` with `fix_commits=HEAD` (best-effort).
5. `tdd-step.py transition` stdout uses the `[rabbit] ━━━ ... ━━━` format with ANSI colors — green (`\x1b[32m`) for normal transition messages on stdout, red (`\x1b[31m`) for FORCED/WARNING/ERROR messages on stderr. The `show`, `next`, and `transitions` subcommands remain plain-text (consumed by tests and downstream parsers).
6. In `rabbit-feature-touch` Step 1 (normal mode), scope resolution is performed by invoking the `rabbit-feature-scope` Skill via the Skill tool (`Skill("rabbit-feature-scope", args: "<request>")`), NOT by shelling out to `resolve-scope.sh` directly. The Skill emits a prompt for caller dispatch; the caller parses the JSON response `{"features": [...], "rationale": "..."}` to drive parallel dispatch.
7. `dispatch-tdd-subagent.py` emits a prompt to stdout only; it does not call any agent itself. The assembled prompt instructs the per-feature subagent to run the full TDD cycle (spec-update → test-red → impl → test-green) for ONE feature, using `.rabbit-scope-active-<feature-name>` as its scope marker. Distinct per-feature scope markers enable simultaneous dispatch across features without scope collision. The subagent writes `tdd-report.json` to `.rabbit/tdd-report.json` (a hidden folder at repo root); the `.rabbit/` directory is created automatically if it doesn't exist and is listed in `.gitignore`.
8. When `--linked-item <item-dir> --item-type bug` is provided to `dispatch-tdd-subagent.py`, the orchestrator calls `bug-status.py set <item-dir> closed --reason 'TDD cycle complete' --fix-commits <impl-sha>` after test-green. When `--item-type backlog` is provided, it calls `backlog-item-status.py set <item-dir> implemented --reason 'TDD cycle complete' --fix-commits <impl-sha>`. These calls commit the item automatically. The HANDOFF block must include the linked item path and its new status.
9. `surface.skills` in `feature.json` MUST be `[]`. Skills are now managed via explicit copy-file entries in `build-contract.json`; the `surface.skills` field is retired and must remain an empty array.
10. E2E tests are always required — every behaviour described in a feature spec MUST
    have a corresponding end-to-end test. Unit tests alone are insufficient. The TDD
    subagent enforces this rule in the TEST-WRITE step without exception.
11. The 9 named steps (SPEC-READ, HUMAN-APPROVAL, LOCK, TEST-WRITE, TEST-RED,
    IMPLEMENT, CODE-REVIEW, TEST-GREEN, UNLOCK) are labelled sections in the assembled
    subagent prompt. tdd-step.py state transitions remain forward-only and unchanged.
12. dispatch-tdd-subagent.py interface: --scope (mandatory), --spec (mandatory),
    --impl-suggestion (optional), --linked-item / --item-type (B/B mode),
    --no-human-approval, --code-review-full-loop, --max-iterations (default 3, min 1).
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
    requested autonomous execution. The bypass is signalled by passing
    `--no-human-approval` to the `dispatch-tdd-subagent.py` invocation in Step 5.
    Silent bypass without user direction is prohibited.

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
