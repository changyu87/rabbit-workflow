# bug-filing

> Source of truth: [`feature.json`](./feature.json).

## Purpose

Defines the schema and operations for filing, transitioning, and querying bugs
in the rabbit workflow. Bugs are filesystem-native: each bug is a directory
under `.claude/docs/bugs/<bug-name>/` containing `bug.json` (machine-first
manifest) and any supporting artifacts (repro scripts, fix specs, etc.).

## Naming rule

Bug identifiers follow the pattern `<PREFIX>-<N>`:

- `PREFIX` = `related_feature` value, uppercased (hyphens preserved).
  Example: `related_feature: install-distribute` → `INSTALL-DISTRIBUTE`.
  When `--related-feature` is omitted, `$BUG_PREFIX` env var is used
  (default: `RBT`).
- `N` = positive integer, no padding, no ceiling. Auto-incremented by
  scanning `$BUG_ROOT` for existing IDs with the same prefix and taking
  `max + 1`.

Examples: `RBT-1`, `WORKLOG-3`, `INSTALL-DISTRIBUTE-12`.

`file-bug.sh` never accepts a `--name` arg. The name is always computed.
Collisions are prevented by the scan; no counter file needed.

## Schema (`bug.json`)

| Field             | Type      | Notes                                                     |
|-------------------|-----------|-----------------------------------------------------------|
| `name`            | string    | Same as the directory name                                |
| `title`           | string    | One-line human title                                      |
| `status`          | enum      | `open` \| `closed` \| `reopened`                          |
| `severity`        | enum      | `low` \| `medium` \| `high` \| `critical`                 |
| `description`     | string    | Free-form details                                         |
| `related_feature` | string?   | Name of the affected feature, or `null`                   |
| `filed`           | ISO-8601  | UTC timestamp of initial filing                           |
| `filed_by`        | string    | Actor name (defaults to `$USER`)                          |
| `closed`          | ISO-8601? | UTC timestamp of close, or `null` if open/reopened        |
| `closed_by`       | string?   | Actor who closed, or `null`                               |
| `history`         | array     | Append-only list of `{ts, actor, action, note}` entries   |

The `history` array is the audit log. Each transition appends one entry. A
no-op transition (setting status to its current value) is silently allowed
but does NOT append to history.

## Status transitions

```
open       → closed
closed     → reopened
reopened   → closed
(any)      → (same)   # no-op, no history append
```

**Disallowed (must use `reopened` instead):**

```
closed   → open
reopened → open
```

`open` is the initial state only. Once a bug has been closed, future cycles
use `closed` and `reopened` exclusively. This keeps the audit log
unambiguous.

## Scripts

### `file-bug.sh`

```
file-bug.sh --name <YYYY-MM-DD-slug> --title <t> --severity <l|m|h|c> \
            --description <d> [--related-feature <name>] [--filed-by <actor>]
```

Creates a new bug. Validates name format, severity enum, dedup, required
fields. Exits 0 on success; 1 on validation error; 2 on bad invocation.

### `bug-status.sh`

```
bug-status.sh get <bug-dir>
bug-status.sh set <bug-dir> <new-status> --note <reason> [--actor <a>]
```

Reads or transitions the status. Validates the transition rules above.
Appends to `history` on real transitions; silent no-op for same-status sets.

### `list-bugs.sh`

```
list-bugs.sh                        # JSON array of all bugs
list-bugs.sh --status <s>           # filter by status
list-bugs.sh --feature <name>       # filter by related_feature
list-bugs.sh --status s --feature f # combine filters
list-bugs.sh --text                 # human-readable text instead of JSON
```

Default output is a JSON array, parsed by deterministic tools. `--text` is
the LLM-prose view, useful when piping into a subagent prompt or quick
inspection.

## `$BUG_ROOT` override

All three scripts honor `$BUG_ROOT` (default: `.claude/docs/bugs`). This is
the test seam — fixtures point `$BUG_ROOT` at a temp directory.

## What this feature does NOT define

- **Triaging or routing** of bugs to feature owners — that is `vet`.
- **Test-coverage gap detection** when a bug reveals an untested code path —
  also `vet`'s responsibility (it dispatches a follow-up to the
  affected feature's owner).
- **Cross-tool sync** with external bug trackers — out of scope for v1.

Bounded scope: this feature owns the **format** and the **mechanical
operations**. Higher-level workflow lives in `vet`.

## Tests

`test/run.sh` runs three test files (26 cases total):

- `test-file-bug.sh` (10) — name validation, dedup, severity enum, required
  fields, `related_feature` persistence, default status, history seeding,
  length cap.
- `test-bug-status.sh` (9) — get, allowed transitions, denied transitions,
  invalid status, no-op behavior, history growth, missing-dir error.
- `test-list-bugs.sh` (7) — list all, filter by status, filter by feature,
  combined filters, `--text` mode, empty store.
