# rabbit-feature

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns the rabbit-feature-touch orchestration skill (and future rabbit-feature-scope, rabbit-feature-spec). Invokes tdd-subagent's dispatch-tdd-subagent.py and tdd-step.py across a declared cross-feature contract.

## Schema / Behavior

TODO: describe what this feature does in narrative form.

## What this feature does NOT define

TODO: name adjacent concerns and which features own them. (Bounded scope.)

## Tests

`test/run.py` runs the end-to-end suite. Currently red (expected: this
feature is in `tdd_state: spec`; tests have not been authored yet).

Per the TDD state machine: author tests next, transition to `test-red`,
then implement, transition to `impl`, etc.
