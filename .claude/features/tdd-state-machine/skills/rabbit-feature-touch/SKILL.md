---
name: rabbit-feature-touch
description: Use when any write, edit, delete, or add operation targets a feature directory, or when a new feature is being created. Not for read-only queries, and NOT for metadata-only writes (bug filing, backlog filing) which require schema compliance only. Ensures the formal TDD state machine is advanced via tdd-step.sh on every feature touch, preventing test-green drift.
version: 1.0.0
owner: tdd-state-machine
deprecation_criterion: when dispatch-feature-edit.sh natively enforces tdd-step.sh transitions
---

## Overview

**Owner:** tdd-state-machine feature. This skill is the authoritative TDD orchestration reference — all TDD discipline is self-contained here.

## Core Orchestration Steps

1. **Identify feature dir** — locate via feature registry (`find .claude/features -name feature.json`) or by path convention.

2. **Check current state**
   ```
   tdd-step.sh show <feature-dir>
   ```

3. **Force to spec-update** (always `--force` — feature may be at any state)
   ```
   tdd-step.sh transition <feature-dir> spec-update --force
   ```

4. **Dispatch SPEC-UPDATE subagent** (Opus — R2) via `dispatch-spec-update.sh`. Pass `model: opus` to Agent.
   ```
   bash .claude/features/contract/scripts/dispatch-spec-update.sh <feature-name> "<what you are building or fixing>"
   ```

5. **Read HANDOFF** — verify `spec_changes` field is present. Read the git diff of the spec dir to understand what changed:
   ```
   git diff HEAD -- <feature-dir>/docs/spec/
   ```

6. **Advance to test-red** — pass `--spec-no-change-reason` if spec was unchanged:
   ```
   # spec was modified (normal case):
   tdd-step.sh transition <feature-dir> test-red

   # spec was NOT modified (e.g. bug fix where spec is already correct):
   tdd-step.sh transition <feature-dir> test-red --spec-no-change-reason "<reason from HANDOFF>"
   ```
   The state machine enforces that one of these conditions holds before advancing.

7. **Dispatch TEST subagent** via `dispatch-feature-edit.sh` with task: "Write failing tests only. Tests must assert the updated spec's invariants. Do NOT implement. Run tests, confirm they fail."

8. **Confirm test fails** — read subagent HANDOFF, verify `test_result: fail`. If not fail, STOP and investigate.

9. **Advance to impl**
   ```
   tdd-step.sh transition <feature-dir> impl
   ```

10. **Dispatch IMPLEMENTATION subagent** via `dispatch-feature-edit.sh` with task: "Implement to make the test pass. Follow spec.md invariants — do not deviate. Run all tests, confirm they pass. Then call: `tdd-step.sh transition <feature-dir> test-green`"

11. **Verify test-green**
    ```
    tdd-step.sh show <feature-dir>
    ```
    Must output `test-green`. If not, do not proceed.

    > Note: tdd-step.sh automatically closes any in-progress backlog items linked to the feature (transitions them to `implemented`, setting `fix_commits` to the HEAD commit SHA).

## New Feature Variant

If the feature does not exist yet, scaffold it first:
```
new-feature.sh <feature-name>
```
Then start at Step 1. The initial state will be `spec`; use `transition test-red` without `--force`.

## Common Mistakes

| Mistake | Consequence |
|---|---|
| Skipping spec-update and jumping straight to test dispatch | Spec stays stale; tests and impl follow main session's analysis, not the spec |
| Dispatching IMPL before reading HANDOFF from spec-update | No confirmation spec was considered; TDD gap enters silently |
| Advancing to test-red without checking git diff of spec | State machine accepts reason but you may have missed a needed change |
| Dispatching impl before confirming test fails | No proof the test is real; green state is meaningless |
| Omitting `--force` when resetting from test-green | Transition rejected; workflow stalls |
| Single dispatch for both test and impl | Test/impl boundary collapsed; R4 violated |

## Red Flags — STOP

- Any thought of "I'll skip spec-update, this is a simple fix"
- Any thought of "the spec is probably fine, I'll go straight to test-red"
- Any thought of "I'll just dispatch once and do both test and impl"
- Any thought of "tests-after is fine, I'll write impl first"
- Subagent HANDOFF shows `test_result: pass` at the test-only dispatch stage
- Advancing to test-red without reading the spec diff output
