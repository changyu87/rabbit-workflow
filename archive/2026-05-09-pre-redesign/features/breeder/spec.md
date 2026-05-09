# rabbit-breeder

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).
> Agent definition: [`../../agents/rabbit-breeder.md`](../../agents/rabbit-breeder.md).

## Purpose

The `rabbit-breeder` is a Claude Code subagent that owns all writes to a
**dispatched scope**. The work model is unified: one breeder, one scope per
dispatch. It does not matter whether the scope is `.claude/features/<x>/`
(rabbit improving itself), `projA/features/<y>/` (a host project applying
the rabbit discipline), or any other path. Same agent semantics, different
scope.

When the caller says "improve rabbit's bug-filing feature", the dispatcher
launches `rabbit-breeder` with `SCOPE=.claude/features/bug-filing/`. When
the caller says "scaffold an auth feature in my project", the dispatcher
launches `rabbit-breeder` with `SCOPE=projA/features/auth/`. From the
breeder's perspective these are identical operations.

## How scope is enforced

Two layers:

1. **Convention** — the breeder's system prompt (see
   [`agents/rabbit-breeder.md`](../../agents/rabbit-breeder.md)) explicitly
   refuses any out-of-scope write request and emits `REJECTED: out-of-scope`.

2. **Hook** — the dispatcher (typically the main session) creates
   `<SCOPE>/.rabbit-scope-active` immediately before the `Agent` call. The
   `scope-guard` hook (defined in the `scope-guard` feature) wires
   `PreToolUse` on `Write|Edit|Bash`, walks up the target path looking for
   `.rabbit-scope-active`, and denies (`exit 2`) any tool call whose target
   has no marker-bearing ancestor. Dispatcher removes the marker after
   `Agent` returns.

Per-feature markers (locality) is what makes parallel dispatch work:
multiple breeders running concurrently on different scopes each have their
own marker in their own scope dir. Hook checks resolve independently.

**Residual gap (honest):** the hook detects "is this target inside *some*
active scope?" but not "is it inside *this specific breeder's* scope" —
Claude Code's hook input doesn't currently expose subagent identity. So a
misbehaving breeder could in theory write into another active breeder's
scope and the hook would allow it. Convention plus PR review handles that
case. When/if Anthropic exposes subagent invocation identity in hook
input, the strict version becomes a one-line lookup.

## Invocation

```
# dispatcher (main session) protocol:
touch "<SCOPE>/.rabbit-scope-active"
Agent({
  subagent_type: "rabbit-breeder",
  prompt: <structured request, see Input contract in agents/rabbit-breeder.md>
})
rm "<SCOPE>/.rabbit-scope-active"
```

The caller supplies a structured request listing `SCOPE`, `operation`,
`target`, `payload`, `tdd_context` (optional), and `reason`. The breeder
parses, validates, applies, and returns a structured `RESULT:` block.

## Validation responsibilities

After every write that touches a feature directory (any directory
containing `feature.json`), the breeder MUST run:

```
bash <repo>/.claude/features/feature-skeleton/scripts/validate-feature.sh \
  <SCOPE>
```

Non-zero exit → roll back the write or report `REJECTED: schema violation`.

After every TDD state transition, the breeder MUST run:

```
bash <repo>/.claude/features/tdd-state-machine/scripts/tdd-drift-check.sh \
  <SCOPE>
```

Drift detected → refuse to commit; reply `REJECTED: drift — <details>`.

The scripts are path-agnostic — they work for any feature dir, regardless
of where it lives.

## What is special about `.claude/`?

In the work model: nothing. The breeder treats `.claude/features/<x>/`
identically to `projA/features/<y>/`. The hook applies the same way. The
schema applies the same way. The TDD state machine applies the same way.

The only special property of `.claude/` is its **subject** — it contains
rabbit's own features, so dispatching breeder there is "rabbit improves
rabbit". Dispatching elsewhere is "rabbit helps a project". Same code path,
different content.

## What this feature does NOT define

- The scope-guard hook implementation — that is `scope-guard` (formerly
  `claude-write-lockdown`).
- The schema the breeder validates against — that is `feature-skeleton`.
- The state machine the breeder honors — that is `tdd-state-machine`.
- The bug filing format used in `add_bug` operations — that is `bug-filing`.

Bounded scope: this feature owns the **agent definition and the unified
work-model convention**. The hook plumbing lives in `scope-guard`.

## Tests

`test/run.sh` runs `test-agent-definition.sh`, which statically validates
the breeder's frontmatter and system-prompt invariants:

- Required frontmatter fields present
- Tools list includes Write/Edit/Read/Bash
- Body asserts scope-parameterized constraint (NOT `.claude/`-only)
- Body references `<SCOPE>` parameter
- Body references philosophy/work-guide
- Body references the scope-guard hook / `.rabbit-scope-active` marker
- Body references validate-feature.sh
- Body references TDD state-machine scripts
- Body references branch/PR discipline / no-merge

Dynamic dispatch tests (actually invoking the breeder and observing it
apply a write) are not bash-runnable and are deferred to harness-level
integration tests.
