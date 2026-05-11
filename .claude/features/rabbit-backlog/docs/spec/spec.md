# rabbit-backlog

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns backlog item filing and lifecycle for all rabbit features. Provides two
scripts: `file-backlog-item.sh` (creates new backlog items) and
`backlog-item-status.sh` (reads and transitions item status).

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

### Invariants

- `closed` is non-null iff current `status` is `implemented` or `refused`.
- `fix_commits` is non-empty iff the item has ever reached `implemented`
  (the array persists across a subsequent `reopened` transition).
- Every `history` entry has a non-empty `reason`.
- `reopened` is only reachable from `implemented` or `refused`.

## What this feature does NOT define

- Bug filing (`docs/bugs/`) — that remains within each feature's own scope
  (managed by `file-bug.sh` in rabbit-cage).
- Feature scaffolding — owned by rabbit-cage.
- TDD state machine — owned by `tdd-state-machine`.

## Tests

`test/run.sh` runs the end-to-end suite. All tests must pass when
`tdd_state` is `test-green`.
