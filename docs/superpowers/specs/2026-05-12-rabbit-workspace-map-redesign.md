# rabbit-workspace-map Redesign

**Date:** 2026-05-12
**Owner:** rabbit-workflow team
**Status:** approved

---

## Problem Statement

The current `rabbit-workspace-map` skill calls `workspace-map.sh`, which performs an ad-hoc
filesystem walk to enumerate features, scripts, schemas, commands, skills, hooks, and user
project directories. The output is a flat inventory — not a structural hierarchy — and the
expected folder structure is hardcoded in the script rather than declared in a contract.
The result is a system that discovers structure rather than enforcing it: unknown directories
are invisible, deviations are undetected, and there is no authoritative declaration of what
the workspace *should* look like.

---

## Goals

- Replace ad-hoc discovery with a contract-driven hierarchy map
- Declare workspace structure as a hard contract at each project root
- Surface unknown filesystem entries (not in contract) as annotated alerts
- Support two operational modes: show (default) and audit
- Machine-first output by default; human-readable via `--human` flag
- Preserve the `backlog` legacy subcommand unchanged

---

## Contract Architecture

### Schema (rabbit-owned)

**Location:** `.claude/features/contract/schemas/workspace-structure.json`

Defines the shape every `workspace-structure.json` declaration must follow. A declaration
is a recursive node tree. Each node:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Directory name |
| `required` | boolean | yes | Whether absence is a contract violation |
| `description` | string | yes | Human-readable annotation |
| `children` | array | yes | Child nodes (same structure, recursive) |

Top-level declaration fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string (semver) | yes | Schema version |
| `owner` | string | yes | Owner of this declaration |
| `root` | string | yes | Tag identifying this root (e.g. `"rabbit"`, `"my-project"`) |
| `nodes` | array | yes | Top-level node declarations |

`additionalProperties: false` at all levels.

### Declaration Files

| Level | File location |
|---|---|
| Rabbit's own structural declaration | `.claude/workspace-structure.json` |
| User project declaration | `<project-root>/workspace-structure.json` |

The meta-contract rule: every project root recognized by the workspace map must have a
`workspace-structure.json` at its top level conforming to the schema. User project roots
are all non-hidden top-level directories at the repo root.

