# rabbit-file: Unified Bug & Backlog Skill — Design Spec

**Date:** 2026-05-14
**Owner:** rabbit-file
**Status:** Approved — ready for implementation planning

---

## Problem

Two separate skills (`rabbit-bug`, `rabbit-backlog`) handle bugs and backlog items with nearly identical working protocols. Both use shell scripts (`.sh`) despite the project tech stack unifying to Python. Both store data as commits to temporary `filing/` branches on `main`, creating PR churn for metadata-only operations.

---

## Solution

A single unified skill `/rabbit-file` that handles both types. Items are stored on a dedicated, deletion-protected branch `origin/bug-backlog-files` — no temp branches, no PRs for filing. All scripts are Python.

---

## Architecture (Option B — chosen)

```
.claude/features/rabbit-file/
  scripts/
    branch_ops.py     # all reads/writes against origin/bug-backlog-files
    file-item.py      # filing protocol
    item-status.py    # status transitions
    list-items.py     # listing/querying
  skills/rabbit-file/
    SKILL.md          # published to .claude/skills/ by build contract
  docs/spec/spec.md
  test/run.sh
```

`branch_ops.py` is the only code that touches `origin/bug-backlog-files`. All other scripts delegate to it.

---

## Dedicated Branch

**Name:** `origin/bug-backlog-files`
**Protection:** deletion-protected (configured at repo level — admin task, outside scope of this feature)

**Layout:**
```
origin/bug-backlog-files
└── rabbit/
    └── features/
        └── <feature-name>/
            ├── bugs/
            │   ├── counter.json          {"next": N}
            │   └── <FEATURE-BUG-N>/
            │       └── item.json
            └── backlogs/
                ├── counter.json          {"next": N}
                └── <FEATURE-BACKLOG-N>/
                    └── item.json
```

**Initialization:** `branch_ops.py` auto-initializes the branch (orphan) and any missing `counter.json` on first use — no manual setup required.

---

## Unified item.json Schema

```json
{
  "name": "RABBIT-CAGE-BUG-17",
  "type": "bug",
  "title": "...",
  "status": "open",
  "priority": "high",
  "description": "...",
  "related_feature": "rabbit-cage",
  "filed": "2026-05-14T10:00:00Z",
  "filed_by": "cyxu",
  "closed": null,
  "history": [
    {
      "ts": "2026-05-14T10:00:00Z",
      "actor": "cyxu",
      "action": "opened",
      "note": "initial filing"
    }
  ]
}
```

| Field | Rule |
|---|---|
| `type` | `"bug"` or `"backlog"` |
| `priority` | required — `low\|medium\|high\|critical` |
| `status` | `"open"` or `"close"` — bidirectional, reason in history |
| `closed` | timestamp set on close, cleared on reopen |

Dropped from old schemas: `severity` (replaced by `priority`), `closed_by`, `owner`, vet-triage gate.

---

## ID Naming Convention

Unchanged from current:
- Bugs: `<FEATURE-UPPER>-BUG-N`
- Backlogs: `<FEATURE-UPPER>-BACKLOG-N`

---

## Status Lifecycle

```
open ↔ close    (bidirectional — reason required on every transition)
```

No intermediate states. No `refused`, `in-progress`, `implemented` — only `open` and `close`.

---

## branch_ops.py — Local Staging

Every write operation uses a git worktree to avoid polluting the current branch:

1. `git worktree add .claude/tmp/bug-backlog-files origin/bug-backlog-files`
2. Read/write inside `.claude/tmp/bug-backlog-files/`
3. `git -C .claude/tmp/bug-backlog-files add <files>`
4. `git -C .claude/tmp/bug-backlog-files commit -m "..."`
5. `git -C .claude/tmp/bug-backlog-files push origin bug-backlog-files`
6. `git worktree remove --force .claude/tmp/bug-backlog-files` (always — try/finally)

`.claude/tmp/` is gitignored by contract.

---

## File Protocol

1. Invoke `rabbit-feature-scope` to resolve related feature.
2. Ask clarifying questions if title/description/priority are missing.
3. `file-item.py` calls `branch_ops` in two phases:
   - **Phase A** — `allocate_id(feature, type)`: fetch, read/init counter, increment, commit+push, return ID
   - **Phase B** — `commit_item(feature, type, id, item_dict)`: write item.json, commit+push, backfill SHA, push
4. Report ID and commit SHA. No PR, no temp branch.

---

## List Protocol

```bash
python3 list-items.py --type bug|backlog|all [--feature F] [--status open|close]
```

Uses `branch_ops.read_branch()` (worktree → walk item.json → filter → cleanup). Read-only.
If branch doesn't exist: inform user, direct to `/rabbit-file file`.

Output: `NAME  [TYPE]  [STATUS]  [PRIORITY]  TITLE`

---

## Work Protocol

1. `branch_ops.fetch_item()` reads item.json from dedicated branch.
2. Eval subagent: reads item.json + feature spec → verdict `valid` or `stale/invalid`.
3. User-decision gate: present verdict, ask "close without work or proceed?"
4. If close without work: `item-status.py set close` → `branch_ops.commit_item()`.
5. If proceed: invoke `rabbit-feature-touch` (B/B mode, item dir) → TDD cycle → on success, `item-status.py set close --fix-commits <sha>` → `branch_ops.commit_item()` → review PR on fix/task branch (code only).

`rabbit-feature-touch` is NOT invoked until user confirms at step 3.

---

## Skill Invocation Surface

| Command | Purpose |
|---|---|
| `/rabbit-file file bug` | File a new bug |
| `/rabbit-file file backlog` | File a new backlog item |
| `/rabbit-file work bug <ID>` | Work or close a bug |
| `/rabbit-file work backlog <ID>` | Work or close a backlog item |
| `/rabbit-file list [bug\|backlog\|all] [--feature F] [--status S]` | List items |

---

## Migration

Old data in `.claude/bugs/` and `.claude/backlogs/` is archived to `.claude/archive/bugs/` and `.claude/archive/backlogs/` as a one-time commit to `main`. Old skills `rabbit-bug` and `rabbit-backlog` are retired (removed from build contract).

---

## Eval Results Summary (2 iterations, 4 evals each)

| Eval | With skill | Without skill |
|---|---|---|
| File a bug | Feature-scope caught correct owner, two-phase branch_ops, no PR | Manual reasoning, old script + temp branch + PR |
| Work a backlog | Graceful failure, named branch, offered suggestions | Searched old location, stopped and asked |
| List open bugs (feature) | Correct command + branch, edge case handled | Read from old location, legacy results |
| List all open (project) | `--type all`, no questions, edge case handled | 5 manual steps, old locations |
