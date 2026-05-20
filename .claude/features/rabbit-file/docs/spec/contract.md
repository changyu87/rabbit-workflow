---
feature: rabbit-file
version: 0.2.0
template_version: 2.0.0
owner: rabbit-workflow team
deprecation_criterion: when a unified tracking system replaces file-based bug and backlog management
---

# rabbit-file — Contract

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when a unified tracking system replaces file-based bug and backlog management",
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/rabbit-file/scripts/branch_ops.py",
        "description": "All git operations against origin/bug-backlog-files. Uses a per-process git worktree at .claude/tmp/bug-backlog-files-<pid> (gitignored). Exposes allocate_id, commit_item, fetch_item, read_branch, release_id, branch_exists. Auto-initializes orphan branch and counter.json on first use against a non-local origin; refuses orphan creation when origin is local (chained-workspace guard, BUG-32). Exposes module-level constants BRANCH, IDENTITY_NAME, IDENTITY_EMAIL."
      },
      {
        "path": ".claude/features/rabbit-file/scripts/file-item.py",
        "description": "Files a new bug or backlog item. Args: --type bug|backlog --feature F --title T --priority low|medium|high|critical --description D. Allocates an ID then commits item.json. Enforces per-field length limits and ASCII-control-char sanitisation (BACKLOG-7). Rolls back the counter slot via release_id on commit_item failure."
      },
      {
        "path": ".claude/features/rabbit-file/scripts/item-status.py",
        "description": "Reads, transitions, or updates fields on an item. Subcommands: get | show | set | update. set requires --reason on every transition and short-circuits no-op transitions. update mutates priority|title|description on OPEN items only, with audit trail in history."
      },
      {
        "path": ".claude/features/rabbit-file/scripts/list-items.py",
        "description": "Lists items from origin/bug-backlog-files filtered by --type, --feature, --status. Output is sorted ascending by item name (deterministic). Distinguishes the branch-missing condition from the no-items-matched-filters condition."
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [
      {
        "path": ".claude/features/rabbit-file/skills/rabbit-file/SKILL.md",
        "description": "Operator-facing skill: File, Work, List, Show modes for bug and backlog items. Triggers on lifecycle phrasing (file, log, work, close, reopen, list, what bugs are open). Replaces rabbit-bug and rabbit-backlog skills."
      }
    ]
  },
  "reads": {
    "files": [
      "<repo>/.claude/tmp/bug-backlog-files-<pid>/rabbit/features/<feature>/bugs/counter.json",
      "<repo>/.claude/tmp/bug-backlog-files-<pid>/rabbit/features/<feature>/bugs/<ID>/item.json",
      "<repo>/.claude/tmp/bug-backlog-files-<pid>/rabbit/features/<feature>/backlogs/counter.json",
      "<repo>/.claude/tmp/bug-backlog-files-<pid>/rabbit/features/<feature>/backlogs/<ID>/item.json"
    ],
    "external": [
      "origin/bug-backlog-files (remote ref, fetched and checked out into per-process worktree)"
    ]
  },
  "invokes": {
    "scripts": [],
    "agents": []
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "Write item data or counter.json to the main branch or any fix/task branch — all writes go through the bug-backlog-files worktree.",
    "Edit item.json on the bug-backlog-files branch directly; all mutations route through file-item.py, item-status.py set, or item-status.py update so every change is recorded in the history array.",
    "Reuse the legacy fixed worktree path .claude/tmp/bug-backlog-files (without the -<pid> suffix); concurrent agents would race on the same path.",
    "Skip allocate_id before commit_item; the counter must reserve the ID slot first.",
    "Push from a stale base — every push retries with a fetch + reset + reapply on non-fast-forward or ref-lock contention.",
    "Mutate the caller-supplied item dict in branch_ops.commit_item; commit_sha backfill is applied to an internal copy only.",
    "Create the orphan bug-backlog-files branch when origin is a local filesystem path (chained-workspace topologies require the intermediate to materialise the branch from upstream first; BUG-32).",
    "Allow item-status.py update on closed items, or on fields outside {priority, title, description}."
  ]
}
```
