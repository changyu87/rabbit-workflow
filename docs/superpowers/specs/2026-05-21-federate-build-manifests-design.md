# Federate Build Manifests — Design Spec

**Backlog:** CONTRACT-BACKLOG-21  
**Date:** 2026-05-21  
**Status:** approved for implementation

---

## Problem

`contract/build-contract.json` is a monolithic list of every copy-file target across all features. Adding a script to any feature requires editing the `contract` feature — a bounded-scope violation. This also creates gaps: `rabbit-config/scripts/rabbit-config.py` and `rabbit-feature/scripts/` are not declared because the friction of touching `contract` has let them fall through.

---

## Design Decisions

### 1. publish.json schema shape — flat targets, relative source paths

Each feature publishes a `publish.json` with a flat `targets` array. Source paths are **relative to the feature root** (not the repo root), eliminating the redundant `.claude/features/<feature>/` prefix.

```json
{
  "schema_version": "1.0.0",
  "feature": "rabbit-cage",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively manages workspace artifact generation",
  "targets": [
    {
      "name": "hooks/refresh.py",
      "type": "copy-file",
      "source": "hooks/refresh.py",
      "destination": ".claude/hooks/refresh.py",
      "check_on_stop": true
    }
  ]
}
```

`check_on_stop` remains per-target because some targets (README.md, install.py) are legitimately `false`.

### 2. Discovery model — iterate feature.json, check for publish.json

`build.py` and `sync-check.py` discover manifests by:

1. Globbing `.claude/features/*/feature.json` (sorted, deterministic)
2. Skipping features with `"status": "retired"`
3. Checking if `publish.json` exists in the feature dir; silently skipping if not
4. Resolving each target's `source` path: `feature_dir / target["source"]` → absolute

Features without a `publish.json` (contract, policy) need not add one.

### 3. build-contract.json — fully retired

`build-contract.json` and `build-contract.schema.json` are deleted. The new schema lives at `contract/schemas/publish-manifest.schema.json`. The two targets with `check_on_stop: false` (README.md, install.py) move into `rabbit-cage/publish.json`.

### 4. Migration strategy — atomic (single PR)

All changes land in one PR: schema creation, per-feature publish.json files, build.py/sync-check.py refactor, test changes, and build-contract.json deletion. No coexistence window. Per "delete what no longer exists."

### 5. sync-check.py failure mode — soft-fail with warning

If a `publish.json` fails to parse, `_collect_drifted_targets` logs a stderr warning and skips that feature. Malformed manifests must not block the Stop hook. Schema validation violations at runtime are also soft-fail (the build step validates — Stop hook detects drift, not schema errors).

### 6. Test strategy — contract test suite owns publish.json validation

Two new tests added to `contract/test/`:
- `test-publish-manifests.py` — for each active feature with a `publish.json`: validates against schema, all source paths exist on disk.
- `test-publish-manifest-schema.py` — schema file is valid JSON and itself validates against a meta-schema.

Two existing tests deleted: `test-build-contract.py` and `test-build-contract-post-consolidation.py` (contract no longer owns a monolithic manifest).

`run.py` updated to remove old tests, add new ones.

### 7. Backward-compatibility — none

Hard cutover. No consumers outside this repo reference `build-contract.json`.

---

## Publish.json Per Feature

### rabbit-cage (11 targets — 10 existing + 1 new)

| source (relative to feature root) | destination | check_on_stop |
|---|---|---|
| hooks/refresh.py | .claude/hooks/refresh.py | true |
| hooks/scope-guard.py | .claude/hooks/scope-guard.py | true |
| hooks/session-init.py | .claude/hooks/session-init.py | true |
| hooks/sync-check.py | .claude/hooks/sync-check.py | true |
| commands/rabbit-refresh.md | .claude/commands/rabbit-refresh.md | true |
| commands/rabbit-project.md | .claude/commands/rabbit-project.md | true |
| settings.json | .claude/settings.json | true |
| skills/rabbit-config/SKILL.md | .claude/skills/rabbit-config/SKILL.md | true |
| **skills/rabbit-config/scripts/rabbit-config.py** | **.claude/skills/rabbit-config/scripts/rabbit-config.py** | **true** |
| README.md | README.md | false |
| install.py | install.py | false |

The bolded row fixes the root cause described in the backlog.

### rabbit-feature (5 targets — unchanged)

