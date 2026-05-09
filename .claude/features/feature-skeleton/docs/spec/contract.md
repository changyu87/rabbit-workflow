# Contract — feature-skeleton

## Reads

- `<feature-dir>/feature.json` — parsed; all required fields validated.
- `<feature-dir>/spec.md` — existence only.
- `<feature-dir>/contract.md` — existence only.
- `<feature-dir>/test/run.sh` — existence and executable bit only.
- `<feature-dir>/test/` — existence only.

## Writes

None. The validator is read-only by design.

## Invokes

- `jq` — required external tool for JSON parsing. If `jq` is absent the
  validator's exit code becomes `127` (bash "command not found"), which is
  surfaced as a test failure rather than a silent pass.

## Inputs

- A single positional arg: path to the feature directory.

## Outputs

- **stdout:** `PASS: <dir>` on success.
- **stderr:** `ERROR: ...` per violation, then `FAIL: N error(s) in <dir>`.
- **exit code:** `0` (pass), `1` (validation error), `2` (invocation error).

## Cross-scope handoff

If a caller wants to:

- **Enforce TDD step transitions** → invoke the `tdd-state-machine` feature,
  not this one. This validator only checks that the `tdd_state` field is in
  the allowed enum, not that the value is _correct_ for the feature's actual
  state on disk.
- **File a bug found by validation** → the validator does not file bugs. The
  caller (or a higher-level orchestrator) must invoke the `bug-filing`
  feature with the validator's stderr as input.
- **Write to `<feature-dir>`** → must go through the `breeder` subagent once
  `claude-write-lockdown` is active.

## Versioning

- Current version: `1.0.0`.
- Breaking changes (removing or renaming a required field) require a major
  bump and a coexistence window per `work-guide.md` §3.
- Adding a new required field is breaking; adding an optional field is not.
