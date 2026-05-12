---
name: rabbit-feature-touch
description: Use when any write, edit, delete, or add operation targets a feature directory, or when a new feature is being created. Not for read-only queries, and NOT for metadata-only writes (bug filing, backlog filing) which require schema compliance only. Ensures the formal TDD state machine is advanced via tdd-step.sh on every feature touch, preventing test-green drift.
version: 2.0.0
owner: tdd-state-machine
deprecation_criterion: when dispatch-feature-edit.sh natively enforces tdd-step.sh transitions
---

## Overview

**Owner:** tdd-state-machine feature. This skill is the authoritative TDD orchestration reference — all TDD discipline is self-contained here.

The main session's role is **orchestration only**: resolve which features are touched, dispatch one parallel subagent per feature, collect HANDOFFs. The main session does NOT read feature code or reason about implementation — those responsibilities belong to the dispatched subagents.

## Step 0 — Resolve Feature Scope

Before any TDD cycle, identify which features the request targets:

```bash
# Build the scope-resolution prompt and dispatch to Opus:
SCOPE_PROMPT=$(bash .claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh "<request-description>")
# Dispatch Agent(model: opus, prompt: SCOPE_PROMPT)
# Opus responds with JSON: {"features": ["feat-a", "feat-b"], "rationale": "..."}
```

The Opus response is the authoritative feature list. Main session does not second-guess it.

## Step 1 — Parallel TDD Dispatch (one Agent per feature)

For each feature in the Opus response, build a full-TDD-cycle prompt and dispatch simultaneously:

```bash
# For each feature (dispatch ALL in parallel — single Agent tool call with multiple invocations):
PROMPT_A=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh feat-a "<request-description>")
PROMPT_B=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh feat-b "<request-description>")
# Dispatch Agent(prompt: PROMPT_A) and Agent(prompt: PROMPT_B) simultaneously
```

### Optional: Linking a Bug or Backlog Item

When the request originated from a tracked bug or backlog item, pass the optional flag so the
orchestrator automatically closes/marks-implemented the item after reaching test-green:

```bash
# Link a bug (closes it after test-green):
PROMPT=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh feat-a "<request>" --bug .claude/bugs/<bug-dir>)

# Link a backlog item (marks it implemented after test-green):
PROMPT=$(bash .claude/features/tdd-state-machine/scripts/dispatch-feature-tdd.sh feat-a "<request>" --backlog .claude/backlogs/<feature-name>/<item-dir>)
```

The dispatched subagent captures the impl commit SHA after test-green and calls the appropriate
status script (`bug-status.sh set ... closed` or `backlog-item-status.sh set ... implemented`).
The HANDOFF block includes `linked_item: <path> (status: <new-status>)` when a flag was passed.

Each dispatched agent:
- Sets `.rabbit-scope-active-<feature>` at the repo root (parallel-safe, no race)
- Runs the full TDD cycle: spec-update → test-red → impl → test-green
- Emits a structured HANDOFF when complete

## Step 2 — Collect and Verify HANDOFFs

After all agents complete, verify each HANDOFF:
- `tdd_state: test-green` for every feature
- `test_result: pass` for every feature

If any feature fails, investigate that feature's agent output before proceeding.

## New Feature Variant

If a feature does not exist yet, scaffold it first (before Step 0):
```bash
new-feature.sh <feature-name>
```
Then proceed from Step 0. The feature-tdd subagent will start from `spec` state (no `--force` needed for its first transition).

## Red Flags — STOP

- Any thought of "I'll read the feature files myself to understand what needs changing" → STOP. That's the subagent's job.
- Any thought of "I'll skip Step 0 and just pick the features myself" → STOP. Scope resolution must go through resolve-feature-scope.sh.
- Any thought of "I'll dispatch features sequentially to be safe" → STOP. Dispatch in parallel; per-feature scope markers prevent races.
- Subagent HANDOFF shows `tdd_state` other than `test-green` → STOP and investigate.
- Subagent HANDOFF shows `test_result: pass` at the test-only dispatch stage → STOP, the test subagent did not fail correctly.
## Override Path — Bypassing TDD with User Approval

When the main session wants to make a quick edit without running the full TDD cycle, it may present an explicit confirm token to the user in-conversation. The user's in-conversation approval IS the authorization — this path does NOT skip authorization.

### Conditions for Use

Use the override path only when:
- The edit is narrow and low-risk (e.g., a typo fix, a documentation-only change, a comment update).
- The full TDD cycle cost is not justified for this specific change.
- The user is present and available to grant approval explicitly.

### Protocol

1. **Present the confirm token.** The main session shows the user a clearly labelled confirm token with the proposed change and two choices:
   - `one-time` — the override applies to the next single edit only. After the write, the scope-guard deletes `.rabbit-scope-override` and creates `.rabbit-scope-override-used` as an audit trace.
   - `session` — the override applies for the remainder of the current session (until `.rabbit-scope-override` is manually removed or the session ends).

2. **Wait for user selection.** Do NOT proceed without an explicit in-conversation choice. No implicit defaults.

3. **Write the override file.** After the user approves, the main session writes `.rabbit-scope-override` at the repo root containing exactly `one-time` or `session` (no other content).

4. **Write the scope marker.** The main session writes `.rabbit-scope-active` containing the feature name.

5. **Make the edit directly.** The main session edits the file without dispatching a subagent and without advancing `tdd-step.sh`.

6. **Scope-guard enforcement.** The scope-guard reads `.rabbit-scope-override` at write time and allows the write. For `one-time` mode it automatically consumes the override file (deletes `.rabbit-scope-override`, creates `.rabbit-scope-override-used`).

### Constraints

- The override file MUST be written **after** the user approves — never pre-emptively.
- The confirm token presentation MUST be explicit and visible — never buried in a wall of text.
- The main session must NOT dispatch a subagent for the overridden edit; it edits directly.
- The override does NOT reset the feature's `tdd_state`. The feature remains in `test-green` (or whatever state it was in). The next feature touch via the normal path will trigger a fresh TDD cycle as usual.
- If the user does not respond or declines, the main session falls back to the full TDD path.

