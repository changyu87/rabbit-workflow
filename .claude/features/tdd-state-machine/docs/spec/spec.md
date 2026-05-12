---
feature: tdd-state-machine
version: 1.4.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When the TDD step model is replaced by a different lifecycle model; or when state tracking moves out of feature.json into a dedicated event log.
status: active
---

# tdd-state-machine — Spec

## Purpose

Provides the `tdd-step.sh` CLI for forward-only TDD state transitions, drift detection, and enforcement gates at `test-green`. Owns the `rabbit-feature-touch` user-facing skill that ensures every feature touch advances the TDD state machine.

## Surface

- `.claude/features/tdd-state-machine/scripts/tdd-step.sh`
- `.claude/features/tdd-state-machine/scripts/tdd-drift-check.sh`
- `.claude/features/tdd-state-machine/scripts/tdd-context.sh`
- `.claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh` (builds an Opus-targeted prompt that, given a natural-language request, instructs the agent to read the feature registry — names, summaries, spec Purpose sections — and emit a structured JSON list of features the request targets; prompt goes to stdout for caller dispatch)
- `.claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh` (assembles a per-feature full-TDD-cycle subagent prompt; the dispatched subagent runs spec-update → test-red → impl → test-green autonomously for ONE feature, using `.rabbit-scope-active-<feature>` as its scope marker so multiple features can be dispatched in parallel; prompt goes to stdout for caller dispatch)
- `.claude/features/tdd-state-machine/skills/rabbit-feature-touch/` (self-contained TDD orchestration reference; triggers on any feature write/edit/delete/add and orchestrates via parallel per-feature subagents — Step 0 resolves scope by dispatching `resolve-feature-scope.sh` to Opus, Step 1 dispatches one `dispatch-feature-tdd.sh` subagent per resolved feature in parallel; the main session only orchestrates and never reads feature code itself)

## Invariants

1. `tdd_state` transitions are forward-only without `--force`.
2. `test-green` transition triggers `rebuild-registry.sh` and enforcement checks.
3. All five scripts are executable.
4. `test-green` transition auto-closes any in-progress backlog items under `.claude/backlogs/<feature-name>/` via `backlog-item-status.sh` with `fix_commits=HEAD` (best-effort).
5. `tdd-step.sh transition` stdout uses the `[rabbit] ━━━ ... ━━━` format with ANSI colors — green (`\x1b[32m`) for normal transition messages on stdout, red (`\x1b[31m`) for FORCED/WARNING/ERROR messages on stderr. The `show`, `next`, and `transitions` subcommands remain plain-text (consumed by tests and downstream parsers).
6. `resolve-feature-scope.sh` emits a prompt to stdout only; it does not call any agent itself. The caller dispatches the prompt to an Opus Agent, which reads the feature registry and returns structured JSON of the form `{"features": ["feat-a", "feat-b"], "rationale": "..."}`. The main session parses this JSON to drive parallel dispatch.
7. `dispatch-feature-tdd.sh` emits a prompt to stdout only; it does not call any agent itself. The assembled prompt instructs the per-feature subagent to run the full TDD cycle (spec-update → test-red → impl → test-green) for ONE feature, using `.rabbit-scope-active-<feature-name>` as its scope marker. Distinct per-feature scope markers enable simultaneous dispatch across features without scope collision.

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
