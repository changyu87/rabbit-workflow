# Contract — rabbit-backlog

## Reads

- `<item-dir>/item.json` — backlog item status and history (via `backlog-item-status.sh get`)

## Writes

- `<item-dir>/item.json` — created by `file-backlog-item.sh`; mutated by `backlog-item-status.sh set`
- `docs/backlog/<ITEM-ID>/item.json` — canonical storage location for items filed in this feature

## Invokes

- `jq` — JSON manipulation for item.json read/write

## Inputs / Outputs

### `file-backlog-item.sh`

- Input: `--name <id>`, `--title <str>`, `--priority <level>`, `--owner <str>`, `--dir <path>`
- Output: path of created item directory (stdout); `item.json` written to `<dir>/item.json`
- Exit: 0=created, 1=error, 2=usage

### `backlog-item-status.sh`

- Input (get): `<item-dir>`
- Output (get): current status string (stdout)
- Input (set): `<item-dir> <new-status> [--reason <text>]`
- Output (set): transition string `"<old> -> <new>"` (stdout); `item.json` mutated in-place
- Exit: 0=ok, 1=error, 2=usage

## Cross-scope handoff

This feature does not delegate to other features. Callers (rabbit-cage, other
features) invoke these scripts to file and manage their own backlog items.
The `--dir` argument determines where items are stored; this feature does not
enforce a storage path on callers.

## Versioning

- Current version: `0.1.0`.
- Bump rules: minor bump on new fields added to item.json schema; major bump on breaking schema changes or removed fields.
- Deprecation criterion: when rabbit features are retired or a unified project management system replaces file-based backlog.
