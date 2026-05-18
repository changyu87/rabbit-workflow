---
name: rabbit-file
description: Use when Claude detects intent to file a bug or backlog item, check item status, list items, close/reopen an item, or perform any bug or backlog lifecycle operation in this repository. Replaces rabbit-bug and rabbit-backlog. Trigger on phrases like "file a bug", "log a backlog", "work this bug", "close the backlog item", "what bugs are open", "mark that done", "reopen that bug", or any lifecycle phrasing for bugs or backlogs — even casual language. Always use this skill instead of rabbit-bug or rabbit-backlog.
version: 1.1.0
owner: rabbit-file
deprecation_criterion: when a unified tracking system replaces file-based bug and backlog management
---

## Overview

Two modes — **File** and **Work** — for two types: **bug** and **backlog**. A **List** operation is also supported for read-only queries.

All items are stored on the dedicated branch `origin/bug-backlog-files`, never on `main` or any fix/task branch. Scripts live at `.claude/features/rabbit-file/scripts/`.

Invocation surface — there are NO slash commands; all surface is direct
script invocation:

| Mode | Script | Purpose |
|---|---|---|
| File  | `python3 .claude/features/rabbit-file/scripts/file-item.py …`     | File a new bug or backlog item |
| Work  | `python3 .claude/features/rabbit-file/scripts/item-status.py …`   | Read or transition item state |
| List  | `python3 .claude/features/rabbit-file/scripts/list-items.py …`    | List items with filters |
| Show  | `python3 .claude/features/rabbit-file/scripts/item-status.py show …` | Print full item.json |

---

## Branch Initialization

If `origin/bug-backlog-files` does not exist yet, or a feature has no `counter.json` for a given type, `branch_ops.py` initializes them automatically:

- **Branch missing**: create it as an orphan branch with an empty root commit, then push.
- **counter.json missing**: initialize with `{"next": 1}` before allocating the first ID.

This means filing always succeeds even in a fresh repo — no manual setup required.

---

## File Protocol

When the user confirms they want to file a bug or backlog item:

1. Invoke `rabbit-feature-scope` to identify the related feature (or ask the user if ambiguous).
2. Ask clarifying questions if title, description, or priority are missing.
3. Call `file-item.py`:
   ```bash
   python3 .claude/features/rabbit-file/scripts/file-item.py \
     --type bug|backlog \
     --feature <feature-name> \
     --title "..." \
     --priority <low|medium|high|critical> \
     --description "..."
   ```

   Internally `file-item.py` calls `branch_ops` in two phases:

   **Phase A — ID allocation** (`branch_ops.allocate_id(feature, type)`):
   - Sets up worktree at `.claude/tmp/bug-backlog-files` (gitignored)
   - Reads or initializes `rabbit/features/<feature>/<type>s/counter.json`
   - Increments counter, commits and pushes to `origin/bug-backlog-files`
   - Returns assigned ID (e.g. `RABBIT-CAGE-BUG-17`)
   - Cleans up worktree

   **Phase B — Item commit** (`branch_ops.commit_item(feature, type, id, item_dict)`):
   - Sets up worktree again
   - Writes `item.json` to `rabbit/features/<feature>/<type>s/<ID>/item.json`
   - Commits and pushes to `origin/bug-backlog-files`
   - Backfills commit SHA into `item.json`, pushes update
   - Cleans up worktree

4. Report the assigned ID and commit SHA to the user. No PR, no temp branch.

---

## List Protocol

When the user wants to see open or closed items:

```bash
python3 .claude/features/rabbit-file/scripts/list-items.py \
  --type bug|backlog|all \
  [--feature <feature-name>] \
  [--status open|close]
```

`list-items.py` uses `branch_ops.read_branch()` (worktree setup → walk `item.json` files → filter → cleanup). No writes occur.

If `origin/bug-backlog-files` does not exist, inform the user that no items have been filed yet and direct them to `/rabbit-file file`.

Output format: `NAME  [TYPE]  [STATUS]  [PRIORITY]  TITLE`

---

## Work Protocol

When the user asks to work or close a bug or backlog item:

