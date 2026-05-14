---
title: Rabbit Workflow Redesign — TDD / Feature-Touch / Bug / Backlog
date: 2026-05-14
status: approved
owner: rabbit-workflow team
---

# Rabbit Workflow Redesign

## Motivation

The current system has TDD tightly coupled to `rabbit-feature-touch`. Bug and
backlog skills have no TDD workflow — they are purely metadata lifecycle tools.
`registry.json` is a centralized generated artifact that causes merge conflicts
in parallel branches. `CLAUDE.md` can accumulate generated content. Branch
creation happens at session start with meaningless names.

This redesign:
- Makes TDD a standard subagent invocable from any skill
- Wires bug and backlog skills into the TDD cycle via a contracted handoff
- Introduces `rabbit-feature-scope` as a shared, skill-agnostic scope resolver
- Removes `registry.json` in favour of distributed `feature.json` files
- Converts `CLAUDE.md` to a pure `@-import` pointer (no generated content)
- Moves branch creation to the skill level with meaningful, contracted names

---

## Architecture Overview

```
rabbit-feature-scope  (new shared skill — anyone can invoke)
         ↑
  [optional invocation]

rabbit-feature-touch  (revised orchestration skill)
  Step 1: scope resolution (skip in B/B mode)
  Step 2: create branch (mode-determined name)
  Step 3: dispatch TDD subagents per feature, parallel if multiple
  Step 4: collect TDD reports, verify test-green
  Step 5: create PR to main; summarize to user
          (B/B mode: also hand tdd-report.json path to calling skill)

rabbit-bug / rabbit-backlog  (revised skills)
  Filing:  scope-resolve → clarify → filing/ branch → file JSON → auto-merge PR
  Working: eval subagent → invoke feature-touch B/B mode → receive report
           → commit updated bug/item JSON to fix/task branch → review PR
```

---

## Implementation Phasing

| Phase | Components | Notes |
|---|---|---|
| 1 — Foundation | `find-feature.sh`, TDD state prune, CLAUDE.md pointer, session-init branch removal, R7 gate update, .gitignore | Shared dependency; must complete first |
| 2 — Interface (parallel) | `rabbit-feature-scope` skill, TDD report schema | Independent of each other |
| 3 — Orchestration | `rabbit-feature-touch` revision, `dispatch-feature-tdd.sh` consolidation | Depends on phases 1 and 2 |
| 4 — Consumers (parallel) | `rabbit-bug` revision, `rabbit-backlog` revision | Both depend on phase 3; independent of each other |

---

## Section 1 — Infrastructure Changes (Foundation)

### 1a. Distributed Registry — `find-feature.sh`

`registry.json` is **dropped as a stored artifact**. `rebuild-registry.sh` is removed.
The `test-green` post-transition hook that called `rebuild-registry.sh` is removed from
`tdd-step.sh`.

A new utility `find-feature.sh` (owned by `contract` feature) replaces all registry
lookups across the codebase:

```bash
find-feature.sh <feature-name>   # prints feature dir path; exit 1 if not found
find-feature.sh --list            # prints all feature names, one per line
find-feature.sh --list-json       # prints [{name, path, summary, tdd_state}, ...] JSON
```

Internally walks `.claude/features/` and any project-level `features/` dirs declared
in `workspace-structure.json`, reads each `feature.json`, indexes by `.name`.
Always authoritative; no stale artifact possible.

**Scripts updated to use `find-feature.sh`:**
- `dispatch-feature-edit.sh`
- `dispatch-feature-tdd.sh`
- `dispatch-spec-update.sh`
- `resolve-feature-scope.sh` (deleted; replaced by `rabbit-feature-scope`)
- `file-bug.sh`
- `file-backlog-item.sh`

**`scope-guard.sh`** updated: per-feature marker lookup currently reads `registry.json`
(line ~89). Updated to use `find-feature.sh`.

### 1b. TDD State Machine — Prune `review` and `merged`

`tdd-step.sh` removes `review` and `merged` from `forward_next()` and
`is_valid_state()`. The chain becomes:

```
spec → spec-update → test-red → impl → test-green → deprecated (terminal)
```

`tdd-context.sh` corrected to match: `spec-update` added to `allowed_next()`
between `spec` and `test-red`; guidance text for `spec-update` state added.
Any tests exercising `review` or `merged` transitions are updated or removed.

### 1c. CLAUDE.md — Pure `@-import` Pointer

`generate-claude-md.sh` is **removed** from `rabbit-cage`.

