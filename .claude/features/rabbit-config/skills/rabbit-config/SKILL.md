---
name: rabbit-config
description: Mutate rabbit workflow configurables. Use when the user wants to change human approval, bypass permissions, prompt threshold, allowed tools, or bash allow settings — phrases like "human approval off", "bypass permissions on", "set prompt threshold", "add allowed tool", "bash allow", "permissions lock", or any configuration change to the rabbit workflow.
version: 1.0.0
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
- `prompt-threshold <N>` — set the policy-refresh prompt counter threshold
- `allowed-tools add|remove <tool>` — add or remove a tool from the allow list
- `bash-allow add|remove <command>` — add or remove a Bash command from the allow list
- `permissions lock|unlock` — lock or unlock repo file permissions via repo-permissions.py

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

### Actions-style subcommands (no extra value)

```
rabbit-config permissions lock
rabbit-config permissions unlock
```

### Actions-style subcommands (with extra value)

```
rabbit-config allowed-tools add <tool>
rabbit-config allowed-tools remove <tool>
rabbit-config bash-allow add <command>
rabbit-config bash-allow remove <command>
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
