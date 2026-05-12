# Symlink Elimination — Design Spec

**Date:** 2026-05-12
**Owner:** rabbit-workflow team
**Status:** approved

## Problem

All git-tracked symlinks in this repo must be eliminated. Symlinks cause fragility across tools, platforms, and installers. The existing CLAUDE.md and skills generation model (copy from source, commit the copy, drift-detect on Stop) already proves the correct pattern. This design extends that model to all remaining symlinked artifacts.

## Current git-tracked symlinks

| Path | Target | Runtime-affecting |
|---|---|---|
| `.claude/commands` | `features/rabbit-cage/commands/` | yes |
| `.claude/hooks` | `features/rabbit-cage/hooks/` | yes |
| `.claude/settings.json` | `features/rabbit-cage/settings.json` | yes |
| `.claude/policy` | `features/policy/` | no (path alias, unused at runtime) |
| `.claude/contract` | `features/contract/` | no (path alias, unused at runtime) |
| `README.md` | `.claude/features/rabbit-cage/README.md` | no |
| `install.sh` | `.claude/features/rabbit-cage/install.sh` | no |

## Design

### Section 1: Architecture

A new machine-readable contract (`build-contract.json`) declares every generated artifact in the workspace. A new unified runner (`build.sh`) reads it and executes. This replaces three separate callers (`generate-claude-md.sh --write`, `generate-skills-dir.sh`, `relink.sh`) with one.

**`build-contract.json`** — owned by the `contract` feature, at `.claude/features/contract/build-contract.json`. Declares all targets: name, type, source, destination, `check_on_stop`. Schema at `.claude/features/contract/schemas/build-contract.schema.json`.

**`build.sh`** — owned by rabbit-cage, at `.claude/features/rabbit-cage/scripts/build.sh`. Reads `build-contract.json` and builds all targets. No `--check` flag — drift checking is the responsibility of `test-generated-surface.sh`.

**`sync-check.sh`** — calls `test-generated-surface.sh`; on failure calls `build.sh` then emits drift alert.

**`install.sh`** — replaces three generation calls with one: `build.sh TARGET`.

**Deleted with no replacement:**
- `relink.sh`
- `generate-skills-dir.sh`
- `.claude/policy` symlink (git rm)
- `.claude/contract` symlink (git rm)

`workspace-map.sh` is left untouched (known spec gap).

### Section 2: Components

**`build-contract.json`** has two target types only:

- `generate-claude-md`: delegates to `generate-claude-md.sh`. No `source` field (sources are implicit: `features/policy/*.md`).
- `copy-file`: copies a single file from `source` to `destination`. Both paths are repo-relative.

Every target declares `check_on_stop` (bool). Runtime-affecting artifacts set it `true`; non-runtime artifacts set it `false`.

Full target list:

| name | type | source | destination | check_on_stop |
|---|---|---|---|---|
| CLAUDE.md | generate-claude-md | — | CLAUDE.md | true |
| hooks/refresh.sh | copy-file | .claude/features/rabbit-cage/hooks/refresh.sh | .claude/hooks/refresh.sh | true |
| hooks/scope-guard.sh | copy-file | .claude/features/rabbit-cage/hooks/scope-guard.sh | .claude/hooks/scope-guard.sh | true |
| hooks/session-init.sh | copy-file | .claude/features/rabbit-cage/hooks/session-init.sh | .claude/hooks/session-init.sh | true |
| hooks/sync-check.sh | copy-file | .claude/features/rabbit-cage/hooks/sync-check.sh | .claude/hooks/sync-check.sh | true |
| commands/rabbit-refresh.md | copy-file | .claude/features/rabbit-cage/commands/rabbit-refresh.md | .claude/commands/rabbit-refresh.md | true |
| commands/rabbit-set-threshold.md | copy-file | .claude/features/rabbit-cage/commands/rabbit-set-threshold.md | .claude/commands/rabbit-set-threshold.md | true |
| commands/rabbit-project.md | copy-file | .claude/features/rabbit-cage/commands/rabbit-project.md | .claude/commands/rabbit-project.md | true |
| settings.json | copy-file | .claude/features/rabbit-cage/settings.json | .claude/settings.json | true |
| skills/rabbit-backlog/SKILL.md | copy-file | .claude/features/rabbit-backlog/skills/rabbit-backlog/SKILL.md | .claude/skills/rabbit-backlog/SKILL.md | true |
| skills/rabbit-bug/SKILL.md | copy-file | .claude/features/rabbit-bug/skills/rabbit-bug/SKILL.md | .claude/skills/rabbit-bug/SKILL.md | true |
| skills/rabbit-feature-touch/SKILL.md | copy-file | .claude/features/tdd-state-machine/skills/rabbit-feature-touch/SKILL.md | .claude/skills/rabbit-feature-touch/SKILL.md | true |
| skills/rabbit-workspace-map/SKILL.md | copy-file | .claude/features/rabbit-cage/skills/rabbit-workspace-map/SKILL.md | .claude/skills/rabbit-workspace-map/SKILL.md | true |
| README.md | copy-file | .claude/features/rabbit-cage/README.md | README.md | false |
| install.sh | copy-file | .claude/features/rabbit-cage/install.sh | install.sh | false |

