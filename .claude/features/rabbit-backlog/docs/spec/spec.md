# rabbit-backlog

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns backlog item filing and lifecycle for all rabbit features. Provides three
scripts: `file-backlog-item.py` (creates new backlog items),
`backlog-item-status.py` (reads and transitions item status), and
`list-backlog.py` (lists backlog items with optional filtering).

All runtime scripts and test harnesses are implemented in Python 3. No shell
scripts (`.sh`) exist in this feature.

Backlog items live under `docs/backlog/<ITEM-ID>/item.json`. The schema and
valid status transitions are declared in `docs/backlog/backlog-contract.md`.

Item lifecycle is version-controlled: `file-backlog-item.py` commits the new
`item.json` to git after creation, and every `backlog-item-status.py set`
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

### `file-backlog-item.py`

Creates a new backlog item directory with an `item.json` in initial `open`
status, then `git add`s and `git commit`s the new file.

```
file-backlog-item.py --name <item-id> --title <title> \
                     [--priority low|medium|high|critical] \
                     [--owner <name>] --dir <item-dir>
```

### `backlog-item-status.py`

Reads or transitions an item's status. Every `set` invocation requires a
`--reason` argument and commits the mutated `item.json` to git.

```
backlog-item-status.py get <item-dir>
backlog-item-status.py set <item-dir> <new-status> --reason <text> \
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

### `list-backlog.py`

Lists backlog items from centralized `.claude/backlogs/` storage with optional
filtering.

```
list-backlog.py                         # all items, JSON array
list-backlog.py --status open|in-progress|implemented|refused|reopened
list-backlog.py --feature NAME[,NAME2]  # only named features (comma-separated)
list-backlog.py --text                  # human-readable: NAME  [STATUS]  [PRIORITY]  TITLE per line
list-backlog.py -h|--help
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
- **Branch guard:** `file-backlog-item.py` MUST detect the current git branch
  via `git branch --show-current`. If the branch is not `main`, the script
  MUST print a warning to stderr. In interactive environments (`/dev/tty`
  available), the script MUST read an explicit confirmation; if the user does
  not confirm (types anything other than `y` or `yes`), the script MUST exit
  non-zero without creating any item. In non-interactive environments (no
  `/dev/tty`), the script MUST also exit non-zero (cannot obtain confirmation).

### feature.json Surface Invariants

- `surface.skills` MUST be `[]` (empty array). Skills are now managed via
  explicit copy-file entries in `build-contract.json`. The `surface.skills`
  field in `feature.json` is the retired mechanism and must not be populated.

### Working Protocol Invariants

The Working Protocol in `skills/rabbit-backlog/SKILL.md` MUST include a
user-decision gate after the eval subagent returns its verdict:

- After the eval subagent returns `valid` or `stale/invalid`, the skill MUST
  present the user with a summary of the verdict and any recommendation before
  taking action.
- The skill MUST then explicitly ask the user whether to refuse/cancel the item
  or proceed to work it via `rabbit-feature-touch`.
- The skill MUST NOT dispatch `rabbit-feature-touch` until the user confirms.

### SKILL.md Documentation Invariants

The `skills/rabbit-backlog/SKILL.md` (deployed to `.claude/skills/rabbit-backlog/SKILL.md`)
MUST document `list-backlog.sh` with the same completeness as `rabbit-bug` SKILL.md
documents `list-bugs.sh`. Specifically:

- A `list-backlog.py` section with a **Usage** block showing all flags.
- A **Parameters** table listing every flag, whether it is required, and its description.
- At least three **Example** invocations covering: no-args JSON, `--text`, `--status`,
  and `--feature` (with comma-separated values).

## Dependencies

### `workspace-map.py` (from contract)

`file-backlog-item.py` invokes `workspace-map.py` (located at
`.claude/features/contract/scripts/workspace-map.py`) to resolve the canonical
backlog storage path for a given feature name. The scripts do NOT construct
the path by convention — they delegate path resolution to `workspace-map.py`.

`backlog-item-status.py` does not invoke `workspace-map.py` directly; callers
pass a resolved `<item-dir>` path. Path resolution happens upstream at filing
time via `file-backlog-item.py`.

## What this feature does NOT define

- Bug filing (`docs/bugs/`) — that remains within each feature's own scope
  (managed by `file-bug.py` in rabbit-cage).
- Feature scaffolding — owned by rabbit-cage.
- TDD state machine — owned by `tdd-subagent`.
- Backlog storage path convention — owned by `workspace-map.py` in contract.

## Tests

`test/run.py` runs the end-to-end suite. All tests must pass when
`tdd_state` is `test-green`.
