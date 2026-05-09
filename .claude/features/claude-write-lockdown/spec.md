# claude-write-lockdown

> Source of truth: [`feature.json`](./feature.json).

## Purpose

Activates the `.claude/` write lockdown by adding two rules to the shared
`.claude/settings.json`:

```
"permissions": {
  "deny": [
    "Write(.claude/**)",
    "Edit(.claude/**)"
  ]
}
```

After this feature is on `main` and a session reloads settings, the `Write`
and `Edit` tools cannot target any path under `.claude/`. This is the
"hardening with json, not local but shared settings.json" the user asked for.

## Honest scope of enforcement (read this carefully)

These deny rules block the `Write` and `Edit` tools at the harness level.
They do **not** block:

- `Bash` writes (e.g. `cat > .claude/file`, `sed -i .claude/...`,
  `jq ... > .claude/...`). `Bash` is not path-restricted in `permissions`.
- Subagents using `Write`/`Edit` — the parent's deny rules apply to all
  subagents, including the `breeder`, so the breeder also cannot use
  these tools on `.claude/**`.

The intended workflow:

1. Main session and most subagents receive a hard `REJECTED` from the
   harness if they attempt `Write` or `Edit` on `.claude/**`. This catches
   accidental writes early.
2. The `breeder` subagent (and any other agent that needs to write inside
   `.claude/`) uses `Bash` heredocs / `sed` / `jq` for the actual write.
3. Code review on every PR verifies that `.claude/**` changes are
   appropriate — this is the human/AI-review backstop for intentional
   misuse via `Bash`.

This hybrid (tool-level deny + convention + review) is deliberate and
honest. A full per-subagent path lockdown is not currently expressible in
Claude Code; when it becomes expressible, this feature's deprecation
criterion is met and we migrate.

## Why this is the LAST feature in the build

Every feature in this overnight build needed to write `.claude/<feature>/...`.
If lockdown was applied first, none of the others could have been authored
through the normal `Write` tool. By landing this feature LAST, the build
remains incremental and reviewable. After this PR merges, all future
`.claude/` writes either:

- Use `Bash` (as the `breeder` is designed to), or
- Are dispatched to the `breeder` subagent which performs the `Bash`
  writes on the caller's behalf.

## Optional supervisory hook (not in this PR)

A future feature may add a `PreToolUse` hook on `Bash` that detects when a
bash command writes to `.claude/**` and emits a `systemMessage` warning
naming the path. This adds an audit signal for `Bash`-level writes without
blocking them. Not shipped in v1.0; out of scope.

## What this feature does NOT define

- The `breeder` subagent itself — that is the `breeder` feature.
- The `bug-handler` subagent — that is `bug-handler`.
- The validator that checks feature-schema conformance — that is
  `feature-skeleton`.
- The hard rules (branch-per-feature, opus-for-planning, tests-non-interactive)
  — that is `hard-rules`.

Bounded scope: this feature owns the **deny rules** and a single **detective
script** (`check-lockdown-active.sh`) to verify they are present.

## Tests

`test/run.sh` runs `test-lockdown-active.sh` (7 cases):

- t1: settings with both deny rules → ok
- t2: settings missing Edit deny → fails (and names Edit)
- t3: settings with no permissions field → fails
- t4: missing settings file → invocation error
- t5: malformed JSON → invocation error
- t6: extra unrelated deny rules tolerated
- t7: shared `.claude/settings.json` (after this PR) has the rules
