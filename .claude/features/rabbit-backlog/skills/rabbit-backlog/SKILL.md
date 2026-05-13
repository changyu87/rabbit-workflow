---
name: rabbit-backlog
description: Invoke when the user intends to file a backlog item, check backlog item status, transition a backlog item, or manage any backlog lifecycle in this repository. Use this skill whenever the user mentions filing, creating, or adding a backlog item; asking about a backlog item's status; moving a backlog item to in-progress, done, or cancelled; or any other backlog lifecycle operation — even if they phrase it as "log a todo", "track an issue", "mark that backlog as done", or similar casual language.
---

# rabbit-backlog skill

This skill covers three CLI scripts for filing, managing, and listing backlog items in the rabbit-workflow repository. All backlog data lives under `.claude/backlogs/`.

## Script 1 — file-backlog-item.sh

**Location:** `scripts/file-backlog-item.sh` (relative to this feature root)
**Repo path:** `.claude/features/rabbit-backlog/scripts/file-backlog-item.sh`

### Purpose
Files a new backlog item for a given rabbit feature. Creates a structured `item.json` directory under `.claude/backlogs/<feature-name>/`.

### Parameters

| Flag | Required | Description |
|------|----------|-------------|
| `--related-feature F` | **Yes** | Feature name. Must match a key in `.claude/features/registry.json`. |
| `--title T` | **Yes** | Short human-readable title for the backlog item. |
| `--priority {low\|medium\|high\|critical}` | No | Priority level. Default: `medium`. |
| `--owner O` | No | Owner name. Default: `$USER` (or `"unknown"` if unset). |

### Output
- Creates: `.claude/backlogs/<feature-name>/<PREFIX>-BACKLOG-N/item.json`
- Prints: the full path of the created item directory to stdout
- Exit codes: `0` = created, `1` = error, `2` = usage/bad args

### Example invocations

```bash
# Minimal — required flags only
.claude/features/rabbit-backlog/scripts/file-backlog-item.sh \
  --related-feature rabbit-cage \
  --title "Add retry logic to install hook"

# Full options
.claude/features/rabbit-backlog/scripts/file-backlog-item.sh \
  --related-feature rabbit-bug \
  --title "Improve error message for missing registry key" \
  --priority high \
  --owner alice
```

### Common errors
- `ERROR: --related-feature and --title are required` — one or both required flags missing.
- `ERROR: invalid priority '...'` — priority must be exactly `low`, `medium`, `high`, or `critical`.
- Feature not found in `registry.json` — the `--related-feature` value must match a key in `.claude/features/registry.json`.

---

## Script 2 — backlog-item-status.sh

**Location:** `scripts/backlog-item-status.sh` (relative to this feature root)
**Repo path:** `.claude/features/rabbit-backlog/scripts/backlog-item-status.sh`

### Purpose
Reads or transitions the status of an existing backlog item.

### Subcommands

#### `get <item-dir>`
Prints the current status string of the item.

```bash
.claude/features/rabbit-backlog/scripts/backlog-item-status.sh get \
  .claude/backlogs/rabbit-cage/RC-BACKLOG-1
# Output: open
```

#### `set <item-dir> <new-status> [--reason R]`
Transitions the item to a new status. Prints `"<old> -> <new>"` on success.

```bash
.claude/features/rabbit-backlog/scripts/backlog-item-status.sh set \
  .claude/backlogs/rabbit-cage/RC-BACKLOG-1 in-progress --reason "Picked up in sprint 4"
# Output: open -> in-progress
```

### Valid statuses
`open` | `in-progress` | `done` | `cancelled`

### Valid transitions

| From | To |
|------|----|
| `open` | `in-progress` |
| `open` | `cancelled` |
| `in-progress` | `done` |
| `in-progress` | `cancelled` |

Any other transition (e.g., `done → open`) is rejected with an error. Transitioning to the same status is a no-op.

### Parameters for `set`

| Arg | Required | Description |
|-----|----------|-------------|
| `<item-dir>` | **Yes** | Path to the backlog item directory (must contain `item.json`). |
| `<new-status>` | **Yes** | Target status: `open`, `in-progress`, `done`, or `cancelled`. |
| `--reason R` | No | Free-text reason for the transition; stored in item history. |

### Exit codes
`0` = ok, `1` = error, `2` = usage/bad args

---

## Typical workflows

### File a new backlog item and capture its path
```bash
ITEM_DIR=$(.claude/features/rabbit-backlog/scripts/file-backlog-item.sh \
  --related-feature rabbit-cage \
  --title "Handle missing registry.json gracefully" \
  --priority medium)
echo "Created: $ITEM_DIR"
```

### Start work on a backlog item
```bash
.claude/features/rabbit-backlog/scripts/backlog-item-status.sh set \
  "$ITEM_DIR" in-progress --reason "Starting implementation"
```

### Mark a backlog item done
```bash
.claude/features/rabbit-backlog/scripts/backlog-item-status.sh set \
  "$ITEM_DIR" done --reason "Fix merged in PR #42"
```

### Check the current status of an item
```bash
.claude/features/rabbit-backlog/scripts/backlog-item-status.sh get "$ITEM_DIR"
```

---

## Script 3 — list-backlog.sh

**Location:** `scripts/list-backlog.sh` (relative to this feature root)
**Repo path:** `.claude/features/rabbit-backlog/scripts/list-backlog.sh`

### Purpose
Lists backlog items from centralized `.claude/backlogs/` storage with optional
filtering by status and/or feature. Outputs a JSON array by default, or a
human-readable one-line-per-item summary with `--text`.

### Usage

```
list-backlog.sh [--status STATUS] [--feature NAME[,NAME2]] [--text]
list-backlog.sh -h|--help
```

### Parameters

| Flag | Description |
|------|-------------|
| *(no args)* | Print JSON array of all backlog items |
| `--status {open\|in-progress\|implemented\|refused\|reopened}` | Filter by exact status value |
| `--feature NAME[,NAME2,...]` | Filter by feature bucket name (comma-separated for multiple) |
| `--text` | Human-readable output: `NAME  [STATUS]  [PRIORITY]  TITLE` per line |
| `-h\|--help` | Print usage and exit 0 |

### Output

- Default (no `--text`): JSON array of `item.json` objects matching the filter(s).
  Empty result yields `[]`.
- `--text`: one line per item in the format `NAME  [STATUS]  [PRIORITY]  TITLE`.
  Empty result prints `(no items)` or `(no items match)`.
- Exit codes: `0` = success, `2` = usage error.

### Examples

```bash
# All backlog items as JSON
.claude/features/rabbit-backlog/scripts/list-backlog.sh

# All open items, human-readable
.claude/features/rabbit-backlog/scripts/list-backlog.sh --status open --text

# Items for a specific feature
.claude/features/rabbit-backlog/scripts/list-backlog.sh --feature rabbit-cage

# Multiple features, JSON output
.claude/features/rabbit-backlog/scripts/list-backlog.sh --feature rabbit-cage,rabbit-bug

# Open items for a specific feature, human-readable
.claude/features/rabbit-backlog/scripts/list-backlog.sh --status open --feature rabbit-cage --text
```
