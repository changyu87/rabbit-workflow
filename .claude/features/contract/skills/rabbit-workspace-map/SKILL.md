---
name: rabbit-workspace-map
description: Use when the user asks to see, inspect, or understand the rabbit-workflow workspace layout — the features, scripts, schemas, commands, skills, hooks, and project directories under .claude/. Trigger phrases include "show the workspace map", "what features exist", "list all rabbit components", "give me a workspace overview", or any question that requires enumerating workspace structure. Use the --human flag when the user wants a readable terminal view; default JSON output otherwise.
---

# rabbit-workspace-map skill

Execute `.claude/features/contract/scripts/workspace-map.sh` immediately on invocation. Do not describe it, do not paraphrase its output — run it.

## Action

Run one of the following, based on what the user wants:

- User wants to **see** the map (read it themselves) — execute with `--human`:

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --human
  ```

- User wants to **process** the map (pipe into jq, filter programmatically) — execute with default JSON (omit `--human`):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh
  ```

The default JSON output conforms to `.claude/features/contract/schemas/workspace-map.json.schema.json` and covers `features`, `scripts`, `schemas`, `commands`, `skills`, `hooks`, and user project directories.

## Mode Selection

| User signal | Mode |
|-------------|------|
| "show me", "what features", "give me an overview", "list" | `--human` |
| "filter ... where", "give me JSON", "pipe to jq", chained tooling | default JSON |

If unsure, prefer `--human` — it is the readable form.

## Do Not

- Do not re-implement the workspace walk inline (no ad-hoc `find` / `ls` loops). Always invoke `workspace-map.sh`.
- Do not call `.claude/skills/rabbit-workspace-map/...` as a script — that path holds only this SKILL.md. The executable lives under `.claude/features/contract/scripts/`.
- Do not dump raw JSON to a user who asked to *see* the map; use `--human`.
