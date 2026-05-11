# rabbit-backlog

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns backlog item filing and lifecycle for all rabbit features. Provides two
scripts: `file-backlog-item.sh` (creates new backlog items) and
`backlog-item-status.sh` (reads and transitions item status).

Backlog items live under `docs/backlog/<ITEM-ID>/item.json`. The schema and
valid status transitions are declared in `docs/backlog/backlog-contract.md`.

## Schema / Behavior

Each backlog item is a directory containing one `item.json` file. Fields:

- `name` — item identifier (e.g. `BACKLOG-001`)
- `title` — short human-readable title
- `status` — `open | in-progress | done | cancelled`
- `priority` — `low | medium | high | critical`
- `description` — free-form description (may be empty)
- `owner` — accountable individual or team
- `filed` / `filed_by` — creation timestamp and actor
- `closed` — ISO8601 timestamp set when status transitions to `done` or `cancelled`
- `history` — append-only log of all status transitions

### `file-backlog-item.sh`

Creates a new backlog item directory with an `item.json` in initial `open` status.

```
file-backlog-item.sh --name <item-id> --title <title> \
                     [--priority low|medium|high|critical] \
                     [--owner <name>] --dir <item-dir>
```

### `backlog-item-status.sh`

Reads or transitions an item's status.

```
backlog-item-status.sh get <item-dir>
backlog-item-status.sh set <item-dir> <new-status> [--reason <text>]
```

Valid transitions:
- `open -> in-progress`
- `in-progress -> done`
- `open -> cancelled`
- `in-progress -> cancelled`

Direct `open -> done` is rejected.

## What this feature does NOT define

- Bug filing (`docs/bugs/`) — that remains within each feature's own scope
  (managed by `file-bug.sh` in rabbit-cage).
- Feature scaffolding — owned by rabbit-cage.
- TDD state machine — owned by `tdd-state-machine`.

## Tests

`test/run.sh` runs the end-to-end suite (9 tests). All tests must pass when
`tdd_state` is `test-green`.
