# onboard — Spec

**Version:** 1.0.0
**Owner:** rabbit-workflow team
**Deprecation criterion:** when project scaffolding is offered by a native Claude Code mechanism

## Purpose

`onboard` scaffolds and maintains `project-{name}/` directories under the repo root. Each project directory holds a `project-map.json` (linking source paths to rabbit features) and a `features/registry.json` (the project-local feature registry).

The `rabbit-project.sh` script is the sole entry point. It is non-interactive and exits 0 on success, 1 on error, 2 on bad invocation.

## Sub-commands

### `init <name>`

Creates `project-{name}/` under `REPO_ROOT` with:
- `project-{name}/features/` — feature directory root
- `project-{name}/contract/` — placeholder for project-level contract artifacts
- `project-{name}/project-map.json` — from `contract/templates/project-map-template.json`, with `{{project_name}}` substituted
- `project-{name}/features/registry.json` — from `contract/templates/registry-template.json`, with `{{owner}}` substituted

Fails if `project-{name}/` already exists.

### `set-path <name> <absolute-path>`

Updates the `path` field in `project-{name}/project-map.json` to `<absolute-path>`. The path argument must start with `/`. Fails if `project-map.json` does not exist.

### `map <name> <source-path> <feature-name>`

Adds or updates `source_map["<source-path>"]` = `"<feature-name>"` in `project-{name}/project-map.json`. Fails if `project-map.json` does not exist.

### `consolidate <name>`

Validates the consistency of `project-{name}/project-map.json` against `project-{name}/features/registry.json`:

1. For each feature in `registry.json` with no `source_map` entry: logs `note: feature <f> has no source_map entry in project-map.json` to stderr.
2. For each `source_map` entry whose feature name is not in `registry.json`: logs `warning: source_map refers to unknown feature <f>` to stderr.
3. Detects overlapping source paths (one is a prefix of another): logs `warning: overlapping paths: <a> and <b>` to stderr.

Exits 0 even when warnings are emitted. Fails if `project-map.json` does not exist.

## Invariants

- `init` does NOT touch `.claude/features/registry.json` (the rabbit-internal registry).
- `consolidate` is non-interactive: no prompts, no stdin reads.
- Contract changes (schemas, templates) go through TDD on the `contract` feature, not `onboard`.
- `onboard` never modifies any file under `.claude/features/` except indirectly through `consolidate` logs.

## Deprecation criterion

When project scaffolding is offered by a native Claude Code mechanism, this feature is superseded and should be migrated to that mechanism.
