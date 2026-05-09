# tdd-state-machine

> **Note:** Human view. Source of truth is [`feature.json`](./feature.json).

## Purpose

Hardens the TDD discipline. Every feature has a `tdd_state` field; this
feature owns the rules for what those states mean, how they transition, and
how to detect drift between the claimed state and reality on disk. It also
provides the *context block* that every spawned subagent should receive so the
agent knows where the feature is in its lifecycle and what comes next.

## States

```
spec → test-red → impl → test-green → review → merged → deprecated
```

| State        | Meaning                                                      | Drift check        |
|--------------|--------------------------------------------------------------|--------------------|
| `spec`       | Spec written; tests not yet authored.                        | None               |
| `test-red`   | Tests authored; all failing as expected.                     | tests MUST fail    |
| `impl`       | Implementation in progress; tests transitioning.             | None (transient)   |
| `test-green` | All tests passing.                                           | tests MUST pass    |
| `review`     | PR open; under review.                                       | tests MUST pass    |
| `merged`     | PR merged into main.                                         | tests MUST pass    |
| `deprecated` | Superseded; consult `deprecation.successor`. Terminal.       | None               |

## Transitions

**Forward only**, without flags:

| From         | To           |
|--------------|--------------|
| `spec`       | `test-red`   |
| `test-red`   | `impl`       |
| `impl`       | `test-green` |
| `test-green` | `review`     |
| `review`     | `merged`     |
| `merged`     | `deprecated` |

**Anything else** (skipping, going backward, jumping multiple steps) requires
`--force`. `--force` is the explicit human override per the no-drift rule
("no skip unless user directly commanded").

`deprecated` is terminal: no transitions out, even with `--force`. To resurrect,
file a new feature.

## Scripts

### `tdd-step.sh`

```
tdd-step.sh show <feature-dir>           # print current state
tdd-step.sh next <feature-dir>           # print next allowed state
tdd-step.sh transitions <feature-dir>    # list allowed next state(s)
tdd-step.sh transition <feature-dir> <new-state> [--force]
```

Exit `0` on success, `1` on denied transition or invalid input, `2` on bad
invocation. Mutates `tdd_state` and `updated` in `feature.json`.

### `tdd-drift-check.sh`

```
tdd-drift-check.sh <feature-dir>
```

Runs the feature's `test/run.sh` and compares the exit code against what the
claimed `tdd_state` requires. Exit `0` on consistent state, `1` on drift.

### `tdd-context.sh`

```
tdd-context.sh <feature-dir>          # JSON output (default)
tdd-context.sh --text <feature-dir>   # human-readable summary
```

Emits a structured context block describing the feature's current state,
allowed next states, per-state guidance, deprecation criterion, and contract.
**This is the canonical block to inject into any subagent prompt that operates
on the feature**, so subagents always know "what step am I in, what's next, on
what criteria do I hand over." (See `my_request.txt` rule #3.)

## How subagents stay aligned

Per the philosophy of bounded scope and the user's hard-rule on TDD discipline,
every subagent dispatched to work on a feature **must** receive the output of
`tdd-context.sh <feature-dir>` in its prompt. This is policy, enforced by the
spawning agent (typically the main session or a planner). Without that block,
the subagent has no way to know which step it is in, which means it cannot
honor "no drift, no skip."

## What this feature does NOT define

- The schema of `feature.json` itself — that is `feature-skeleton`.
- Who can write to `feature.json` — that is `breeder` + `claude-write-lockdown`.
- The branch/PR rules around state transitions — that is `branch-per-feature`
  (under `hard-rules`).

## Tests

`test/run.sh` runs three test files (24 cases total):

- `test-tdd-step.sh` — 11 cases for show / next / transitions / transition / --force
- `test-drift-check.sh` — 8 cases for state-vs-reality consistency
- `test-context.sh` — 5 cases for JSON shape, text mode, per-state guidance, contract surfacing