| source | destination | check_on_stop |
|---|---|---|
| skills/rabbit-feature-touch/SKILL.md | .claude/skills/rabbit-feature-touch/SKILL.md | true |
| skills/rabbit-feature-scope/SKILL.md | .claude/skills/rabbit-feature-scope/SKILL.md | true |
| skills/rabbit-feature-new/SKILL.md | .claude/skills/rabbit-feature-new/SKILL.md | true |
| skills/rabbit-feature-audit/SKILL.md | .claude/skills/rabbit-feature-audit/SKILL.md | true |
| skills/rabbit-feature-spec/SKILL.md | .claude/skills/rabbit-feature-spec/SKILL.md | true |

### rabbit-file (1 target — unchanged)

| source | destination | check_on_stop |
|---|---|---|
| skills/rabbit-file/SKILL.md | .claude/skills/rabbit-file/SKILL.md | true |

### tdd-subagent (2 targets — unchanged)

| source | destination | check_on_stop |
|---|---|---|
| agents/tdd-subagent.md | .claude/agents/tdd-subagent.md | true |
| scripts/dispatch-tdd-subagent.py | .claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py | true |

### tdd-state-machine (1 target — unchanged)

| source | destination | check_on_stop |
|---|---|---|
| scripts/tdd-step.py | .claude/agents/tdd-subagent/scripts/tdd-step.py | true |

### contract, policy — no publish.json

These features own schemas and policies but deploy nothing to `.claude/`.

---

## Schema — publish-manifest.schema.json

Stored at `contract/schemas/publish-manifest.schema.json`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "publish-manifest",
  "description": "Per-feature publish manifest declaring copy-file targets to the deployed .claude/ surface",
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code natively manages workspace artifact generation",
  "type": "object",
  "required": ["schema_version", "feature", "owner", "deprecation_criterion", "targets"],
  "properties": {
    "schema_version": {"type": "string"},
    "feature": {"type": "string"},
    "owner": {"type": "string"},
    "deprecation_criterion": {"type": "string"},
    "targets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type", "source", "destination"],
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["copy-file"]},
          "source": {"type": "string"},
          "destination": {"type": "string"},
          "check_on_stop": {"type": "boolean"}
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

---

## build.py Refactor

`build.py` gains a `discover_manifests(root)` function that iterates `feature.json` files, skips retired features, and yields `(feature_dir, manifest)` tuples. The copy logic currently in `build-targets.py` (~30 lines: sha256 compare, mkdir, shutil.copy, marker write) is inlined directly into `build.py`. `build-targets.py` becomes dead code and is deleted.

Discovery → resolution → copy all happens in one script, no subprocess or temp file needed.

Public interface unchanged: `python3 build.py [REPO_ROOT]`

## sync-check.py Refactor

`_collect_drifted_targets(root)` gains the same discovery loop. The contract path reference is removed. On JSON parse error for any feature's `publish.json`, a warning is logged to stderr and that feature is skipped (soft-fail). `check_on_stop: true` targets are sha256-compared as before.

---

## Test Changes

| File | Action |
|---|---|
| `test-build-contract.py` | Delete |
| `test-build-contract-post-consolidation.py` | Delete |
| `test-publish-manifests.py` | Add (validates each active feature publish.json against schema; all sources exist on disk) |
| `test-publish-manifest-schema.py` | Add (schema file is valid JSON and has required ownership fields) |
| `run.py` | Remove deleted tests; add new tests in same position |

---

## Implementation Order (atomic PR)

1. `contract/schemas/publish-manifest.schema.json` — add schema
2. `{feature}/publish.json` for rabbit-cage, rabbit-feature, rabbit-file, tdd-subagent, tdd-state-machine — add manifests  
3. `contract/test/test-publish-manifests.py` — add test (will pass once publish.json files exist)
4. `contract/test/test-publish-manifest-schema.py` — add test
5. `rabbit-cage/scripts/build.py` — federated discovery (inline copy logic, retire build-targets.py)
6. `rabbit-cage/hooks/sync-check.py` — federated drift check
7. `contract/test/run.py` — swap test references
8. Delete `contract/build-contract.json` and `contract/schemas/build-contract.schema.json`
9. Delete `contract/test/test-build-contract.py`, `test-build-contract-post-consolidation.py`, and `rabbit-cage/scripts/build-targets.py`
10. Run `python3 .claude/features/rabbit-cage/scripts/build.py` — verify all 20 targets build
11. Run all 7 test suites — verify green