`CLAUDE.md` is rewritten to contain only `@-import` pointer lines pointing to
distributed policy source files under `features/policy/`. The inline
`rabbit-policy-start` / `rabbit-policy-end` block is removed.

`session-init.sh` path 1 (inline section injection) becomes dead code and is
removed. Path 2 (`@-import` parsing and injection) remains unchanged.

`CLAUDE.md` becomes stable: it only changes when a policy file is added or
removed from the import list. No generated content; no merge conflicts.

### 1d. Branch Creation — Removed from `session-init.sh`

The R1 block in `session-init.sh` that creates `session/YYYYMMDD-HHMMSS`
branches is removed. Branch creation moves entirely to the skill level.

The scope-guard still prevents writes without a scope marker — no unguarded
window. The first action of any work skill (feature-touch, bug working,
backlog working) is branch creation.

### 1e. R7 Gate — Updated

`bug-status.sh` close gate updated:

- **Before:** requires `vet-triage.json` + `tdd-gap.json` files in bug dir
- **After:** requires `vet-triage.json` present AND `tdd_report` field present
  in `bug.json` history

`tdd-gap.json` check is removed. `--skip-vet-reason` still bypasses both checks.

### 1f. `.gitignore` Addition

```
tdd-report.json
.claude/tdd-report.json
```

`tdd-report.json` is a session-local ephemeral file; never committed.

### 1g. `workspace-structure.json` Updated

`rabbit-feature-scope` entry added under `features`.
`tdd-state-machine` entry updated (removes `resolve-feature-scope.sh` from surface).

---

## Section 2 — `rabbit-feature-scope` (New Shared Skill)

**New feature:** `.claude/features/rabbit-feature-scope/`

**Purpose:** Resolve a natural-language request to the list of features whose
files the request will modify. General-purpose shared skill — makes no
assumptions about who calls it or when.

### Script: `scripts/resolve-scope.sh`

```bash
resolve-scope.sh "<request-description>"
# Output: assembled prompt to stdout
# Caller dispatches with default model
# Response JSON: {"features": ["feat-a"], "rationale": "one sentence"}
```

- Replaces `resolve-feature-scope.sh` from `tdd-state-machine` (that script deleted)
- Uses `find-feature.sh --list-json` instead of `registry.json`
- Dispatched with **default model** (no Opus override)
- Response is authoritative; caller parses JSON and acts on feature list

### Skill: `rabbit-feature-scope`

Surfaces the script usage, input/output contract, and response schema.
Makes no prescriptions about callers.

### Ownership

- New `rabbit-feature-scope` feature owns this skill
- `tdd-state-machine` spec updated: `resolve-feature-scope.sh` removed from surface
- `resolve-feature-scope.sh` deleted from `tdd-state-machine/scripts/`

---

## Section 3 — `rabbit-feature-touch` (Revised Skill)

### Unified Five-Step Sequence

All modes (normal and B/B) follow the same five steps. Mode affects branch
naming and what happens at step 5.

```
Step 1: Scope resolution
        Normal mode: invoke rabbit-feature-scope → get feature list
        B/B mode:    skipped — feature name read from passed file's related_feature field

Step 2: Create branch
        Normal, single feature:  feat/<feature-name>-<keywords>
        Normal, multi-feature:   feat/<primary-feature>-multi-<keywords>
                                 (primary = first feature in scope resolution response)
        Bug fix (B/B):           fix/<bug-id>-<keywords>
        Backlog task (B/B):      task/<backlog-id>-<keywords>
        <keywords> = 2–4 words from request, hyphenated, lowercase
        Created via: git checkout -b <branch-name>

Step 3: Dispatch TDD subagents
        One subagent per feature; parallel if multiple features
        Each subagent receives: feature name, request, linked item context (B/B mode)

Step 4: Collect TDD reports
        Verify: tdd_state = test-green, test_result = pass for every feature
        If any fail: stop, surface error to user before proceeding

Step 5: Create PR / hand off
        Normal mode: feature-touch creates PR to main; summary presented to user
        B/B mode:    feature-touch commits code to branch; writes tdd-report.json
                     locally (not committed); hands off to calling skill.
                     Calling skill commits item JSON update to same branch,
                     then creates the single review PR. PR creation is the
                     calling skill's responsibility in B/B mode.
```

### Branch Naming Contract

