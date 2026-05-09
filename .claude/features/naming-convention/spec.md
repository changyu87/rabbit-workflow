# naming-convention

> Source of truth: [`feature.json`](./feature.json).

## Purpose

Hardens the project's naming scheme:

- **User-facing artifacts** (slash commands, skills, subagents) MUST start
  with `rabbit-`. These are what end users see and invoke; consistency
  helps recognition.
- **Internal artifacts** (hook scripts, env vars, runtime state files)
  use the short prefix `rbt-`. Same lineage, less screen real estate where
  no user is reading.
- **The legacy `rwf-` prefix is banned** anywhere under `.claude/` except
  inside `.claude/docs/` (historical specs/plans that record what was true
  at the time and should not be retroactively edited).

## What is "user-facing"

| Artifact kind | Where it lives                       | Prefix    |
|---------------|--------------------------------------|-----------|
| Slash command | `.claude/commands/<name>.md`         | `rabbit-` |
| Subagent      | `.claude/agents/<name>.md`           | `rabbit-` |
| Skill         | `.claude/skills/<name>/`             | `rabbit-` |
| Hook script   | `.claude/hooks/<name>.sh`            | `rbt-`    |
| Env var       | (read by hooks, set in settings)     | `RBT_*`   |
| Runtime file  | `.rbt-*` at repo root                | `.rbt-`   |

The `rabbit-` artifacts surface in Claude Code's UI and the user's typed
input (`/rabbit-refresh`). The `rbt-` artifacts are wires under the hood.

## Renames performed by this PR

| Old                                      | New                                       |
|------------------------------------------|-------------------------------------------|
| `.claude/commands/rwf-refresh.md`        | `.claude/commands/rabbit-refresh.md`      |
| `.claude/commands/rwf-set-threshold.md`  | `.claude/commands/rabbit-set-threshold.md`|
| `.claude/hooks/rwf-refresh.sh`           | `.claude/hooks/rbt-refresh.sh`            |
| `RWF_REFRESH_EVERY` (env var)            | `RBT_REFRESH_EVERY`                       |
| `.rwf-prompt-counter` (state file)       | `.rbt-prompt-counter`                     |

Direct callers updated: `.claude/settings.json`, `.gitignore`, `install.sh`,
`test/test-install.sh`, `README.md`, and the renamed command files'
self-references.

Historical specs/plans under `.claude/docs/` are intentionally left
untouched — they record the past truthfully.

## Validator

`scripts/check-naming.sh [root]`

Two checks in one pass:

1. Every file in `<root>/.claude/commands/`, `<root>/.claude/agents/`, and
   every directory in `<root>/.claude/skills/` MUST have a basename
   starting with `rabbit-`. (`README.md` and `CHANGELOG.md` ignored.)
2. NO file under `<root>/.claude/` (excluding `<root>/.claude/docs/`)
   may have a basename starting with `rwf-`.

Each violating file is reported once (deduped). Exit codes:

| Exit | Meaning                                |
|------|----------------------------------------|
| 0    | All conformant (or no `.claude` tree)  |
| 1    | One or more violations (named on stderr) |
| 2    | Bad invocation (not a directory)       |

## Why two prefixes (rabbit- and rbt-) instead of one

Brevity in the wires. `RABBIT_REFRESH_EVERY` and `.rabbit-prompt-counter`
are 4–5 characters longer per use, which adds up in shell scripts, JSON
config, and command lines. Users never see those names. The `rabbit-` form
is reserved for places where humans actually read it.

## What this feature does NOT define

- **The semantic content** of any command/agent/skill — only the name shape.
- **The lockdown rules** in `settings.json` — that is `claude-write-lockdown`.
- **The hard rules in work-guide.md** — that is `hard-rules`.
- **Renames inside unmerged PRs** (#5 breeder, #7 bug-handler) — those
  branches are amended separately to use `rabbit-breeder` / `rabbit-bug-handler`.

Bounded scope: this feature owns **the naming rule and its detective check**.

## Tests

`test/run.sh` runs `test-check-naming.sh` (14 cases):

- t1–t9: empty tree, all-rabbit, rwf- command, nude command/agent/skill, mix,
  no `.claude` dir, README.md ignored.
- t10: violation count line correct after dedupe.
- t11: this very repo passes (post-rename self-check).
- t12: `rwf-` hook script flagged.
- t13: `rbt-` hook script accepted (internal naming).
- t14: `rwf-` inside `docs/` tolerated (historical).
