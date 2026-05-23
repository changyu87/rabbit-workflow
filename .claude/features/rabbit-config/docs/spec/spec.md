---
feature: rabbit-config
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when the rabbit CLI exposes native configuration mutation that subsumes this feature
status: active
---

# rabbit-config — Spec

## Purpose

rabbit-config is the configuration manager of the rabbit workflow. It hosts
the `/rabbit-config` skill, which is the sole mutation surface for all
feature-declared configurables. At Stop and SessionStart, it iterates every
feature's CONFIGURATION declarations and emits alerts for active overrides.

rabbit-config holds no per-configurable integration code. Its behavior is
entirely driven by reading and dispatching the CONFIGURATION arrays declared
in other features' `feature.json` files.

## Surface

The deployed surface (produced by `install.py` running rabbit-config's MANIFEST):

- `.claude/skills/rabbit-config/SKILL.md` — skill manifest for the
  `/rabbit-config` subcommand interpreter

## Interpreter Behavior

The interpreter (`skills/rabbit-config/scripts/rabbit-config.py`) is invoked
as a CLI with the following argument structure:

```
rabbit-config.py <subcommand> [<value-or-action> [<template-value>]]
```

The interpreter:

1. Sets `repo_root` to `os.getcwd()` and imports `contract.lib.mutation`
   from `<repo_root>/.claude/features/contract`.
2. Enumerates every feature's `feature.json configuration` array in
   alphabetical order by feature directory name, skipping retired features
   and features with malformed or missing `feature.json`.
3. Matches `argv[1]` (subcommand) against the `subcommand` field of each
   CONFIGURATION entry; uses the first match.
4. For values-style configurables (`values` key present): resolves
   `values[argv[2]]` and dispatches the declared mutation API.
5. For actions-style configurables (`actions` key present): resolves
   `actions[argv[2]]` and dispatches the declared mutation API, passing
   `argv[3]` as the template value when the API args contain `{placeholder}`
   patterns.
6. Performs template substitution: any `{tool}` or `{command}` substring in
   the API args dict is replaced with `argv[3]` before dispatch.
7. For mutations other than `run_feature_script`: calls
   `mutation.<api>(**args, repo_root=<repo_root>)`.
   For `run_feature_script`: calls `mutation.run_feature_script(**args,
   feature_dir=<owning_feature_dir>)`.
8. Prints each `CheckResult.message` line to stdout. Exits 0 on
   `CheckResult.passed == True`, exits non-zero otherwise.

## Validation

If a CONFIGURATION entry declares a `validation` field, the interpreter
applies the rules to the user-supplied input before dispatching:

- `reject_prefix`: reject any input that starts with the declared prefix.
- `reject_chars`: reject any input that contains a character matching
  the declared character-class pattern.

Validation applies to `argv[2]` for values-style configurables and to
`argv[3]` (the template value) for actions-style configurables with templates.
Rejection exits non-zero with a descriptive message on stderr.

## Runtime Declarations

rabbit-config's own RUNTIME entries (`iterate_configurables_alerts` at Stop,
`iterate_configurables_banner` at SessionStart) are invoked by the
`stop-dispatcher.py` and `session-start-dispatcher.py` hooks (owned by
rabbit-cage). These APIs walk every feature's CONFIGURATION array and emit
`print_result` entries for any configurable whose current value matches its
`alert-on` field.

## Invariants

1. The MANIFEST contains exactly one entry:
   `{"api": "publish_skill", "args": {"source": "skills/rabbit-config/SKILL.md"}}`.
2. The RUNTIME.Stop array contains exactly one entry:
   `{"api": "iterate_configurables_alerts", "args": {}}`.
3. The RUNTIME.SessionStart array contains exactly one entry:
   `{"api": "iterate_configurables_banner", "args": {}}`.
4. The CONFIGURATION array is empty — rabbit-config has no configurables of
   its own; it operates on other features' declarations.
5. The skill manifest (`skills/rabbit-config/SKILL.md`) exists with non-empty
   content naming the subcommands discoverable from current CONFIGURATION
   declarations.
6. The interpreter (`skills/rabbit-config/scripts/rabbit-config.py`) begins
   with `#!/usr/bin/env python3` and uses Python 3 stdlib only.
7. On unknown subcommand, the interpreter exits non-zero and writes the
   unknown name and the list of known subcommands to stderr.
8. On valid values-style subcommand with valid value, the interpreter
   dispatches the declared `contract.lib.mutation` API and exits 0.
9. On valid actions-style subcommand with valid action, the interpreter
   dispatches the declared `contract.lib.mutation` API and exits 0.
10. Template substitution: `{tool}` and `{command}` in API args strings are
    replaced with `argv[3]` before dispatch. When templates are present in
    the API args and `argv[3]` is absent, the interpreter exits non-zero.
11. If `validation.reject_prefix` is declared, any input starting with that
    prefix is rejected with exit non-zero before dispatch.
12. If `validation.reject_chars` is declared, any input containing a
    character matching that pattern is rejected with exit non-zero before
    dispatch.
13. On values-style subcommand with unrecognized value, the interpreter exits
    non-zero and writes the valid values to stderr.
14. On actions-style subcommand with unrecognized action, the interpreter
    exits non-zero and writes the valid actions to stderr.
15. `rabbit-config` is declared as a required feature in
    `.claude/workspace-structure.json`.

## Tech Stack

Python 3 stdlib only. Imports `contract.lib.mutation` at runtime.
No Bash runtime dependency.

## Out of Scope

- Defining or storing configurables (each feature owns its own CONFIGURATION).
- Querying current configurable values (use the runtime API `iterate_configurables_alerts`
  or `iterate_configurables_banner`).
- Adding new mutation APIs to `contract.lib.mutation` (owned by the contract feature).