| Mode | Pattern |
|---|---|
| Normal, single feature | `feat/<feature-name>-<keywords>` |
| Normal, multi-feature | `feat/<primary-feature>-multi-<keywords>` |
| Bug fix | `fix/<bug-id>-<keywords>` |
| Backlog task | `task/<backlog-id>-<keywords>` |
| Filing | `filing/<item-id>` |

### B/B Mode Handoff to Calling Skill

After committing code to the branch, feature-touch provides:

```json
{
  "mode": "bug|backlog",
  "linked_item": "<path>",
  "feature": "<name>",
  "branch": "<branch-name>",
  "tdd_report_path": "<repo-root>/tdd-report.json",
  "status": "success|failed"
}
```

If `status` is `failed`, the calling skill surfaces the failure to the user
before any item close action. No PR is created on failure.

If `status` is `success`, the calling skill uses `tdd_report_path` to run
`bug-status.sh set closed --tdd-report <path>` or `backlog-item-status.sh
set implemented --tdd-report <path>`, which embeds the report summary into
the item JSON and commits it to the same branch. The calling skill then
creates the single review PR (code + item JSON). PR creation is the calling
skill's responsibility in B/B mode.

### Override/Bypass Path

Unchanged from current spec. Present confirm token, user approves in-conversation,
write `.rabbit-scope-override`, make direct edit. The override does not reset
`tdd_state`.

---

## Section 4 — TDD Subagent (`dispatch-feature-tdd.sh`) Consolidated

### Interface

```bash
dispatch-feature-tdd.sh <feature-name> "<request>" \
  [--linked-item <path> --item-type <bug|backlog>]
```

`--bug` and `--backlog` flags replaced by unified `--linked-item` + `--item-type`.
Extensible to future item types without new flags.

### TDD Cycle (embedded in emitted prompt, in order)

```
0. Set scope marker: touch .rabbit-scope-active-<feature>; trap EXIT to remove
1. Force to spec-update: tdd-step.sh transition <dir> spec-update --force
2. Dispatch Opus spec-update subagent (dispatch-spec-update.sh)
3. Advance to test-red (or --spec-no-change-reason if spec unchanged)
4. Dispatch test subagent — write failing tests only; confirm fail
5. Advance to impl
6. Dispatch impl subagent — implement until tests pass; advance to test-green
7. Inline spec-review — read spec invariants + git diff HEAD -- <feature-dir>;
   produce spec_compliance assessment directly (no nested Agent dispatch)
8. Write tdd-report.json to repo root (gitignored, overwritten each run)
9. Remove scope marker (EXIT trap fires)
```

### Contracted `tdd-report.json` Schema

```json
{
  "schema_version": "1.0.0",
  "feature": "<name>",
  "request": "<original request text>",
  "linked_item": "<path or null>",
  "item_type": "<bug|backlog|null>",
  "spec_changes": "<yes|no>",
  "spec_no_change_reason": "<text or null>",
  "test_gap_analysis": "<what was missing in test coverage, or 'none'>",
  "impl_summary": "<brief description of what was implemented>",
  "spec_compliance": "<pass|fail>",
  "spec_compliance_notes": "<gaps found, or null>",
  "test_result": "<pass|fail>",
  "tdd_state": "test-green",
  "impl_commit": "<SHA>"
}
```

### HANDOFF Block (emitted by subagent, references report)

```
HANDOFF:
  feature: <name>
  tdd_state: test-green
  test_result: pass
  spec_compliance: pass|fail
  tdd_report_path: <repo-root>/tdd-report.json
  notes: <brief>
```

### What Is Removed

- Hardcoded `--bug` / `--backlog` flag handling
- Post-test-green `bug-status.sh` / `backlog-item-status.sh` calls (moved to calling skills)
- `HANDOFF_LINKED_ITEM` inline block (replaced by report schema)

---

## Section 5 — `rabbit-bug` (Revised Skill + Scripts)

### Filing Protocol

1. Invoke `rabbit-feature-scope` to identify related feature (or ask user if ambiguous)
2. Ask clarifying questions if bug description is insufficient
3. Create branch: `filing/RABBIT-BUG-N` (N from `file-bug.sh` output)
4. Run `file-bug.sh` → creates `bug.json` under `.claude/bugs/<feature>/RABBIT-BUG-N/`
5. Commit and create **auto-merge PR** to main (metadata only)

### Working Protocol

1. Run read-only eval subagent (default model) — reads `bug.json` + current feature
   spec; determines if bug still stands
2. **If invalid/stale:** confirm with user → `filing/RABBIT-BUG-N-invalidate` branch
   → `bug-status.sh set refused` → commit → auto-merge PR
