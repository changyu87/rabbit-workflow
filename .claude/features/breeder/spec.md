# rabbit-breeder

> Source of truth: [`feature.json`](./feature.json).
> Agent definition: [`../../agents/rabbit-breeder.md`](../../agents/rabbit-breeder.md).

## Purpose

The `breeder` is a Claude Code subagent that owns all writes to `.claude/`.
The convention is: **no other agent — including the main session — writes to
`.claude/` directly**. Every mutation of a file under `.claude/` is dispatched
to the breeder via the `Agent` tool with `subagent_type: "rabbit-breeder"`.

Why bind writes to one agent? Because `.claude/` is the workflow's
constitution. When every change passes through one funnel that knows the
schemas and the TDD discipline, drift becomes harder.

## Honest scope of enforcement

This is a **convention**, not a hardware-level lock. Claude Code's permission
system is tool-call-level, not subagent-aware. Specifically:

- The `claude-write-lockdown` feature (separate PR) adds `permissions.deny`
  rules for `Write(.claude/**)` and `Edit(.claude/**)` in the shared
  `.claude/settings.json`. **These deny rules apply to ALL agents, including
  the breeder.**
- The breeder, in turn, performs `.claude/` mutations via `Bash` (heredocs,
  `cat >`, `sed`, `jq` in-place). `Bash` is not path-restricted in deny
  rules, so the breeder retains write capability while the `Write`/`Edit`
  tools are denied across the board.
- Other agents could *also* use `Bash` to bypass the deny rule. The
  convention says they will not, and code review enforces this.

The result is a hybrid: tool-level deny on `Write`/`Edit` blocks the *easy*
path of accidental writes, and the convention plus PR review handles the
*intentional* path. This is sufficient for an honest team-of-agents.

## Invocation

```
Agent({
  subagent_type: "rabbit-breeder",
  prompt: <structured request, see Input contract in agents/rabbit-breeder.md>
})
```

The caller supplies a structured request listing `operation`, `target`,
`payload`, `tdd_context` (optional), and `reason`. The breeder parses,
validates, applies, and returns a structured `RESULT:` block.

## Validation responsibilities

After every write that touches a `.claude/features/<name>/` directory, the
breeder MUST run:

```
bash .claude/features/feature-skeleton/scripts/validate-feature.sh \
  .claude/features/<name>/
```

Non-zero exit → roll back the write or report `REJECTED: schema violation`.

After every TDD state transition, the breeder MUST run:

```
bash .claude/features/tdd-state-machine/scripts/tdd-drift-check.sh \
  .claude/features/<name>/
```

Drift detected → refuse to commit; reply `REJECTED: drift — <details>`.

## What this feature does NOT define

- The deny rules in `settings.json` themselves — that is
  `claude-write-lockdown`.
- The schema the breeder validates against — that is `feature-skeleton`.
- The state machine the breeder honors — that is `tdd-state-machine`.
- The bug filing format used in `add_bug` operations — that is `bug-filing`.

Bounded scope: this feature owns the **agent definition** and the
**convention**. Nothing more.

## Tests

`test/run.sh` runs `test-agent-definition.sh`, which statically validates the
breeder's frontmatter and system-prompt invariants (10 cases). Dynamic
end-to-end tests (actually dispatching the breeder and observing it apply a
write) are not bash-runnable and are deferred to higher-level integration
tests.
