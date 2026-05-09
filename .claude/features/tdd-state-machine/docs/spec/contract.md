# Contract — tdd-state-machine

## Reads

- `<feature-dir>/feature.json` — `tdd_state`, `name`, `version`, `owner`,
  `status`, `deprecation`, `contract` fields.
- `<feature-dir>/test/run.sh` — invoked by `tdd-drift-check.sh` to compare
  reality against the claimed state.

## Writes

- `<feature-dir>/feature.json` — only the `tdd_state` and `updated` fields.
  All other fields are left untouched (jq surgical update).

## Invokes

- `jq` — for JSON parsing and writing.
- `bash <feature-dir>/test/run.sh` — invoked by drift check.

## Inputs / Outputs

### `tdd-step.sh`

- **stdin:** none
- **stdout:** current state (`show`), next state (`next`), allowed next
  states (`transitions`), or transition message like `spec -> test-red`.
- **stderr:** error messages on denied or invalid transitions; `FORCED:`
  prefix when `--force` is used.
- **exit:** `0` (success), `1` (denied/invalid), `2` (bad invocation).

### `tdd-drift-check.sh`

- **stdin:** none
- **stdout:** `OK (...)` summary on consistent state.
- **stderr:** `DRIFT: ...` or `ERROR: ...`
- **exit:** `0` (ok), `1` (drift), `2` (bad invocation or missing files).

### `tdd-context.sh`

- **stdin:** none
- **stdout:** JSON block (default) or formatted text (`--text`) with fields:
  `feature_name`, `current_state`, `allowed_next_states[]`, `guidance`,
  `deprecation_criterion`, `contract`, `version`, `owner`, `status`.
- **exit:** `0` (success), `2` (bad invocation).

## Cross-scope handoff

- **Schema-shape violations** in `feature.json` are out of scope. Caller
  should run `feature-skeleton/scripts/validate-feature.sh` first; this
  feature assumes the schema is valid.
- **Writing the `feature.json` file at all** in a locked-down environment
  must go through the `breeder` subagent; this feature only does the in-place
  jq edit.
- **Reporting a drift as a bug** is the caller's responsibility — see the
  `bug-filing` feature.

## Versioning

- Current version: `1.0.0`.
- Adding a new state is a breaking change (downstream consumers parse the
  enum). Bump major and document migration path for any feature still in an
  obsoleted state.
- Adding a new sub-command to `tdd-step.sh` is non-breaking (additive).
- Changing the JSON shape of `tdd-context.sh` is breaking (subagent prompts
  parse it).