3. **If valid:** invoke `rabbit-feature-touch` in B/B mode, passing bug dir path
4. Receive handoff from feature-touch: branch name + `tdd-report.json` path
5. Run `bug-status.sh set closed --tdd-report tdd-report.json
   --fix-commits <impl_commit>` — embeds TDD report summary into `bug.json`,
   commits to the `fix/` branch
6. Create **review PR** (same `fix/` branch; contains code fix + updated `bug.json`)

### Script Changes

| Script | Change |
|---|---|
| `file-bug.sh` | No change |
| `bug-status.sh` | Add `--tdd-report <path>` flag; R7 checks `tdd_report` field in `bug.json` history instead of `tdd-report.json` file; remove `tdd-gap.json` check |
| `list-bugs.sh` | No change |

`vet-triage.json` and `rabbit-triage.sh` unchanged — triage still required before close.

### PR Tiers

| PR type | Branch | Merge |
|---|---|---|
| Filing | `filing/RABBIT-BUG-N` | Auto-merge |
| Invalidate/refuse | `filing/RABBIT-BUG-N-invalidate` | Auto-merge |
| Fix (code + close) | `fix/<bug-id>-<keywords>` | Requires review |

---

## Section 6 — `rabbit-backlog` (Revised Skill + Scripts)

Mirrors `rabbit-bug` exactly in structure. Vocabulary differences only.

### Filing Protocol

1. Invoke `rabbit-feature-scope` to identify related feature (or ask user if ambiguous)
2. Ask clarifying questions if item description is insufficient
3. Create branch: `filing/RABBIT-BACKLOG-N`
4. Run `file-backlog-item.sh` → creates `item.json` under
   `.claude/backlogs/<feature>/RABBIT-BACKLOG-N/`
5. Commit and create **auto-merge PR** to main

### Working Protocol

1. Run read-only eval subagent (default model) — reads `item.json` + current feature
   spec; determines if item is still relevant and correctly scoped
2. **If invalid/stale:** confirm with user → `filing/RABBIT-BACKLOG-N-cancel` branch
   → `backlog-item-status.sh set cancelled` → commit → auto-merge PR
3. **If valid:** invoke `rabbit-feature-touch` in B/B mode, passing item dir path
4. Receive handoff from feature-touch: branch name + `tdd-report.json` path
5. Run `backlog-item-status.sh set implemented --tdd-report tdd-report.json
   --fix-commits <impl_commit>` — embeds TDD report summary into `item.json`,
   commits to the `task/` branch
6. Create **review PR** (same `task/` branch; contains implementation + updated `item.json`)

### Script Changes

| Script | Change |
|---|---|
| `file-backlog-item.sh` | No change |
| `backlog-item-status.sh` | Add `--tdd-report <path>` flag; add `--fix-commits` flag (currently missing); `implemented` transition embeds TDD report summary into `item.json` |
| `list-backlog.sh` | No change |

### PR Tiers

| PR type | Branch | Merge |
|---|---|---|
| Filing | `filing/RABBIT-BACKLOG-N` | Auto-merge |
| Cancel | `filing/RABBIT-BACKLOG-N-cancel` | Auto-merge |
| Task (impl + close) | `task/<backlog-id>-<keywords>` | Requires review |

---

## Invariants

1. `tdd-report.json` is never git-tracked. It is session-local and overwritten on each TDD run.
2. The permanent TDD record lives in `bug.json` / `item.json` as an embedded `tdd_report` field.
3. Branch creation is always the first write action of any work skill.
4. `rabbit-feature-scope` makes no assumptions about its callers.
5. The TDD subagent performs spec-review inline — no nested Agent dispatch.
6. `registry.json` does not exist. Feature lookup always uses `find-feature.sh`.
7. `CLAUDE.md` contains only `@-import` pointer lines. No generated content.
8. `review` and `merged` are not valid TDD states. The TDD work cycle ends at `test-green`.

---

## Files Deleted

- `.claude/features/contract/scripts/rebuild-registry.sh`
- `.claude/features/registry.json`
- `.claude/features/tdd-state-machine/scripts/resolve-feature-scope.sh`
- `.claude/features/rabbit-cage/scripts/generate-claude-md.sh`

## New Files

- `.claude/features/contract/scripts/find-feature.sh`
- `.claude/features/rabbit-feature-scope/` (full feature scaffold)
- `docs/superpowers/specs/2026-05-14-rabbit-workflow-redesign.md` (this file)
