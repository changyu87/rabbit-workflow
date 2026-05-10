---
name: rabbit-feature-touch
description: Use when any write, edit, delete, or add operation targets a feature directory, or when a new feature is being created. Not for read-only queries. Ensures the formal TDD state machine is advanced via tdd-step.sh on every feature touch, preventing test-green drift.
version: 1.0.0
owner: rabbit-cage
deprecation_criterion: when dispatch-feature-edit.sh natively enforces tdd-step.sh transitions
---

## Overview

This skill enforces the full TDD step sequence around every feature modification by orchestrating tdd-step.sh transitions before and after each dispatch leg. It closes the test-green drift gap caused by subagents doing ad-hoc testing without advancing the formal state machine.

## When to Use

Trigger on any write/edit/delete/add to a feature directory, or new feature creation. Do NOT use for read-only queries or status checks.

## Core Orchestration Steps

1. **Identify feature dir** — locate via feature registry (`find .claude/features -name feature.json`) or by path convention.

2. **Check current state**
   ```
   tdd-step.sh show <feature-dir>
   ```

3. **Force to test-red** (always `--force` — feature may already be test-green)
   ```
   tdd-step.sh transition <feature-dir> test-red --force
   ```

4. **Dispatch TEST subagent** via `dispatch-feature-edit.sh` with task: "Write failing test only. Do NOT implement. Run the test, confirm it fails."

5. **Confirm test fails** — read subagent HANDOFF, verify `test_result: fail`. If not fail, STOP and investigate.

6. **Advance to impl**
   ```
   tdd-step.sh transition <feature-dir> impl
   ```

7. **Dispatch IMPLEMENTATION subagent** via `dispatch-feature-edit.sh` with task: "Implement to make the test pass. Run all tests, confirm they pass. Then call: `tdd-step.sh transition <feature-dir> test-green`"

8. **Verify test-green**
   ```
   tdd-step.sh show <feature-dir>
   ```
   Must output `test-green`. If not, do not proceed.

## New Feature Variant

If the feature does not exist yet, scaffold it first:
```
new-feature.sh <feature-name>
```
Then start at Step 1. The initial state will be `spec`; use `transition test-red` without `--force`.

## Common Mistakes

| Mistake | Consequence |
|---|---|
| Skipping tdd-step.sh calls | TDD state machine never advances; state stays stale |
| Dispatching impl before confirming test fails | No proof the test is real; green state is meaningless |
| Omitting `--force` when resetting from test-green | Transition rejected; workflow stalls |
| Single dispatch for both test and impl | Test/impl boundary collapsed; R4 violated |

## Red Flags — STOP

- Any thought of "I'll just dispatch once and do both test and impl"
- Any thought of "tests-after is fine, I'll write impl first"
- Any thought of "the feature is simple, I can skip the state transitions"
- Subagent HANDOFF shows `test_result: pass` at the test-only dispatch stage
