# Contract — hard-rules

## Reads

- `git rev-parse --git-dir`, `git rev-parse --abbrev-ref HEAD` —
  for `check-no-main-edits.sh`.
- `$AGENTS_DIR/*.md` (default: `.claude/agents/*.md`) — for
  `check-opus-for-planning-agents.sh`.
- `<feature-dir>/test/*.sh` — for `check-tests-non-interactive.sh`.

## Writes

**None.** All three checks are read-only.

## Invokes

- `git`, `awk`, `sed`, `grep`, `find` — standard shell utilities.

## Inputs / Outputs

### `check-no-main-edits.sh`

- **Inputs:** none (reads from current working directory's git context).
- **Stdout:** `OK: on '<branch>' (not main)` on success.
- **Stderr:** `REJECTED: ...` or `ERROR: ...`.
- **Exit:** `0` not on main; `1` on main/master/trunk/develop; `2` not a repo.

### `check-opus-for-planning-agents.sh`

- **Inputs:** none (reads `$AGENTS_DIR`, default `.claude/agents`).
- **Stdout:** `OK: ...` on success.
- **Stderr:** one `VIOLATION:` line per non-conformant agent, then `FAIL: N ...`.
- **Exit:** `0` all conformant or empty agents dir; `1` one or more violations.

### `check-tests-non-interactive.sh`

- **Inputs:** `<feature-dir>` (positional).
- **Stdout:** `OK: ...` on success.
- **Stderr:** `VIOLATION: <file> uses '...'` per offending file, then `FAIL: ...`.
- **Exit:** `0` no violations; `1` violations found; `2` bad invocation.

## Cross-scope handoff

- These checks are **detective** — they identify violations. They do not
  fix them. The caller (typically a CI step, a pre-commit hook, or the
  breeder before committing) decides what to do on a non-zero exit.
- For TDD-related drift detection, use `tdd-state-machine/scripts/
  tdd-drift-check.sh`. This feature does not duplicate that logic.

## Versioning

- Current version: `1.0.0`.
- Adding a new check script is non-breaking (additive).
- Adding a new pattern to an existing check (e.g. a new forbidden
  interactive construct) is non-breaking unless it would falsely fail
  existing-but-conformant code; in that case bump minor and announce.
- Tightening the planning-agent regex (more matches) is breaking for any
  agent whose description newly hits the regex without `model: opus`.
