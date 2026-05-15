---
feature: tdd-state-machine
version: 1.5.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When the TDD step model is replaced by a different lifecycle model; or when state tracking moves out of feature.json into a dedicated event log.
status: active
---

# tdd-state-machine — Spec

## Purpose

Provides the `tdd-step.py` CLI for forward-only TDD state transitions, drift detection, and enforcement gates at `test-green`. Owns the `rabbit-feature-touch` user-facing skill that ensures every feature touch advances the TDD state machine.

## Scripting Tech Stack

All scripts in this feature are Python 3. Bash is not used anywhere in this feature — not in runtime scripts, test harnesses, or fixtures. The sole test runner for each feature is `test/run.py`.

## Surface

- `.claude/features/tdd-state-machine/scripts/tdd-step.py`
- `.claude/features/tdd-state-machine/scripts/tdd-drift-check.py`
- `.claude/features/tdd-state-machine/scripts/tdd-context.py`
- `.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.py` (assembles a per-feature full-TDD-cycle subagent prompt; the dispatched subagent runs spec-update → test-red → impl → test-green autonomously for ONE feature, using `.rabbit-scope-active-<feature>` as its scope marker so multiple features can be dispatched in parallel; accepts optional `--linked-item <item-dir>` and `--item-type <bug|backlog>` — after the subagent reaches test-green the orchestrator captures the impl commit SHA and closes the linked item accordingly; prompt goes to stdout for caller dispatch)
- `.claude/features/tdd-state-machine/skills/rabbit-feature-touch/` (self-contained TDD orchestration reference; triggers on any feature write/edit/delete/add and orchestrates via parallel per-feature subagents — Step 1 resolves scope by invoking the `rabbit-feature-scope` Skill via the Skill tool, Step 3 dispatches one `dispatch-feature-tdd.py` subagent per resolved feature in parallel; the main session only orchestrates and never reads feature code itself)

## Invariants

1. `tdd_state` transitions are forward-only without `--force`.
2. `test-green` transition triggers enforcement checks.
3. All four scripts are executable.
4. `test-green` transition auto-closes any in-progress backlog items under `.claude/backlogs/<feature-name>/` via `backlog-item-status.py` with `fix_commits=HEAD` (best-effort).
5. `tdd-step.py transition` stdout uses the `[rabbit] ━━━ ... ━━━` format with ANSI colors — green (`\x1b[32m`) for normal transition messages on stdout, red (`\x1b[31m`) for FORCED/WARNING/ERROR messages on stderr. The `show`, `next`, and `transitions` subcommands remain plain-text (consumed by tests and downstream parsers).
6. In `rabbit-feature-touch` Step 1 (normal mode), scope resolution is performed by invoking the `rabbit-feature-scope` Skill via the Skill tool (`Skill("rabbit-feature-scope", args: "<request>")`), NOT by shelling out to `resolve-scope.sh` directly. The Skill emits a prompt for caller dispatch; the caller parses the JSON response `{"features": [...], "rationale": "..."}` to drive parallel dispatch.
7. `dispatch-feature-tdd.py` emits a prompt to stdout only; it does not call any agent itself. The assembled prompt instructs the per-feature subagent to run the full TDD cycle (spec-update → test-red → impl → test-green) for ONE feature, using `.rabbit-scope-active-<feature-name>` as its scope marker. Distinct per-feature scope markers enable simultaneous dispatch across features without scope collision. The subagent writes `tdd-report.json` to `.rabbit/tdd-report.json` (a hidden folder at repo root); the `.rabbit/` directory is created automatically if it doesn't exist and is listed in `.gitignore`.
8. When `--linked-item <item-dir> --item-type bug` is provided to `dispatch-feature-tdd.py`, the orchestrator calls `bug-status.py set <item-dir> closed --reason 'TDD cycle complete' --fix-commits <impl-sha>` after test-green. When `--item-type backlog` is provided, it calls `backlog-item-status.py set <item-dir> implemented --reason 'TDD cycle complete' --fix-commits <impl-sha>`. These calls commit the item automatically. The HANDOFF block must include the linked item path and its new status.
9. `surface.skills` in `feature.json` MUST be `[]`. Skills are now managed via explicit copy-file entries in `build-contract.json`; the `surface.skills` field is retired and must remain an empty array.

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
