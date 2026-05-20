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

Extracted from `tdd-subagent` so that `tdd-subagent` itself contains only
subagent dispatch (`dispatch-tdd-subagent.py` + agent definition). The
import + slim cycles are complete; the three scripts are owned here and
absent from `tdd-subagent/scripts/`.

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

All three scripts are stored with the user-executable bit set (any mode
satisfying `mode & 0o100`; in practice `0o755` or `0o775` depending on the
contributor's umask). The end-to-end test suite invokes them via
`python3 <script>` so the executable bit is not strictly required at
run-time, but is preserved for direct invocation.

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

### Inv 6 — Sole ownership: present here, absent in `tdd-subagent`

`tdd-state-machine` owns `tdd-step.py`, `tdd-context.py`, and
`tdd-drift-check.py`. These scripts MUST be present in
`.claude/features/tdd-state-machine/scripts/` and MUST be absent from
`.claude/features/tdd-subagent/scripts/`. Replaces the previous
byte-identity guard from the import cycle (the `tdd-subagent` originals
have been deleted).

### Inv 7 — Post `test-green` hooks

On a successful transition to `test-green`, `tdd-step.py` invokes
`_post_test_green_hooks(<feature-dir>)`. The hook runs (best-effort, never
blocks the transition):

- `_run_enforcement_checks` — calls the library functions in
  `contract.lib.checks` directly (no subprocess fan-out to enforcement
  CLI scripts). The set called: `check_tests_non_interactive`,
  `check_sentinel`, `check_naming`, `check_imports_resolve`,
  `check_symlinks_resolve`, `check_template_producer_consistency`.
  A failed `CheckResult` emits a warning via `rabbit_print` on stderr
  but does not fail the transition.
- `rabbit-project.py consolidate <project>` — invoked when the enclosing
  project directory carries a `project-map.json`; failure is swallowed.
- `auto_close_backlog` — retained as a no-op stub (the dispatcher closes
  linked items).

### Inv 8 — `--spec-no-change-reason` flag and git-diff gate

For the transition `spec-update -> test-red`, `tdd-step.py` requires
either (a) a non-empty `git diff HEAD` under `<feature-dir>/docs/spec/`,
or (b) the `--spec-no-change-reason <reason>` flag with a non-empty
reason. When (b) is supplied the reason is persisted on `feature.json`
as `spec_no_change_reason`. Missing both causes the transition to be
denied with exit 1.

### Inv 9 — `rabbit_print` branding contract

`tdd-step.py` MUST render all transition messages through the centralised
`rabbit_print` module loaded from
`.claude/features/contract/scripts/rabbit_print.py`. Accepted forward
transitions emit `tdd_transition(cur, new)` (ANSI green, `[🐇 rabbit 🐇]`
brand) on stdout; forced transitions additionally emit `tdd_forced(...)`
(ANSI red) on stderr.

### Inv 10 — `test-green` has `spec-update` as an alternate forward target

`tdd-step.py`'s `_FORWARD_ALT['test-green']` MUST include `spec-update`
so a feature reaching `test-green` can start a fresh cycle without
`--force`. This is the structural backing for Inv 1's `_FORWARD_ALT`
narrative.

### Inv 11 — `_run_enforcement_checks` uses the `contract.lib.checks` library

`tdd-step.py` MUST import the check functions from
`contract.lib.checks` (located at
`.claude/features/contract/lib/checks.py`) and call them in-process. It
MUST NOT fan out via `subprocess` to the
`.claude/features/contract/scripts/enforcement/check-*.py` CLI shims.
The library returns a `CheckResult` per call; a non-passed result emits a
`rabbit_print` warning on stderr and the transition continues.

### Inv 12 — `spec-update -> test-red` runs `check_numbered_lists`

For the transition `spec-update -> test-red`, `tdd-step.py` MUST call
`contract.lib.checks.check_numbered_lists` against the feature's
`docs/spec/` directory. A non-passed result emits a warning via
`rabbit_print` on stderr but does NOT block the transition (the
git-diff / `--spec-no-change-reason` gate from Inv 8 remains the only
blocking precondition for this transition).

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
exercises every documented behaviour above, including the
present-here-absent-in-`tdd-subagent` check for Inv 6
(`test-no-originals-in-tdd-subagent.py`).
