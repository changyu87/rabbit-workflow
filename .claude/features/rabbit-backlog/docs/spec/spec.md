# rabbit-backlog

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns backlog item filing and lifecycle for all rabbit features. Provides three
scripts: `file-backlog-item.sh` (creates new backlog items),
`backlog-item-status.sh` (reads and transitions item status), and
`list-backlog.sh` (lists backlog items with optional filtering).

Backlog items live under `docs/backlog/<ITEM-ID>/item.json`. The schema and
valid status transitions are declared in `docs/backlog/backlog-contract.md`.

Item lifecycle is version-controlled: `file-backlog-item.sh` commits the new
`item.json` to git after creation, and every `backlog-item-status.sh set`
transition commits the mutated `item.json`. This makes the audit trail
inspectable through `git log` in addition to the in-file `history` array.

## Schema / Behavior

Each backlog item is a directory containing one `item.json` file. Fields:

- `name` — item identifier (e.g. `BACKLOG-001`)
- `title` — short human-readable title
- `status` — `open | in-progress | implemented | refused | reopened`
- `priority` — `low | medium | high | critical`
- `description` — free-form description (may be empty)
- `owner` — accountable individual or team
- `filed` / `filed_by` — creation timestamp and actor
- `closed` — ISO8601 timestamp set when status transitions to `implemented`
  or `refused`; cleared (set to null) when status transitions to `reopened`
- `fix_commits` — array of git commit SHAs that delivered the item; set when
  transitioning to `implemented`. Empty array `[]` for items that never
  reached `implemented`.
- `history` — append-only log of all status transitions. Every entry records
  `from`, `to`, `at`, `by`, and `reason` (reason is required on every
  transition).

### `file-backlog-item.sh`

Creates a new backlog item directory with an `item.json` in initial `open`
status, then `git add`s and `git commit`s the new file.

```
file-backlog-item.sh --name <item-id> --title <title> \
                     [--priority low|medium|high|critical] \
                     [--owner <name>] --dir <item-dir>
```

### `backlog-item-status.sh`

Reads or transitions an item's status. Every `set` invocation requires a
`--reason` argument and commits the mutated `item.json` to git.

```
backlog-item-status.sh get <item-dir>
backlog-item-status.sh set <item-dir> <new-status> --reason <text> \
                       [--fix-commits <sha>[,<sha>...]]
```

`--reason` is required on every transition.
`--fix-commits` is required when `<new-status>` is `implemented`; rejected
otherwise.

Valid transitions:
- `open -> in-progress`
- `open -> refused`
- `in-progress -> implemented`
- `in-progress -> refused`
- `implemented -> reopened`
- `refused -> reopened`
- `reopened -> in-progress`
- `reopened -> refused`

Direct `open -> implemented` is rejected. Any transition not listed above
(e.g. `refused -> in-progress`, `implemented -> in-progress`) is rejected;
revival must go through `reopened`.

### `list-backlog.sh`

Lists backlog items from centralized `.claude/backlogs/` storage with optional
filtering.

```
list-backlog.sh                         # all items, JSON array
list-backlog.sh --status open|in-progress|implemented|refused|reopened
list-backlog.sh --feature NAME[,NAME2]  # only named features (comma-separated)
list-backlog.sh --text                  # human-readable: NAME  [STATUS]  [PRIORITY]  TITLE per line
list-backlog.sh -h|--help
```

- Default output: JSON array of `item.json` objects.
- `--text` prints one line per item: `NAME  [STATUS]  [PRIORITY]  TITLE`.
- `--status` filters by exact status value.
- `--feature` filters by feature bucket name(s); comma-separated values accepted.

### Invariants

- `closed` is non-null iff current `status` is `implemented` or `refused`.
- `fix_commits` is non-empty iff the item has ever reached `implemented`
  (the array persists across a subsequent `reopened` transition).
- Every `history` entry has a non-empty `reason`.
- `reopened` is only reachable from `implemented` or `refused`.

### feature.json Surface Invariants

- `surface.skills` MUST be `[]` (empty array). Skills are now managed via
  explicit copy-file entries in `build-contract.json`. The `surface.skills`
  field in `feature.json` is the retired mechanism and must not be populated.

## Dependencies

### `workspace-map.sh` (from contract)

`file-backlog-item.sh` invokes `workspace-map.sh` (located at
`.claude/features/contract/scripts/workspace-map.sh`) to resolve the canonical
backlog storage path for a given feature name. The scripts do NOT construct
the path by convention — they delegate path resolution to `workspace-map.sh`.

`backlog-item-status.sh` does not invoke `workspace-map.sh` directly; callers
pass a resolved `<item-dir>` path. Path resolution happens upstream at filing
time via `file-backlog-item.sh`.

## What this feature does NOT define

- Bug filing (`docs/bugs/`) — that remains within each feature's own scope
  (managed by `file-bug.sh` in rabbit-cage).
- Feature scaffolding — owned by rabbit-cage.
- TDD state machine — owned by `tdd-state-machine`.
- Backlog storage path convention — owned by `workspace-map.sh` in contract.

## Tests

`test/run.sh` runs the end-to-end suite. All tests must pass when
`tdd_state` is `test-green`.
