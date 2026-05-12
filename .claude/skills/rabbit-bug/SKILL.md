---
name: rabbit-bug
description: Use when Claude detects intent to file a bug, check bug status, list bugs, close/reopen/refuse a bug, or perform any bug lifecycle operation (triage, resolution, reopen, refuse) in this repository. Trigger this skill whenever the user mentions filing a bug, reporting an issue, checking bug status, listing open bugs, closing or refusing a bug report, or any other bug tracking action in rabbit-workflow.
version: 1.0.0
owner: rabbit-bug
deprecation_criterion: when a unified tracking system replaces file-based bug management
---

## Overview

The `rabbit-bug` feature provides three CLI scripts for managing bug lifecycle in this repository. All scripts live at `.claude/features/rabbit-bug/scripts/` relative to the repo root. Bugs are stored under `.claude/bugs/` in JSON files.

---

## Scripts

### 1. `file-bug.sh` — File a new bug

**Path:** `.claude/features/rabbit-bug/scripts/file-bug.sh`

**Usage:**
```
file-bug.sh --title T --severity S --description D [--related-feature F] [--filed-by A]
```

**Parameters:**

| Flag | Required | Description |
|------|----------|-------------|
| `--title T` | Yes | Short title for the bug |
| `--severity {low\|medium\|high\|critical}` | Yes | Bug severity level |
| `--description D` | Yes | Full description — **never modified after filing** |
| `--related-feature F` | No | Feature name; must match a key in `registry.json` |
| `--filed-by A` | No | Who is filing; defaults to `$USER` |

**Output:**
- Prints the path of the created bug directory on success
- Creates: `.claude/bugs/<feature-name>/<PREFIX>-N/bug.json`

**Example:**
```bash
.claude/features/rabbit-bug/scripts/file-bug.sh \
  --title "scope-guard ignores symlinks" \
  --severity high \
  --description "When a symlink points into a protected feature dir, the scope-guard does not resolve it and allows the write." \
  --related-feature rabbit-cage \
  --filed-by changyu
```

---

### 2. `bug-status.sh` — Read or transition bug status

**Path:** `.claude/features/rabbit-bug/scripts/bug-status.sh`

**Subcommands:**

#### `get` — Print current status
```
bug-status.sh get <bug-dir>
```
Prints the current status string (`open`, `closed`, `reopened`, or `refused`).

#### `set` — Transition to a new status
```
bug-status.sh set <bug-dir> <status> --note R [--actor A] [--skip-vet-reason S] [--fix-commits C] [--touched-files F]
```

**Parameters:**

| Flag | Required | Description |
|------|----------|-------------|
| `<bug-dir>` | Yes | Path to the bug directory (contains `bug.json`) |
| `<status>` | Yes | Target status (see valid values below) |
| `--note R` | Yes | Reason or note for the transition |
| `--actor A` | No | Who is making the transition; defaults to `$USER` |
| `--skip-vet-reason S` | No | Skip vet artifact check with this justification |
| `--fix-commits C` | No | Commit SHA(s) that fix the bug |
| `--touched-files F` | No | Files modified by the fix |

**Valid statuses:** `open`, `closed`, `reopened`, `refused`

**Valid transitions:**

| From | To |
|------|----|
| `open` | `closed` |
| `open` | `refused` |
| `closed` | `reopened` |
| `reopened` | `closed` |
| `reopened` | `refused` |
| `refused` | `reopened` |

**R7 enforcement:** Closing a bug (`open→closed` or `reopened→closed`) requires both `vet-triage.json` and `tdd-gap.json` to exist in the bug directory. To skip this check, provide `--skip-vet-reason` with a justification.

**Examples:**
```bash
# Check current status
.claude/features/rabbit-bug/scripts/bug-status.sh get .claude/bugs/rabbit-cage/RBT-1/

# Close a bug with vet artifacts present
.claude/features/rabbit-bug/scripts/bug-status.sh set .claude/bugs/rabbit-cage/RBT-1/ closed \
  --note "Fixed in commit abc123" \
  --fix-commits abc123 \
  --touched-files ".claude/hooks/scope-guard.sh"

# Close a bug skipping vet check
.claude/features/rabbit-bug/scripts/bug-status.sh set .claude/bugs/rabbit-cage/RBT-1/ closed \
  --note "Hotfix applied" \
  --skip-vet-reason "urgent prod fix, vet deferred to follow-up"

# Refuse a bug
.claude/features/rabbit-bug/scripts/bug-status.sh set .claude/bugs/rabbit-cage/RBT-2/ refused \
  --note "Not a bug — expected behavior per spec"
```

---

### 3. `list-bugs.sh` — List bugs with optional filtering

**Path:** `.claude/features/rabbit-bug/scripts/list-bugs.sh`

**Usage:**
```
list-bugs.sh [--status STATUS] [--feature NAME[,NAME2]] [--text]
```

**Parameters:**

| Flag | Description |
|------|-------------|
| *(no args)* | Print JSON array of all bugs |
| `--status {open\|closed\|reopened\|refused}` | Filter by status |
| `--feature NAME[,NAME2,...]` | Filter by feature name (comma-separated for multiple) |
| `--text` | Human-readable output: `NAME  [STATUS]  TITLE` per line |

**Examples:**
```bash
# All bugs as JSON
.claude/features/rabbit-bug/scripts/list-bugs.sh

# All open bugs, human-readable
.claude/features/rabbit-bug/scripts/list-bugs.sh --status open --text

# Bugs for a specific feature
.claude/features/rabbit-bug/scripts/list-bugs.sh --feature rabbit-cage

# Multiple features, JSON
.claude/features/rabbit-bug/scripts/list-bugs.sh --feature rabbit-cage,rabbit-bug

# Open bugs for a feature, human-readable
.claude/features/rabbit-bug/scripts/list-bugs.sh --status open --feature rabbit-cage --text
```

---

## Bug Storage Layout

```
.claude/bugs/
└── <feature-name>/          # matches --related-feature value, or "unlinked"
    └── <PREFIX>-N/          # e.g. RBT-1, RBT-2
        ├── bug.json         # canonical bug record (title, severity, status, history)
        ├── vet-triage.json  # required to close (R7)
        └── tdd-gap.json     # required to close (R7)
```

## Status Lifecycle

```
         ┌──────────────────────┐
         │         open         │
         └──┬───────────────────┘
            │                 │
         closed            refused
            │                 │
         reopened ◄───────────┘
            │
         closed / refused
```
