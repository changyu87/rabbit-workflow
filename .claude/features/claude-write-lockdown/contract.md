# Contract — claude-write-lockdown

## Reads

- `.claude/settings.json` (or path passed as positional arg) — for the
  detective script.

## Writes

- `.claude/settings.json` — this feature's installation step adds the
  deny rules. Subsequent operations of the feature (running the check
  script) are read-only.

## Invokes

- `jq` — for reading the deny array.
- `grep -Fx` — for fixed-string exact-line matches against required rules.

## Inputs / Outputs

### `scripts/check-lockdown-active.sh [path]`

- **Inputs:** optional path to a settings file (default `.claude/settings.json`).
- **Stdout:** `OK: lockdown rules present in <path>` on success.
- **Stderr:** `ERROR: missing deny rule: ...` (one per missing rule), then
  `FAIL: N required deny rule(s) missing in <path>`.
- **Exit:** `0` rules present; `1` rules missing; `2` invocation error.

## Cross-scope handoff

- **Adding more deny rules** (e.g. `Bash(rm -rf .claude/**)`) — separate
  PR. This feature only enforces the two `Write`/`Edit` rules; new rules
  are out of scope unless this feature's contract is amended.
- **Bypassing the lockdown for a one-off** — out of band, by editing
  `.claude/settings.local.json` (gitignored). The shared rules still
  apply unless explicitly overridden there.
- **Auditing `Bash`-level writes to `.claude/**`** — out of scope for
  v1.0. A future supervisory-hook feature may add this.

## Versioning

- Current version: `1.0.0`.
- Adding a new required deny rule (e.g. `NotebookEdit(.claude/**)`) is
  breaking for installations that previously passed the check; bump major
  and document migration.
- Removing a required deny rule is breaking (the lockdown weakens).
- Switching the path glob (e.g. `Write(.claude/**)` → `Write(.claude/*)`)
  is breaking and weakens enforcement.