Adding a new skill or hook requires adding a `copy-file` entry to `build-contract.json` as part of that feature's TDD cycle.

`generate-claude-md.sh` stays as an implementation helper called by `build.sh`. `generate-skills-dir.sh` is retired — skills are now explicit `copy-file` entries. `relink.sh` is deleted.

`feature.json` surface blocks (`hooks`, `commands`, `settings`, `skills`) are retired across all features. `workspace-map.sh` is left as-is (known spec gap).

### Section 3: Data flow

**At install time:**
```
cp -r .claude/ TARGET/
build.sh TARGET          # reads build-contract.json, builds all targets in order
```

**Stop hook (`sync-check.sh`):**
```
if ! test-generated-surface.sh; then
    build.sh
    emit drift alert
fi
override alert           # unchanged
```

**`build.sh` internals:**
- Reads `build-contract.json` from `$REPO_ROOT/.claude/features/contract/build-contract.json`
- Iterates targets in declaration order
- For `generate-claude-md`: delegates to `generate-claude-md.sh`
- For `copy-file`: `cp -p source destination`, creating parent dirs as needed
- `REPO_ROOT` arg: optional, defaults to `git rev-parse --show-toplevel`

**Source-of-truth edit flow** (e.g. developer edits `features/rabbit-cage/hooks/sync-check.sh`):
1. Developer edits source in feature dir
2. Session ends → Stop hook fires
3. `test-generated-surface.sh` detects mismatch on `.claude/hooks/sync-check.sh`
4. `build.sh` regenerates the copy; drift alert emitted
5. Developer commits both source and deployed copy in one commit

**Git transition:**
- `git rm`: `.claude/commands`, `.claude/hooks`, `.claude/policy`, `.claude/contract`, `.claude/settings.json`, `README.md`, `install.sh` (all symlinks)
- `git add`: real files at the same paths (generated by `build.sh` before `git rm`)

### Section 4: Error handling and testing

**`build.sh` error handling:**
- Missing source file for a `copy-file` target → `build: source not found: <path>`, exit 1
- `generate-claude-md` fails → propagate its exit code
- Missing destination parent dirs → `mkdir -p` before copy (idempotent)

**`test-generated-surface.sh`** (replaces `test-symlinks.sh`):
Reads `build-contract.json`. For each target, diffs source against destination. Exits 0 (all match) or 1 (any mismatch), printing drifted targets.

- Test 1: exits 0 on a clean workspace
- Test 2: exits 1 when a target is artificially drifted

Same script used by both the TDD test suite and the Stop hook — one drift oracle, no duplication.

**Migration sequence** (implementation order):
1. Create `build-contract.json` (contract feature) and its schema
2. Create `build.sh` (rabbit-cage)
3. Create `test-generated-surface.sh` (rabbit-cage test); delete `test-symlinks.sh`
4. `git rm` all symlinks — removes them from git and the filesystem before build.sh runs
5. Run `build.sh` to produce real files at all destination paths
6. `git add` the real files
7. Update `sync-check.sh` — replace drift-check blocks with `test-generated-surface.sh` / `build.sh` pattern
8. Update `install.sh` — replace three generation calls with `build.sh TARGET`
9. Delete `relink.sh` and `generate-skills-dir.sh`
10. Retire surface blocks in each `feature.json` (hooks, commands, settings, skills)