### Example Declaration Fragment

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "root": "rabbit",
  "nodes": [
    {
      "name": "features",
      "required": true,
      "description": "all feature source directories",
      "children": [
        { "name": "contract",   "required": true,  "description": "cross-feature schemas and dispatch", "children": [] },
        { "name": "policy",     "required": true,  "description": "canonical rule docs", "children": [] },
        { "name": "rabbit-cage","required": true,  "description": "Claude Code surface owner", "children": [] },
        { "name": "skills",     "required": false, "description": "skill library", "children": [] },
        { "name": "agents",     "required": false, "description": "agent definitions", "children": [] }
      ]
    },
    { "name": "skills",   "required": false, "description": "skill library", "children": [] },
    { "name": "hooks",    "required": false, "description": "hook scripts", "children": [] },
    { "name": "commands", "required": false, "description": "slash commands", "children": [] }
  ]
}
```

---

## Script: `workspace-map.sh`

**Location:** `.claude/features/contract/scripts/workspace-map.sh` (replaces current)

### Interface

```
workspace-map.sh [--human] [--audit] [--repo-root <path>]
workspace-map.sh backlog <feature-name> [--repo-root <path>]   # legacy, unchanged
```

| Flag | Purpose |
|---|---|
| `--human` | Human-readable terminal output (default: JSON) |
| `--audit` | Audit mode: output deviations only (default: show mode) |
| `--repo-root <path>` | Override repo root resolution (test seam; preferred over mutating `$RABBIT_ROOT`) |

Root resolution order: `--repo-root` arg → `$RABBIT_ROOT` env var → `git rev-parse --show-toplevel`.

### Show Mode (default)

1. Load `.claude/workspace-structure.json` — validate against schema
2. For each top-level dir at repo root whose name does not start with `.`, check for `<dir>/workspace-structure.json`
3. Walk each declaration against the filesystem:
   - Declared nodes → tagged `present` or `missing`
   - Filesystem entries not in any declaration → tagged `unknown` (alert)
4. Emit unified hierarchy (rabbit root + each user project root)

### Audit Mode (`--audit`)

1. Same loading and walk as show mode
2. Emits **only** deviations: missing required nodes and unknown filesystem entries
3. JSON: array of finding objects
4. Human: flat list of flagged paths with severity prefix

### Output Schema (v2.0.0)

**Show mode JSON:**
```json
{
  "schemaVersion": "2.0.0",
  "repoRoot": "/abs/path",
  "roots": [
    {
      "root": "rabbit",
      "path": ".claude",
      "declaration": "found",
      "nodes": [
        { "name": "features", "required": true,  "status": "present",  "children": [...] },
        { "name": "my_docs",  "required": null,  "status": "unknown",  "children": [] }
      ]
    },
    {
      "root": "my-project",
      "path": "my-project",
      "declaration": "missing",
      "nodes": []
    }
  ]
}
```

`required: null` means the node is not in the contract (unknown). `required: false` means
declared optional. These are distinct states.

`declaration: "found"` means a `workspace-structure.json` was located and loaded for this
root. `declaration: "missing"` means no declaration file was found; nodes will be empty
and an audit finding of type `missing_declaration` is emitted.

**Audit mode JSON:**
```json
{
  "schemaVersion": "2.0.0",
  "findings": [
    { "severity": "error", "type": "missing_required", "path": ".claude/features/policy", "root": "rabbit" },
    { "severity": "warn",  "type": "unknown",          "path": ".claude/my_docs",          "root": "rabbit" },
    { "severity": "warn",  "type": "missing_declaration", "path": "my-project",            "root": "my-project" }
  ]
}
```

---

## Skill: `rabbit-workspace-map` SKILL.md

The skill remains a thin wrapper — mode/format selection and script invocation only.

**Updated description:** triggers on workspace structure, hierarchy, conformance, and audit
phrases for both rabbit root and user project roots.

**Mode selection:**

| User signal | Command |
|---|---|
| see / overview / structure (human) | `workspace-map.sh --human` |
| see / overview / structure (machine) | `workspace-map.sh` |
| audit / conformance / deviations (human) | `workspace-map.sh --audit --human` |
| audit / conformance / deviations (machine) | `workspace-map.sh --audit` |

**Do-not rules:**
- Never re-implement the walk inline
- Never dump raw JSON to a user who asked to *see*
- Never run audit mode when the user asked for an overview (and vice versa)

---

## Migration

### Breaking Changes

Output schema bumps `1.0.0` → `2.0.0`. The flat `features`, `scripts`, `schemas`,
`commands`, `skills`, `hooks`, `userProjectDirs` arrays are removed. Consumers that
parse JSON output must switch to `roots[].nodes` traversal.

### Known Consumers

- `rabbit-bug` tests referencing `workspace-map.sh` — audit and update during implementation
- `rabbit-backlog` tests referencing `workspace-map.sh` — audit and update during implementation
- `backlog` subcommand callers — **no change required** (subcommand preserved verbatim)

### New Artifacts

| Artifact | Action |
|---|---|
| `.claude/features/contract/schemas/workspace-structure.json` | Create (node-tree schema) |
| `.claude/features/contract/schemas/workspace-map.json.schema.json` | Update to v2.0.0 output schema |
| `.claude/workspace-structure.json` | Create (rabbit's own declaration) |
| `.claude/features/contract/scripts/workspace-map.sh` | Rewrite |
| `.claude/skills/rabbit-workspace-map/SKILL.md` | Update |

User project declarations (e.g. `my-project/workspace-structure.json`) are created by
each project's owners — not by this implementation.

---

## Non-Goals

- This implementation does not create `workspace-structure.json` files for user projects
- This implementation does not validate the *content* of `workspace-structure.json` beyond
  schema conformance (e.g. it does not check that declared paths are meaningful)
- The skill does not expose `--repo-root` to users — it is a test seam only
