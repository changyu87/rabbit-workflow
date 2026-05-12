# Contract — rabbit-backlog

## Reads

- `<item-dir>/item.json` — backlog item status and history (via `backlog-item-status.sh get`)
- `.claude/backlogs/<feature>/<ITEM-ID>/item.json` — read by `list-backlog.sh` when listing items

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
- `.claude/features/contract/scripts/workspace-map.sh` — invoked by `file-backlog-item.sh` to resolve the canonical backlog storage path for a given feature; must be present and executable

## Inputs / Outputs

### `list-backlog.sh`

- Input: `[--status <status>] [--feature <name[,name2]>] [--text]`
- Output (default): JSON array of `item.json` objects to stdout
- Output (`--text`): one line per item `NAME  [STATUS]  [PRIORITY]  TITLE` to stdout
- Exit: 0=ok, 2=usage

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

`file-backlog-item.sh` delegates storage path resolution to `workspace-map.sh`
(contract feature). Callers (rabbit-cage, other features) invoke these scripts
to file and manage their own backlog items; `file-backlog-item.sh` calls
`workspace-map.sh` internally to locate the canonical backlog directory for the
given feature and does not construct that path by convention.

The status enum (`open | in-progress | implemented | refused | reopened`) is
the canonical backlog terminology and is unified with the bug system's
terminal-state vocabulary (`refused`).

## Versioning

- Current version: `1.2.0`.
- Bump rules: minor bump on new fields added to item.json schema or new
  external invocations declared; major bump on breaking schema changes or
  removed fields.
- Changes in 1.2.0 (from 1.1.0):
  - New script `list-backlog.sh` added. Reads item.json files from centralized
    backlog storage. No breaking changes; existing callers unaffected.
- Changes in 1.1.0 (from 1.0.0):
  - New dependency declared: `workspace-map.sh` (contract feature) invoked by
    `file-backlog-item.sh` for storage path resolution. Callers are unaffected;
    the change is internal to `file-backlog-item.sh`.
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
