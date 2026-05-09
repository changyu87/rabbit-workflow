# bug-handler

> Source of truth: [`feature.json`](./feature.json).
> Agent definition: [`../../agents/bug-handler.md`](../../agents/bug-handler.md).

## Purpose

Read-only triage subagent for bugs. Reads a bug filed at
`.claude/docs/bugs/<bug-name>/`, classifies it, and emits a structured
`TRIAGE:` block. **Never writes anything.** All resulting actions
(transitioning the bug, filing follow-up bugs, adding tests) are dispatched
separately by the caller — typically routed through the `breeder` for
`.claude/` writes or through the relevant feature owner for test additions.

## Why a separate agent (bounded scope rationale)

Triage and action are orthogonal concerns:

- **Triage** asks: what is this? Is it valid? Is it covered by any test?
  Who owns the affected code?
- **Action** asks: do we close it? Do we file a follow-up? Do we add a test?

Bundling these creates the same bias as a judge who is also the executioner.
The user's request explicitly suggests a dedicated bug handler subagent and
notes that the bounded-scope philosophy supports the split. This feature
implements that split.

## Classifications

| Classification | Meaning                                                                |
|----------------|------------------------------------------------------------------------|
| `new`          | Genuine, unique bug; needs a fix.                                      |
| `known`        | Duplicate of an existing open bug; recommend close-as-duplicate.       |
| `invalid`      | Not a bug (misunderstanding, env issue, by design); recommend close.   |
| `test-gap`     | Reveals missing test coverage in the related feature; needs test work. |

A bug may be `new` AND `test-gap` simultaneously. Both must be reflected in
`evidence:` and the recommended handoff should include adding the test.

## Output contract — `TRIAGE:` block

```
TRIAGE:
  bug_name:           <name>
  current_status:     <open|closed|reopened>
  related_feature:    <name | null>
  classification:     <new | known | invalid | test-gap>
  severity_assessed:  <low | medium | high | critical>
  evidence:           |
                      <multi-line evidence>
  recommended_action: <keep_open | close_invalid | close_duplicate | route_to_feature_owner | escalate>
  recommended_test:   <test name when test-gap, else null>
  proposed_handoff:   <e.g. "dispatch breeder to file follow-up bug X" or
                       "dispatch feature owner of <feature> to add test Y" or
                       "no handoff: caller closes bug">
```

This is a fixed-format machine-first block. Surrounding prose is
informational only; the block above is the source of truth and what
downstream automation parses.

## Invocation

```
Agent({
  subagent_type: "bug-handler",
  prompt: "Triage bug <bug-name>. Bug dir: .claude/docs/bugs/<bug-name>/."
})
```

The bug-handler reads everything it needs via Read/Bash/Glob/Grep. The
caller does not need to pre-supply context other than the bug name.

## Test-gap routing

When a bug is classified `test-gap`, the recommended handoff names the
feature owner and the proposed test. The actual test addition is performed
by the feature owner's domain (often via `breeder` writing into
`.claude/features/<feature>/test/`). The `bug-handler` does not write the
test; it routes.

This satisfies the user's request: "If the bug caught a feature bug that
test not covered, hand over to that feature's owner to reflect and
add/enhance test."

## What this feature does NOT define

- The bug schema or the bug-filing operations — that is `bug-filing`.
- The mechanics of writing into `.claude/` — that is `breeder`.
- TDD step gating — that is `tdd-state-machine`.

Bounded scope: this feature owns **triage and routing**. Nothing more.

## Tests

`test/run.sh` runs `test-agent-definition.sh` (12 cases), validating the
agent file's structure and key invariants:

- name, description, tools list (Read/Bash/Glob/Grep)
- explicit absence of Write/Edit (read-only enforcement)
- body covers triage role, references bug-filing scripts, specifies TRIAGE
  format, refuses to write, addresses test-gap, references philosophy /
  work-guide.

Dynamic dispatch tests (actually invoking the agent) are deferred to
harness-level integration tests; bash-level tests cannot exercise the
Agent tool.
