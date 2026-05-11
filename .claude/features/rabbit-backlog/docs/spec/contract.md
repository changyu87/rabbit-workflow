# Contract — rabbit-backlog

## Reads

- `<item-dir>/item.json` — backlog item status and history (via `backlog-item-status.sh get`)

## Writes

- `<item-dir>/item.json` — created by `file-backlog-item.sh`; mutated by `backlog-item-status.sh set`
- `docs/backlog/<ITEM-ID>/item.json` — canonical storage location for items filed in this feature
- Git commits — `file-backlog-item.sh` commits the newly created `item.json`;
  `backlog-item-status.sh set` commits the mutated `item.json` after every
  transition. Commit messages follow the form
  `backlog: <ITEM-ID> <old-status> -> <new-status> (<reason summary>)` for
  transitions and `backlog: file <ITEM-ID> (<title>)` for creation.

## Invokes

- `jq` — JSON manipulation for item.json read/write
- `git` — `git add` and `git commit` after filing and after every status transition

## Inputs / Outputs

### `file-backlog-item.sh`

- Input: `--name <id>`, `--title <str>`, `--priority <level>`, `--owner <str>`, `--dir <path>`
- Output: path of created item directory (stdout); `item.json` written to `<dir>/item.json` and committed to git
- Exit: 0=created, 1=error, 2=usage

### `backlog-item-status.sh`

- Input (get): `<item-dir>`
- Output (get): current status string (stdout)
- Input (set): `<item-dir> <new-status> --reason <text> [--fix-commits <sha>[,<sha>...]]`
  - `--reason` is required on every `set` invocation
  - `--fix-commits` is required when `<new-status>` is `implemented` and rejected otherwise
- Output (set): transition string `"<old> -> <new>"` (stdout); `item.json` mutated in-place and committed to git
- Exit: 0=ok, 1=error (including missing `--reason`, missing/forbidden `--fix-commits`, invalid transition), 2=usage

## Cross-scope handoff

This feature does not delegate to other features. Callers (rabbit-cage, other
features) invoke these scripts to file and manage their own backlog items.
The `--dir` argument determines where items are stored; this feature does not
enforce a storage path on callers.

The status enum (`open | in-progress | implemented | refused | reopened`) is
the canonical backlog terminology and is unified with the bug system's
terminal-state vocabulary (`refused`).

## Versioning

- Current version: `1.0.0`.
- Bump rules: minor bump on new fields added to item.json schema; major bump
  on breaking schema changes or removed fields.
- Breaking changes in 1.0.0 (from 0.1.0):
  - Status `done` renamed to `implemented`.
  - Status `cancelled` renamed to `refused`.
  - New status `reopened` added.
  - `--reason` is now required on every transition (previously optional).
  - New required field `fix_commits` on transitions to `implemented`.
  - New behavior: scripts now produce git commits.
- Migration: pre-1.0.0 items using `done`/`cancelled` must be rewritten to
  `implemented`/`refused` (one-shot rename); no coexistence window because
  the file format is local to each feature directory and migration is a
  trivial substitution.
- Deprecation criterion: when rabbit features are retired or a unified
  project management system replaces file-based backlog.
