# tdd-state-machine

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns the forward-only TDD state machine that every rabbit feature touch
moves through. Three scripts:

- `scripts/tdd-step.py` — the state machine itself (`show`, `next`,
  `transitions`, `transition`).
- `scripts/tdd-context.py` — emits machine-first JSON describing a
  feature's current TDD state, allowed next states, and guidance text;
  consumed by subagent prompts.
- `scripts/tdd-drift-check.py` — verifies that a feature's claimed
  `tdd_state` matches the actual test-run outcome.

Extracted from `tdd-subagent` so that `tdd-subagent` itself can be slimmed
to subagent dispatch only (`dispatch-tdd-subagent.py` + agent definition).
This cycle handles the import side; a follow-up cycle will remove the
originals from `tdd-subagent` and a separate `build-contract.json` cycle
will repoint the deployed-script source.

## Schema / Behavior

### Inv 1 — Forward-only state machine

The state machine is forward-only. The canonical forward order is:

    spec -> spec-update -> test-red -> impl -> test-green -> deprecated

Backward transitions are denied unless `--force` is supplied. `deprecated`
is terminal and rejects all transitions, even with `--force`.

There is exactly one forward-only alternative branch (`_FORWARD_ALT`):
`test-green -> spec-update`, used to start a new cycle on the same feature
after the previous cycle reached test-green.

### Inv 2 — Three scripts, named exactly

`scripts/tdd-step.py`, `scripts/tdd-context.py`, `scripts/tdd-drift-check.py`.
No additional scripts are introduced by this feature in this cycle.

### Inv 3 — Executable bits

All three scripts are stored with mode `0755` (executable). The end-to-end
test suite invokes them via `python3 <script>` so the executable bit is not
strictly required at run-time, but is preserved to match the source from
`tdd-subagent`.

### Inv 4 — `tdd-context.py` guidance aligns with `_FORWARD_ALT`

`tdd-context.py` must surface `spec-update` in `allowed_next_states` when
`current_state == "test-green"` so callers see the cycle-restart branch
that `tdd-step.py` honours.

### Inv 5 — `tdd-drift-check.py` invocation contract

`tdd-drift-check.py <feature-dir>` exits 0 when the claimed state matches
reality, 1 when drift is detected, 2 on invocation error. The drift rules
per state:

- `spec`, `spec-update`, `deprecated` — not test-checked.
- `test-red` — `test/run.py` MUST exit non-zero.
- `impl` — transitional, no test-outcome check.
- `test-green` — `test/run.py` MUST exit 0.

### Inv 6 — Byte-identical-import regression guard (this cycle only)

For the duration of the import cycle the three scripts under
`scripts/` MUST be byte-identical to their counterparts under
`.claude/features/tdd-subagent/scripts/`. The follow-up cycle that
deletes the `tdd-subagent` originals will replace this invariant with
"present here, absent in `tdd-subagent`".

## What this feature does NOT define

- **Subagent dispatch** (`dispatch-tdd-subagent.py`, `tdd-subagent` agent
  markdown) — owned by `tdd-subagent`.
- **Deployment of the scripts** to
  `.claude/agents/tdd-subagent/scripts/` — that path mapping is owned by
  `build-contract.json` (changed in a separate contract-feature cycle).
- **TDD orchestration / state policy at the workflow level**
  (`/rabbit-feature-touch`, human-approval gates, etc.) — owned by
  `rabbit-feature`.
- **Hook integration** (stop hook, post-tool hooks) — owned by their
  respective hook features.

## Tests

`test/run.py` runs the end-to-end suite. The suite imports the three
state-machine scripts from this feature's own `scripts/` directory and
exercises every documented behaviour above, plus a byte-identical
regression check (Inv 6).
