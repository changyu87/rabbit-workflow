---
feature: contract
version: 1.5.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native workflow contract mechanism that supersedes this feature's template, schema, and dispatch responsibilities
status: active
---

# contract — Spec

## Purpose

Owns all cross-feature templates, schemas, dispatch scripts, and enforcement scripts; provides but never directly modifies other features.

## Surface

**templates/**
- `.claude/features/contract/templates/spec-template.md`
- `.claude/features/contract/templates/contract-template.md`
- `.claude/features/contract/templates/bug-template.json`
- `.claude/features/contract/templates/triage-template.md`
- `.claude/features/contract/templates/feature-json-template.json`
- `.claude/features/contract/templates/subagent-launch-template.txt`
- `.claude/features/contract/templates/project-map-template.json`
- `.claude/features/contract/templates/registry-template.json`
- `.claude/features/contract/templates/skill-template.md`
- `.claude/features/contract/templates/command-template.md`

**schemas/**
- `.claude/features/contract/schemas/feature.json.schema.json`
- `.claude/features/contract/schemas/registry.json.schema.json`
- `.claude/features/contract/schemas/bug.json.schema.json`
- `.claude/features/contract/schemas/project-map.json.schema.json`
- `.claude/features/contract/schemas/rabbit-print.schema.json`
- `.claude/features/contract/schemas/workspace-map.json.schema.json`
- `.claude/features/contract/schemas/build-contract.schema.json`
- `.claude/features/contract/schemas/workspace-structure.json`

**data/**
- `.claude/features/contract/build-contract.json`

**declarations/**
- `.claude/workspace-structure.json`

**scripts/**
- `.claude/features/contract/scripts/policy-block.sh`
- `.claude/features/contract/scripts/dispatch-feature-edit.sh`
- `.claude/features/contract/scripts/rebuild-registry.sh`
- `.claude/features/contract/scripts/render-template.sh`
- `.claude/features/contract/scripts/check-maps-consistent.sh`
- `.claude/features/contract/scripts/rabbit-triage.sh`
- `.claude/features/contract/scripts/validate-feature.sh`
- `.claude/features/contract/scripts/workspace-map.sh`

**skills/**
- `.claude/features/contract/skills/rabbit-workspace-map/SKILL.md`

**scripts/enforcement/**
- `.claude/features/contract/scripts/enforcement/check-imports-resolve.sh`
- `.claude/features/contract/scripts/enforcement/check-naming.sh`
- `.claude/features/contract/scripts/enforcement/check-no-main-edits.sh`
- `.claude/features/contract/scripts/enforcement/check-opus-for-planning-agents.sh`
- `.claude/features/contract/scripts/enforcement/check-sentinel.sh`
- `.claude/features/contract/scripts/enforcement/check-symlinks-resolve.sh`
- `.claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.sh`
- `.claude/features/contract/scripts/enforcement/check-tests-non-interactive.sh`

## Invariants

1. Every file in `templates/` carries a `template_version` field.
2. `dispatch-feature-edit.sh` output begins with the sentinel `RABBIT-POLICY-BLOCK-v1`.
3. All scripts in `scripts/` and `scripts/enforcement/` are executable.
4. Every schema file in `schemas/` is valid JSON.
5. `rabbit-print.schema.json` is the authoritative definition of the `[rabbit]` print format used by all rabbit-workflow hooks and CLI scripts.
6. `workspace-map.sh` exists, is executable, and produces valid JSON (conforming to `workspace-map.json.schema.json`) when called without flags (show mode); with `--human` it produces human-readable terminal output; with `--audit` it produces a findings-only JSON object (with a `findings` array) listing deviations from the declared workspace structure — missing required nodes emit `error` severity, unknown nodes emit `warn`, missing optional nodes emit no finding; user projects without a `workspace-structure.json` emit a `warn`-severity `missing_declaration` finding. Both show mode and audit mode also accept `--human` for human-readable output.
7. `workspace-map.json.schema.json` is at schema version 2.0.0 and uses a `oneOf` discriminated union: show mode (with `roots` array of annotated node trees, with a `repoRoot` string field alongside the `roots` array) and audit mode (with `findings` array of severity/type/path/root objects). The v1 flat-array properties (`features`, `scripts`, `schemas`, `commands`, `skills`, `hooks`, `userProjectDirs`) are removed. `workspace-structure.json` exists at `.claude/features/contract/schemas/workspace-structure.json`, is valid JSON, and defines a node-tree schema: documents conforming to it must have `schema_version`, `owner`, `root`, `nodes` at top level; each node must have `name`, `required`, `description`, `children`.
8. `rabbit-workspace-map/SKILL.md` exists under `.claude/features/contract/skills/` (source of truth, deployed to `.claude/skills/` by generate-skills-dir.sh) and instructs Claude to directly execute `workspace-map.sh` on invocation — using `--human` for readable terminal output and the default JSON mode for programmatic use — rather than merely describing how to invoke it.
9. `build-contract.json` exists at `.claude/features/contract/build-contract.json`, is valid JSON, and validates against `.claude/features/contract/schemas/build-contract.schema.json`.
10. All `copy-file` targets declared in `build-contract.json` have a `source` field whose path exists on disk (relative to the repo root).
11. `relink.sh` does NOT exist at `.claude/features/contract/scripts/relink.sh`.
12. `.claude/workspace-structure.json` exists, is valid JSON, conforms to the `workspace-structure.json` schema (requires `schema_version`, `owner`, `root`, `nodes` at top level), has `root` equal to `"rabbit"`, and declares nodes for `features`, `skills`, `hooks`, and `commands`.
13. `check-naming.sh` documents that the `rbt-` prefix is fully deprecated with no remaining valid use cases; comments and flag messages in that script must not reference `rbt-` as a valid or recommended prefix. The current naming policy is: user-facing artifacts use `rabbit-`; the `rbt-` prefix is banned.
14. `rabbit-triage.sh` is called as `rabbit-triage.sh <feature-dir> <bug-name>` and locates bug.json at `<repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json` (centralized bug storage, where `<feature-name>` is the basename of `<feature-dir>`). It does NOT look in `<feature-dir>/docs/bugs/`.

## Out of Scope

- This feature does not directly edit any other feature's files.
