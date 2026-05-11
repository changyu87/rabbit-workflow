---
feature: tdd-state-machine
version: 1.1.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When the TDD step model is replaced by a different lifecycle model; or when state tracking moves out of feature.json into a dedicated event log.
status: active
---

# tdd-state-machine — Spec

## Purpose

Provides the `tdd-step.sh` CLI for forward-only TDD state transitions, drift detection, and enforcement gates at `test-green`.

## Surface

- `.claude/features/tdd-state-machine/scripts/tdd-step.sh`
- `.claude/features/tdd-state-machine/scripts/tdd-drift-check.sh`
- `.claude/features/tdd-state-machine/scripts/tdd-context.sh`

## Invariants

1. `tdd_state` transitions are forward-only without `--force`.
2. `test-green` transition triggers `rebuild-registry.sh` and enforcement checks.
3. All three scripts are executable.
4. `test-green` transition auto-closes any in-progress backlog items under `.claude/backlogs/<feature-name>/` via `backlog-item-status.sh` with `fix_commits=HEAD` (best-effort).

## Out of Scope

- Validating the schema of `feature.json` beyond the `tdd_state` field.
- Enforcing branch or PR rules around state transitions.
- Writing `feature.json` in locked-down environments — callers use `breeder` for that.
