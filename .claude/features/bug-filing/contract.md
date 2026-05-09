# Contract — bug-filing

## Reads

- `$BUG_ROOT/<bug-name>/bug.json` — for `bug-status.sh get` and
  `list-bugs.sh`.
- `$BUG_ROOT/` directory listing — for `list-bugs.sh`.

## Writes

- `$BUG_ROOT/<bug-name>/` — directory creation by `file-bug.sh`.
- `$BUG_ROOT/<bug-name>/bug.json` — JSON manifest, written by `file-bug.sh`
  and surgically updated by `bug-status.sh`.

`$BUG_ROOT` defaults to `.claude/docs/bugs`. Override via env for tests.

## Invokes

- `jq` — JSON construction, parsing, slurping, surgical updates.
- `date -u` — UTC ISO-8601 timestamps.

## Inputs / Outputs

### `file-bug.sh`

- **Inputs:** flag args (`--name`, `--title`, `--severity`, `--description`,
  optional `--related-feature`, `--filed-by`).
- **Stdout:** `filed: <path-to-bug.json>` on success.
- **Stderr:** `ERROR: ...` on validation error.
- **Exit:** `0` success; `1` validation error; `2` bad invocation.
- **Side effects:** creates a directory and a JSON file; no other writes.

### `bug-status.sh get`

- **Inputs:** `<bug-dir>`.
- **Stdout:** current status (`open` / `closed` / `reopened`).
- **Exit:** `0` success; `2` missing dir or file.

### `bug-status.sh set`

- **Inputs:** `<bug-dir> <new-status> --note <reason> [--actor <a>]`.
- **Stdout:** `<old> -> <new>` on transition; `no-op: already <s>` for same.
- **Stderr:** `ERROR: ...` on denied transition or invalid input.
- **Exit:** `0` success; `1` denied/invalid; `2` bad invocation.
- **Side effects:** updates `bug.json` (status, closed, closed_by, history).

### `list-bugs.sh`

- **Inputs:** optional `--status`, `--feature`, `--text`.
- **Stdout:** JSON array (default) or formatted text (`--text`). Empty store
  yields `[]` or `(no bugs)`.
- **Exit:** `0`.

## Cross-scope handoff

- **Triage and routing** — out of scope. Caller dispatches `vet`
  (separate feature) to triage a bug and route it to the affected feature's
  owner.
- **Filing a bug from inside the breeder** — supported: `breeder` may
  invoke `file-bug.sh` as part of a request with `operation: add_bug`.
- **Schema evolution** — adding a new field to `bug.json` is non-breaking
  if the field is optional (downstream tools must tolerate unknown fields).
  Renaming or removing a field requires a major version bump.

## Versioning

- Current version: `1.0.0`.
- Adding a new severity is non-breaking (additive).
- Adding a new status would require updating the transition table. That's a
  major version bump.
- Adding a new optional field (e.g. `assignee`, `due_date`) is non-breaking.