1. **Retrieve** — `branch_ops.fetch_item(feature, type, id)` reads `item.json` from `origin/bug-backlog-files` (worktree setup → read → cleanup). If the item is not found, inform the user and stop.

2. **Eval subagent** — dispatch a read-only default-model subagent:
   - Reads fetched `item.json` + current feature spec (`docs/spec/spec.md`)
   - Returns verdict: `valid` (still relevant and reproducible) or `stale/invalid` with reason
   - Its impl-suggestion output MUST include a **test gap analysis**
     section that names the existing tests covering the affected
     behaviour and lists any missing tests the implementer should add
     before turning RED → GREEN (BACKLOG-2). A bug fix without an
     accompanying regression test is incomplete.

3. **User-decision gate** — after the eval subagent returns, brief the user:
   - Summarize verdict and reasoning
   - State a clear recommendation: close without work (if stale/invalid) or proceed (if valid)
   - Ask explicitly: "Should I **close** this item without working it, or **proceed** to work it?"
   - Do NOT invoke `rabbit-feature-touch` until the user confirms.

4. **If user chooses to close without work:**
   ```bash
   python3 .claude/features/rabbit-file/scripts/item-status.py set \
     --feature <feature> --type bug|backlog --id <ID> \
     --status close --reason "<why>"
   ```
   `branch_ops` commits the updated `item.json` directly to `origin/bug-backlog-files`. No PR.

5. **If user confirms to proceed:**
   - Invoke `rabbit-feature-touch` in B/B mode, passing the item dir path on the dedicated branch.
   - Receive handoff: `{branch, tdd_report_path, status}` where
     `tdd_report_path` is an absolute path emitted by the subagent.
   - If `status: failed` — surface error to user. Stop.
   - If `status: success`, extract `impl_commit` from the report file at
     the path returned in the handoff (substitute the actual path
     reported in the handoff for `<tdd_report_path>` below):
     ```bash
     IMPL_COMMIT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['impl_commit'])" <tdd_report_path>)
     python3 .claude/features/rabbit-file/scripts/item-status.py set \
       --feature <feature> --type bug|backlog --id <ID> \
       --status close \
       --reason "TDD cycle complete" \
       --fix-commits "$IMPL_COMMIT"
     ```
   - `branch_ops` commits updated `item.json` to `origin/bug-backlog-files`.
   - Create **review PR** on the fix/task branch (code only — `item.json` is already on the dedicated branch).

---

## Scripts Reference

| Script | Purpose |
|---|---|
| `file-item.py` | File a new bug or backlog item |
| `item-status.py` | Read or transition item status |
| `list-items.py` | List items with optional filters (`--type bug\|backlog\|all`) |
| `branch_ops.py` | All git operations against `origin/bug-backlog-files` |

---

## item.json Schema

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

- `type`: `"bug"` or `"backlog"`
- `priority`: required — `low | medium | high | critical`
- `status`: `"open"` or `"close"` — bidirectional, reason always recorded in `history`
- `closed`: timestamp set on close, cleared on reopen

---

## Status Lifecycle

```
open ↔ close    (bidirectional — reason required on every transition)
```

---

## Branch Layout

```
origin/bug-backlog-files
└── rabbit/
    └── features/
        └── <feature-name>/
            ├── bugs/
            │   ├── counter.json          {"next": 17}
            │   └── RABBIT-CAGE-BUG-16/
            │       └── item.json
            └── backlogs/
                ├── counter.json          {"next": 4}
                └── RABBIT-CAGE-BACKLOG-3/
                    └── item.json
```

---

## branch_ops.py Lifecycle

Every write operation follows this pattern to prevent item data or commits from leaking into `main` or any fix/task branch:

1. `git worktree add .claude/tmp/bug-backlog-files origin/bug-backlog-files`
2. Read/write files inside `.claude/tmp/bug-backlog-files/`
3. `git -C .claude/tmp/bug-backlog-files add <files>`
4. `git -C .claude/tmp/bug-backlog-files commit -m "..."`
5. `git -C .claude/tmp/bug-backlog-files push origin bug-backlog-files`
6. `git worktree remove --force .claude/tmp/bug-backlog-files` (always — including on failure via try/finally)

`.claude/tmp/` is gitignored by contract.
