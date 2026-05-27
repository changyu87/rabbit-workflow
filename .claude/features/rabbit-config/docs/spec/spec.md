---
feature: rabbit-config
version: 1.2.0
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

The two APIs differ in how many `print_result` entries they emit per active
configurable: `iterate_configurables_alerts` (Stop) emits one line per
active configurable; `iterate_configurables_banner` (SessionStart) emits two
lines per active configurable (alert text + revoke command) so that each
line is rendered with the brand prefix by the dispatcher and neither is
elided by the SessionStart TUI as a continuation line.

`_resolve_current_value` (in `contract.lib.runtime`) returns the
user-facing string value of a configurable so that `alert-on` comparison
operates on user-facing labels rather than raw stored values:

- `marker-file` storage: returns `'false'` if the marker file exists,
  `'true'` if it is absent.
- `json-key` storage: reads the raw value and translates it via
  reverse-lookup through the configurable's `values` map (matching the
  value whose `set_json_key` API would write that raw value); falls back
  to the raw string if no translation is found.
- `json-array` / `json-array-templated` storage: returns `None` (no scalar
  current value; alerts do not apply).

## Invariants

### Feature shape

1. The MANIFEST contains exactly one entry:
   `{"api": "publish_skill", "args": {"source": "skills/rabbit-config/SKILL.md"}}`.
2. The RUNTIME.Stop array contains exactly one entry:
   `{"api": "iterate_configurables_alerts", "args": {}}`.
3. The RUNTIME.SessionStart array contains exactly one entry:
   `{"api": "iterate_configurables_banner", "args": {}}`.
4. The CONFIGURATION array is empty — rabbit-config has no configurables of
   its own; it operates on other features' declarations.

### Skill surface

5. The skill manifest `skills/rabbit-config/SKILL.md` exists with non-empty
   content that names the `/rabbit-config` subcommand convention.
6. The SKILL.md frontmatter `description` field:
   (a) is present and at least 100 characters;
   (b) names every subcommand discoverable from the union of all active
   features' CONFIGURATION arrays;
   (c) contains the literal string `/rabbit-config`;
   (d) contains the disambiguation tokens `NOT` and `Claude Code permission`
   so that the description distinguishes rabbit configurables from
   platform-level concepts.
7. The interpreter `skills/rabbit-config/scripts/rabbit-config.py` begins
   with `#!/usr/bin/env python3` and uses Python 3 stdlib only.

### Interpreter dispatch

8. On unknown subcommand (or no-args), the interpreter exits non-zero and
   writes the unknown name (when present) and the list of known subcommands
   to stderr.
9. On a values-style subcommand with a valid value, the interpreter
   dispatches the declared `contract.lib.mutation` API and exits 0.
10. On an actions-style subcommand with a valid action, the interpreter
    dispatches the declared `contract.lib.mutation` API and exits 0.
11. Template substitution: `{tool}`, `{command}`, and `{value}` in API
    args strings are replaced with `argv[3]` before dispatch. When
    templates are present in the API args and `argv[3]` is absent, the
    interpreter exits non-zero.
12. If `validation.reject_prefix` is declared, any input starting with that
    prefix is rejected with exit non-zero before dispatch.
13. If `validation.reject_chars` is declared, any input containing a
    character matching that pattern is rejected with exit non-zero before
    dispatch.
14. On a values-style subcommand with unrecognized value, the interpreter
    exits non-zero and writes the valid values to stderr; on an
    actions-style subcommand with unrecognized action, the interpreter
    exits non-zero and writes the valid actions to stderr.

### Runtime emission

15. End-to-end via the deployed `stop-dispatcher.py`:
    `iterate_configurables_alerts` causes the dispatcher to emit exactly
    one brand-prefixed line per active configurable. This holds for both
    `marker-file` and `json-key` storage types (the `json-key` case relies
    on reverse-map translation of stored value to user-facing label).
16. End-to-end via the deployed `session-start-dispatcher.py`:
    `iterate_configurables_banner` causes the dispatcher to emit exactly
    two brand-prefixed lines per active configurable — the alert text line
    and a `revoke with: /rabbit-config <subcommand> <default>` line. Both
    lines begin with the rabbit brand prefix; no line is rendered as a
    multi-line continuation.

### Verification hygiene

17. Every test case in `test/` performs all filesystem mutations inside a
    `tempfile.TemporaryDirectory()` scope. No test writes to, deletes from,
    or otherwise mutates files in the live workspace under `.claude/`.

### Workspace declaration

18. `rabbit-config` is declared as a required feature in
    `.claude/workspace-structure.json` under `features.children`.

### Prompt-contract declaration

19. **`prompts` section declares the rabbit-config skill.**
    `feature.json` MUST declare a `prompts` array containing EXACTLY
    ONE entry: `{"id": "rabbit-config", "kind": "skill", "inject":
    [".claude/features/policy/philosophy.md",
    ".claude/features/policy/coding-rules.md"], "slots": ["args"]}`.
    The skill mutates `.claude/settings.local.json` and marker files —
    it is code-authoring — so it needs philosophy + coding-rules (not
    spec-rules). The matching template at
    `.claude/features/contract/templates/prompts/rabbit-config.txt`
    (passthrough ``args`` created by contract Inv 57 in Phase A.4)
    supplies the body via `slots: ["args"]` matching the template's
    ``args`` placeholder. Enforced by
    `test/test-prompts-declared.py` which loads `feature.json` and
    asserts the single entry exists with the exact id, kind, inject,
    and slots values.

## Tech Stack

Python 3 stdlib only. Imports `contract.lib.mutation` at runtime.
No Bash runtime dependency.

## Out of Scope

- Defining or storing configurables (each feature owns its own CONFIGURATION).
- Querying current configurable values (use the runtime API `iterate_configurables_alerts`
  or `iterate_configurables_banner`).
- Adding new mutation APIs to `contract.lib.mutation` (owned by the contract feature).
- The implementations of `iterate_configurables_alerts`,
  `iterate_configurables_banner`, `_resolve_current_value`, and
  `_reverse_map_json_value` live in `contract.lib.runtime` (owned by the
  contract feature); rabbit-config's spec pins their externally observable
  emission shape only.
