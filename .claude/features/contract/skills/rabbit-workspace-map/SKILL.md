---
name: rabbit-workspace-map
description: Use when the user asks to see, inspect, understand, or audit the rabbit-workflow workspace layout — the structural hierarchy of rabbit root and user project roots, based on workspace-structure.json declarations. Trigger phrases include "show the workspace map", "workspace overview", "workspace structure", "audit the workspace", "check workspace conformance", "what's out of contract", or any question requiring workspace hierarchy. Use --human when the user wants a readable terminal view; --audit when checking conformance; default JSON output for machine/programmatic use.
---

# rabbit-workspace-map skill

Execute `.claude/features/contract/scripts/workspace-map.sh` immediately on invocation. Do not describe it, do not paraphrase its output — run it.

## Action

Run one of the following, based on what the user wants:

- User wants to **see** the map (human-readable):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --human
  ```

- User wants to **process** the map (JSON for machine/programmatic use):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh
  ```

- User wants to **audit** conformance (human-readable findings):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --audit --human
  ```

- User wants to **audit** conformance (machine-oriented findings):

  ```bash
  .claude/features/contract/scripts/workspace-map.sh --audit
  ```

The default JSON output conforms to `.claude/features/contract/schemas/workspace-map.json.schema.json` (v2.0.0) with a `roots` array. Audit mode emits a `findings` array of deviations.

## Mode Selection

| User signal | Command |
|-------------|---------|
| "show me", "what's in the workspace", "workspace overview", "workspace structure" | `--human` |
| "give me JSON", "pipe to jq", "filter ... where", chained tooling | default JSON (omit `--human`) |
| "audit", "check conformance", "what's out of contract" (human) | `--audit --human` |
| "audit", "check conformance", "what's out of contract" (machine) | `--audit` |

If unsure between show and audit, prefer `--human` for overviews, `--audit` for correctness checks.

## Do Not

- Do not re-implement the workspace walk inline (no ad-hoc `find` / `ls` loops). Always invoke `workspace-map.sh`.
- Do not call `.claude/skills/rabbit-workspace-map/...` as a script — that path holds only this SKILL.md. The executable lives under `.claude/features/contract/scripts/`.
- Do not dump raw JSON to a user who asked to *see* the map; use `--human`.
- Do not run `--audit` when the user asked for an overview; do not omit `--audit` when the user asked for conformance checking.
