# Contract — feature-scaffolder

## Reads

- `$FEATURES_ROOT` (env, default `.claude/features`) — for `validate-all.sh`.
- `<root>/<name>/feature.json` — when validating each feature.
- The autodetected `feature-skeleton/scripts/validate-feature.sh` (executable
  bit checked at well-known relative paths).

## Writes

- `<root>/<name>/feature.json` — by `new-feature.sh`.
- `<root>/<name>/spec.md`, `contract.md` — by `new-feature.sh`.
- `<root>/<name>/test/run.sh` — by `new-feature.sh`.
- `<root>/<name>/{test,scripts}/` — directories created by `new-feature.sh`.

`<root>` defaults to whatever the user passes. Auto-created (`mkdir -p`)
if missing.

## Invokes

- `jq` — for JSON encoding in `feature.json` (via heredoc, so jq is
  not strictly required at scaffold time, only when the user later edits).
- `feature-skeleton/scripts/validate-feature.sh` (autodetected, optional).
- Standard utilities: `mkdir`, `chmod`, `date`, `cat`, `grep`, `basename`.

## Inputs / Outputs

### `new-feature.sh <root> <name> [--owner N] [--description D]`

- **Stdout:** `scaffolded: <target>` and (if validator reachable) a
  `validated: ...` or `WARNING: ...` line.
- **Stderr:** `ERROR: ...` on validation/refusal; `WARNING: ...` if the
  scaffolded skeleton fails strict validation (expected for fresh skeletons).
- **Exit:** `0` success; `1` invalid name or target exists; `2` invocation error.
- **Side effects:** creates a directory tree with 4 files.

### `validate-all.sh [<root>] [--validator <path>]`

- **Stdout:** per-feature `PASS:` / `FAIL:` line, then summary.
- **Stderr:** `failed features: ...` summary on non-zero exit.
- **Exit:** `0` all pass / vacuous; `1` one or more fail; `2` validator
  not found.
- **Side effects:** none (read-only).

## Cross-scope handoff

- **Editing the scaffolded files after creation** — the dispatcher (the
  user, or the rabbit-breeder if dispatched onto the new scope) does
  this. The scope-guard hook applies once `feature.json` exists in the
  directory; the dispatcher must touch `<scope>/.rabbit-scope-active`
  before further writes.
- **Filing a bug** — use `bug-filing/scripts/file-bug.sh` with `$BUG_ROOT`
  pointed at the relevant bugs directory (could be `.claude/docs/bugs/`
  or `projA/bugs/` — the script is path-agnostic).
- **Tracking TDD state** — use `tdd-state-machine/scripts/tdd-step.sh`
  with the feature path. State-machine scripts are path-agnostic.

## Versioning

- Current version: `1.1.0` (bumped from 1.0.0 — same scripts but reframed
  to drop user/dev mode language; behavior unchanged).
- Adding a new optional flag to `new-feature.sh` (e.g. `--initial-state`,
  `--skip-test-stub`) is non-breaking.
- Changing the scaffolded `feature.json` shape is breaking (downstream
  expectations diverge from `feature-skeleton`).
- Removing the auto-detect logic for the validator is breaking.
