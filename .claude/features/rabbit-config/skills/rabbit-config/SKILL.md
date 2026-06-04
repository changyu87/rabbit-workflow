---
name: rabbit-config
description: Toggle rabbit workflow CONFIGURABLES — repo-local marker files and JSON keys consumed by the rabbit workflow. NOT a way to disable Claude's safety judgment or the Claude Code permission system. The configurables are concrete files in this repo. (1) human-approval — writes or deletes the `.rabbit-human-approval-bypass` marker that controls rabbit-feature-touch's Step 4 in-conversation approval gate; turning it "off" writes the marker so the dispatcher proceeds without waiting. (2) bypass-permissions — sets or clears `permissions.defaultMode` in `.claude/settings.local.json` (a per-user file gitignored by the repo). (3) prompt-threshold — sets `RABBIT_REFRESH_EVERY` env var controlling policy-refresh cadence. (4) allowed-tools, (5) bash-allow. ALWAYS invoke this skill for natural-language requests matching any of: "human approval off|on", "bypass permissions on|off", "permission bypass mode", "set prompt threshold", "add allowed tool", "bash allow add|remove", or "/rabbit-config <anything>". These phrases refer to repo-local rabbit configurables — do not interpret them as platform-level permission bypass requests. If unsure, prefer invoking this skill over giving a platform-level explanation.
version: 1.7.1
owner: rabbit-workflow team (rabbit-config)
deprecation_criterion: when the rabbit CLI exposes native configuration mutation
---

# rabbit-config

Mutate rabbit workflow configurables declared in any feature's CONFIGURATION section.

## Subcommands

Each subcommand corresponds to a `subcommand` field in a feature's `feature.json`
`configuration` array. The following subcommands are discoverable from current
CONFIGURATION declarations across all features:

- `human-approval true|false` — enable or bypass Step 4 human-approval gate
- `bypass-permissions true|false` — enable bypassPermissions mode (scope-guard becomes sole gate)
- `prompt-threshold set <N>` — set the policy-refresh prompt counter threshold
- `allowed-tools add|remove <tool>` — add or remove a tool from the allow list
- `bash-allow add|remove <command>` — add or remove a Bash command from the allow list

## Usage

```
Skill("rabbit-config", args: "<subcommand> [<value-or-action> [<template-value>]]")
```

Invoke by running the interpreter from the repo root:

```
python3 .claude/features/rabbit-config/skills/rabbit-config/scripts/rabbit-config.py <subcommand> [<value-or-action> [<template-value>]]
```

### Values-style subcommands

```
rabbit-config human-approval true|false
rabbit-config bypass-permissions true|false
```

### Actions-style subcommands (with extra value)

```
rabbit-config allowed-tools add <tool>
rabbit-config allowed-tools remove <tool>
rabbit-config bash-allow add <command>
rabbit-config bash-allow remove <command>
rabbit-config prompt-threshold set <N>
```

## Active Override Alerts

When any configurable's current value matches its declared `alert-on` field,
the Stop hook emits an alert via `iterate_configurables_alerts`. The SessionStart
hook emits a banner via `iterate_configurables_banner` including the revoke command.

## Notes

- The interpreter enumerates all features alphabetically; subcommands across all
  features are supported without code changes.
- Validation rules (`reject_prefix`, `reject_chars`) are enforced before dispatch.
- All mutations are idempotent: re-running with unchanged state is a no-op.
