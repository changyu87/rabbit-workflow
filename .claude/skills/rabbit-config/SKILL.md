---
name: rabbit-config
description: Use to configure rabbit-workflow settings via /rabbit-config. Subcommands - help (illustrated usage with examples for every subcommand), prompt-threshold [N] (refresh threshold), allowed-tools [add|remove <tool>] (Claude Code tool permissions), bash-allow [add|remove <cmd>] (Bash command permissions), permissions [lock|unlock] (repo file write protection), human-approval [true|false] (Step 4 gate state, hard file marker; true=gate active, false=bypass), bypass-permissions [true|false] (per-user permissions.defaultMode='bypassPermissions' in settings.local.json). Trigger on phrases like "change prompt threshold", "add permission", "bypass human approval", "revoke human-approval bypass", "enable bypass mode", "turn off bypass permissions", "what subcommands does rabbit-config have", "rabbit-config help".
version: 1.0.0
owner: rabbit-cage
deprecation_criterion: when Claude Code provides a native typed-config mechanism that subsumes this skill
---

## Overview

`/rabbit-config` is the extensible configuration entry point for the rabbit
workflow. The dispatcher invokes this skill whenever the user asks to read or
change one of the workflow's runtime knobs.

All logic lives in `.claude/features/rabbit-cage/skills/rabbit-config/scripts/rabbit-config.py`. There is no slash-command
shim file (per spec Inv 20); the skill itself is the sole entry point.

## Discovering Subcommands

The canonical discovery path is `/rabbit-config help` — it prints an
illustrated usage message that names every subcommand and shows at least one
concrete invocation example per subcommand. Operators new to the skill should
run it once before reaching for the spec or this file.

## CLI Surface

```
/rabbit-config help
    help                           print illustrated usage with examples for every subcommand

/rabbit-config prompt-threshold [value]
    prompt-threshold <N>           set auto-refresh threshold to N (positive integer)
    prompt-threshold               remove threshold override, restoring default

/rabbit-config allowed-tools [add|remove <tool>]
    allowed-tools add <tool>       add <tool> to permissions.allow in settings.local.json
    allowed-tools remove <tool>    remove <tool> from permissions.allow
    allowed-tools                  list current entries (excluding Bash(...) entries managed by bash-allow)

/rabbit-config bash-allow [add|remove <command>]
    bash-allow add <command>       add Bash(<command>:*) to permissions.allow in settings.local.json
    bash-allow remove <command>    remove Bash(<command>:*) from permissions.allow
    bash-allow                     list current bash-allow commands (inner names)

/rabbit-config permissions lock|unlock
    lock     remove owner write permission from archive/ and test/ (run after git clone)
    unlock   restore owner write permission to archive/ and test/ (run before editing)

/rabbit-config human-approval [true|false]
    human-approval false           write .rabbit-human-approval-bypass marker (bypass Step 4)
    human-approval true            remove the marker (Step 4 gate active — default posture)
    human-approval                 print current gate state to stdout: 'true' (active) or 'false' (bypassed)

/rabbit-config bypass-permissions [true|false]
    bypass-permissions true        set permissions.defaultMode='bypassPermissions' in .claude/settings.local.json (per-user opt-in)
    bypass-permissions false       remove permissions.defaultMode from .claude/settings.local.json
    bypass-permissions             print current state to stdout: 'true' if defaultMode='bypassPermissions' in settings.local.json, else 'false'
```

## bypass-permissions Contract

Bypass mode is a per-user preference. The shared `.claude/settings.json` MUST
NOT declare `permissions.defaultMode`; operators opt in individually by writing
`permissions.defaultMode = "bypassPermissions"` to their own gitignored
`.claude/settings.local.json` via this subcommand. When set, Claude Code skips
its native per-write permission prompts so the scope-guard PreToolUse hook
becomes the single decision point for write authorization.

`true` and `false` are both idempotent: re-invoking when the key already
matches is a no-op (exit 0) and does NOT rewrite the file. The no-action form
prints exactly one line (`true` or `false`) reflecting the current value in
`settings.local.json`. Takes effect on next session start.

## human-approval Marker Contract

`.rabbit-human-approval-bypass` is a hard file marker at the repo root,
gitignored, never committed. The boolean value follows contract Inv 11
(boolean CLI values use `true`/`false`): `true` = gate active (marker absent,
default), `false` = gate bypassed (marker present). When the marker is
present, `rabbit-feature-touch` dispatchers pass `--human-approval-gate false`
to `dispatch-tdd-subagent.py` and Step 4 is skipped for every subsequent
dispatch until the marker is removed.

The marker persists across sessions. It is state, not conversation memory.
`sync-check.py` emits a red `[rabbit]` `systemMessage` on every Stop event
while the marker is present so the bypass cannot be silently forgotten.

Revoke explicitly with `/rabbit-config human-approval true` or manual delete.

## When to Invoke

- "set prompt threshold to 30", "lower the refresh threshold", "restore default"
- "allow WebFetch", "remove Edit from permissions", "list allowed tools"
- "let bash run touch", "remove cat from bash-allow"
- "lock the repo", "unlock archive/ and test/"
- "bypass human approval", "skip Step 4 this session", "revoke the bypass",
  "re-enable the gate", "what's the human-approval state?"
- "enable bypass mode", "turn off bypass permissions", "skip native write
  prompts", "what's my bypass-permissions state?"

## Enabling Bypass Mode and Suppressing the Startup Warning (user-local)

Bypass mode (`permissions.defaultMode = "bypassPermissions"`) is per-user.
The shared `settings.json` MUST NOT declare it. To opt in, run:

```
/rabbit-config bypass-permissions true
```

This writes the key to your gitignored `.claude/settings.local.json` and tells
Claude Code to skip its native per-write permission prompts so the scope-guard
hook is the single decision point for write authorization.

Claude Code surfaces a one-time startup warning about bypass mode. Suppress
the warning per-user by adding `skipDangerousModePermissionPrompt` to your
`.claude/settings.local.json` (this knob is still set manually; it is not
managed by `/rabbit-config`):

```json
{
  "permissions": {
    "skipDangerousModePermissionPrompt": true
  }
}
```

Both keys live in `settings.local.json` (user-local, gitignored), never in
the team-wide `settings.json`. Different operators may prefer different
behavior.

## Red Flags — STOP

- Editing `.claude/settings.json` directly → wrong file. Use `settings.local.json`
  via this skill; `settings.json` is build-managed and gets overwritten.
- Hand-editing `.rabbit-human-approval-bypass` → use the subcommand so the
  confirmation is logged.
