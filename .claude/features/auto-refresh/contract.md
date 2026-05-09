# Contract — auto-refresh

## Reads

- `CLAUDE.md` — parses lines beginning with `@` to identify policy files.
- Each file referenced by a `CLAUDE.md` `@`-import (typically
  `.claude/philosophy.md` and `.claude/work-guide.md`).
- `.rbt-prompt-counter` — current count.
- `RBT_REFRESH_EVERY` (env, default 20) — threshold.

## Writes

- `.rbt-prompt-counter` — integer, incremented or reset.

## Invokes

- `python3` — for emitting the JSON payload.
- Standard utilities: `grep`, `sed`, `cat`, `tr`, `mktemp`.

## Inputs / Outputs

### Hook input (from Claude Code, on UserPromptSubmit)

JSON on stdin. The hook does not parse it (the trigger is the only signal
needed; the hook reads its own state from disk).

### Hook output

- **Below threshold:** silent (empty stdout, exit 0).
- **At threshold:** single-line JSON to stdout:
  ```
  {
    "additionalContext": "Periodic policy refresh ... <file bodies> ...",
    "systemMessage": "[rwf] Policy refreshed — <file list>"
  }
  ```
- Exit code: always 0 (no errors are signaled to the harness; failure to
  read a referenced file is silently skipped).

## Cross-scope handoff

- **Adjusting threshold:** use the `/rabbit-set-threshold N` command, NOT
  manual `settings.local.json` edits (the command validates the input).
- **Changing what's re-injected:** edit `CLAUDE.md` to add/remove
  `@`-imports. The hook re-reads `CLAUDE.md` on every threshold hit, so
  changes are picked up without restart.
- **Disabling:** remove the `UserPromptSubmit` hook from
  `.claude/settings.json`, OR set `RBT_REFRESH_EVERY` to a very high
  value (e.g. `999999`).

## Versioning

- Current version: `1.0.0`.
- Changing the JSON output shape is breaking (Claude Code's hook protocol
  consumes specific keys). Bump major.
- Adding a new env var (e.g. `RBT_REFRESH_PROMPT`) is non-breaking.
- Renaming `.rbt-prompt-counter` is breaking (callers that read it will
  break); already done twice in this codebase's history
  (`.rwf-counter` → `.rwf-prompt-counter` → `.rbt-prompt-counter`),
  documented in the historical hierarchy and naming-convention plans.
