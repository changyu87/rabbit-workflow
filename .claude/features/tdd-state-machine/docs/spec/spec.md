# tdd-state-machine

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns the forward-only TDD state machine that every rabbit feature touch
moves through. One script:

- `scripts/tdd-step.py` — the state machine itself (`show`, `next`,
  `transitions`, `transition`).

## Schema / Behavior

### Inv 1 — Valid state set

The valid `tdd_state` values are exactly:

    spec, spec-update, test-red, impl, test-green, deprecated

`transition` rejects any other target value with exit 1.

### Inv 2 — Primary forward order

The primary forward order is:

    spec -> spec-update -> test-red -> impl -> test-green -> deprecated

Without `--force`, a transition is accepted only when the new state is
the primary forward target of the current state (or the alternate target
defined in Inv 3).

### Inv 3 — Alternate forward edge

From `test-green`, the alternate forward target `spec-update` is
accepted without `--force`. This is the only alternate forward edge in
the state machine and lets a feature start a fresh cycle without going
through `deprecated`.

### Inv 4 — Backward transitions require `--force`

Any transition that is not a forward edge (per Inv 2 or Inv 3) is
rejected with exit 1 unless `--force` is supplied. With `--force`, a
transition between any two non-terminal states is accepted.

### Inv 5 — `deprecated` is terminal

From `deprecated`, every transition is rejected with exit 1, including
when `--force` is supplied.

### Inv 6 — Single-script feature

This feature owns exactly one script: `scripts/tdd-step.py`. The script
MUST be present at `.claude/features/tdd-state-machine/scripts/tdd-step.py`
and MUST be absent from `.claude/features/tdd-subagent/scripts/`.

### Inv 7 — Executable bit

`scripts/tdd-step.py` is stored with the user-executable bit set (any
mode satisfying `mode & 0o100`; in practice `0o755` or `0o775` depending
on the contributor's umask).

### Inv 8 — `spec-update -> test-red` precondition

The transition `spec-update -> test-red` is accepted only when at least
one of the following holds:

- `git diff HEAD` under `<feature-dir>/docs/spec/` is non-empty, OR
- `--spec-no-change-reason <reason>` is supplied with a non-empty
  reason; the reason is persisted on `feature.json` as
  `spec_no_change_reason`.

When neither holds, the transition is denied with exit 1.

### Inv 9 — Branding render via `rabbit_print`

`tdd-step.py` MUST render every transition message through the
centralised `rabbit_print` module loaded from
`.claude/features/contract/scripts/rabbit_print.py`. Accepted
transitions emit `tdd_transition(cur, new)` on stdout (ANSI green,
`[🐇 rabbit 🐇]` brand). Forced transitions additionally emit
`tdd_forced(cur, new)` on stderr (ANSI red).

### Inv 10 — `test-green` enforcement-check hook

After a successful transition into `test-green`, `tdd-step.py` calls
each of the following functions from `contract.lib.checks` in-process:

- `check_tests_non_interactive`
- `check_sentinel`
- `check_naming`
- `check_imports_resolve`
- `check_symlinks_resolve`
- `check_template_producer_consistency`

A non-passed `CheckResult` from any of these emits a non-empty warning
via `rabbit_print` on stderr. The hook is best-effort and never blocks
the transition.

### Inv 11 — `test-green` project-consolidate hook

After a successful transition into `test-green`, when
`project-map.json` exists in the enclosing project directory (the
parent of `<feature-dir>`'s parent), `tdd-step.py` invokes
`rabbit-project.py consolidate <project-name>`. The hook is
best-effort: any failure (missing script, broken project layout) is
swallowed and never blocks the transition.

### Inv 12 — `spec-update -> test-red` numbered-list check

After a successful transition `spec-update -> test-red`, `tdd-step.py`
calls `contract.lib.checks.check_numbered_lists` against
`<feature-dir>/docs/spec/`. A non-passed `CheckResult` emits a warning
via `rabbit_print` on stderr but does NOT block the transition. The
Inv 8 gate remains the only blocking precondition for this transition.

### Inv 13 — In-process library imports (no subprocess to CLI shims)

The check functions used by Inv 10 and Inv 12 are imported from the
`contract.lib.checks` library module at
`.claude/features/contract/lib/checks.py` and invoked in-process.
`tdd-step.py` MUST NOT fan out via `subprocess` to the
`.claude/features/contract/scripts/enforcement/check-*.py` CLI shims
for any of these checks.

### Inv 14 — Meta-contract sections (Plan E.* migration)

`feature.json` MUST declare the meta-contract sections `manifest`,
`runtime`, and `configuration`. The shapes are exactly:

- `manifest` is a list of length 1 whose single entry is
  `{"api": "publish_file", "args": {"source": "scripts/tdd-step.py",
  "dest": ".claude/agents/tdd-subagent/scripts/tdd-step.py"}}`,
  declaring the sole deployment target — the state-machine script
  deployed into the `tdd-subagent` agent directory (the cross-feature
  deployment required by Inv 6);
- `runtime` is `{}` — tdd-state-machine owns no Claude Code event
  hook handlers (consistent with `surface.hooks: []`);
- `configuration` is `[]` — tdd-state-machine exposes no
  user-configurable toggles.

The manifest is the meta-contract source of truth for what
tdd-state-machine deploys; the sibling `publish.json` is retained as
a Plan F cleanup artifact during the Plan E migration window and
declares the same single deployment target via the legacy
`source`+`destination` schema (the manifest uses `dest` to match the
canonical `publish_file` shape).

## What this feature does NOT define

- **Subagent dispatch** (`dispatch-tdd-subagent.py`, `tdd-subagent`
  agent markdown) — owned by `tdd-subagent`.
- **Deployment of the script** to `.claude/agents/tdd-subagent/scripts/`
  — owned by `build-contract.json`.
- **TDD orchestration / state policy at the workflow level**
  (`/rabbit-feature-touch`, human-approval gates) — owned by
  `rabbit-feature`.
- **Hook integration** (stop hook, post-tool hooks) — owned by their
  respective hook features.

## Tests

`test/run.py` runs the end-to-end suite. The suite exercises every
invariant above against `scripts/tdd-step.py`.
