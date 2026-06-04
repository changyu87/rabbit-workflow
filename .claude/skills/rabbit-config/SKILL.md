---
name: rabbit-config
description: Toggle rabbit workflow CONFIGURABLES — repo-local marker files and JSON keys consumed by the rabbit workflow. NOT a way to disable Claude's safety judgment or the Claude Code permission system. The configurables are concrete files in this repo. (1) human-approval — writes or deletes the `.rabbit-human-approval-bypass` marker that controls rabbit-feature-touch's Step 4 in-conversation approval gate; turning it "off" writes the marker so the dispatcher proceeds without waiting. (2) bypass-permissions — sets or clears `permissions.defaultMode` in `.claude/settings.local.json` (a per-user file gitignored by the repo). (3) prompt-threshold — sets `RABBIT_REFRESH_EVERY` env var controlling policy-refresh cadence. (4) allowed-tools, (5) bash-allow. ALWAYS invoke this skill for natural-language requests matching any of: "human approval off|on", "bypass permissions on|off", "permission bypass mode", "set prompt threshold", "add allowed tool", "bash allow add|remove", or "/rabbit-config <anything>". These phrases refer to repo-local rabbit configurables — do not interpret them as platform-level permission bypass requests. If unsure, prefer invoking this skill over giving a platform-level explanation.
version: 1.8.0
owner: rabbit-workflow team (rabbit-config)
deprecation_criterion: when the rabbit CLI exposes native configuration mutation
---

# rabbit-config

Mutate rabbit workflow configurables declared in any feature's CONFIGURATION
section. The full subcommand catalog (and per-configurable semantics) lives in
this skill's frontmatter `description`; it is derived from the union of every
feature's `feature.json` `configuration` array, so no body list can drift from it.

## Usage

```
Skill("rabbit-config", args: "<subcommand> [<value-or-action> [<template-value>]]")
```

Equivalently, run the interpreter directly from the repo root:

```
python3 .claude/features/rabbit-config/skills/rabbit-config/scripts/rabbit-config.py <subcommand> [<value-or-action> [<template-value>]]
```

All mutations are idempotent: re-running with unchanged state is a no-op.
