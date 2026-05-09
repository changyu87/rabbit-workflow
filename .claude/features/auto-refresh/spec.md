# auto-refresh

> Source of truth: [`feature.json`](./feature.json).
> Implementation files (NOT in this directory):
> - Hook: [`../../hooks/rbt-refresh.sh`](../../hooks/rbt-refresh.sh)
> - Wired in: [`../../settings.json`](../../settings.json) (UserPromptSubmit + SessionStart hooks)
> - User command: [`../../commands/rabbit-set-threshold.md`](../../commands/rabbit-set-threshold.md)
> - Manual trigger command: [`../../commands/rabbit-refresh.md`](../../commands/rabbit-refresh.md)

## Purpose

Periodically re-inject the rabbit workflow's policy files (everything
`CLAUDE.md` `@`-imports — typically `philosophy.md` and `work-guide.md`)
into the active Claude Code session's context. Defends against silent
drift, where the policy gradually fades out of attention over many turns.

This feature is a **documentation overlay** over the existing implementation.
The implementation files predate the `.claude/features/<name>/` schema and
live at their historical paths (referenced above). This feature directory
adds the schema-required artifacts (`feature.json`, `spec.md`, `contract.md`,
`test/`) so the capability is on equal footing with new features.

## Mechanism

```
UserPromptSubmit hook → rbt-refresh.sh
  ├── increment .rbt-prompt-counter
  ├── if count < $RBT_REFRESH_EVERY: silent exit 0
  └── if count >= $RBT_REFRESH_EVERY:
        ├── reset counter to 0
        ├── parse @-imports from CLAUDE.md
        ├── concatenate file bodies into a payload
        └── emit JSON { additionalContext, systemMessage } to stdout
```

`SessionStart` hook resets the counter to 0 on `startup|resume|clear|compact`.

## Configuration

`RBT_REFRESH_EVERY` (env var, default `20`):

- Set globally in `.claude/settings.json` (committed default).
- User override in `.claude/settings.local.json` (gitignored).
- The `/rabbit-set-threshold N` slash command writes the user override.

A lower value (e.g. `5`) gives tighter policy adherence at the cost of
context-window churn. A higher value (`50+`) is more permissive and saves
tokens. `20` is the team default.

## State files

- `.rbt-prompt-counter` — single integer, incremented per prompt, reset on
  threshold or session start. Gitignored.

## What this feature does NOT define

- The content of `philosophy.md` / `work-guide.md` — that is
  `policy-enforcement` (separate feature).
- The install mechanism that places the hook into a user's workspace —
  that is `install-distribute`.
- The command files (`rwf-refresh.md`, `rwf-set-threshold.md`) themselves —
  they predate the feature schema. Future PRs may move them into
  `.claude/features/auto-refresh/commands/` if desired; for now they remain
  at their historical paths and this feature documents them.

## Tests

`test/run.sh` (6 cases) drives the hook against fixture workspaces
(temporary directory containing a stub `CLAUDE.md`, philosophy/work-guide
fixtures, and a counter file). Hook is copied into the fixture so its
self-computed `REPO_ROOT` resolves into the fixture, isolating it from the
real repo.

Cases:
- t1: source hook exists and is executable
- t2: under threshold → silent
- t3: at threshold → JSON with `additionalContext` containing fixture body
- t4: missing counter file is initialized
- t5: `RBT_REFRESH_EVERY=1` refreshes every call
- t6: `systemMessage` announces refresh
