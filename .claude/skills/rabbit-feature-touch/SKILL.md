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
