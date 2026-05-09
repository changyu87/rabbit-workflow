# feature-skeleton

> **Note:** This file is the human-readable view. The machine-first source of
> truth is [`feature.json`](./feature.json). If they drift, `feature.json` wins.

## Purpose

Defines and enforces the layout of every feature in `.claude/features/<name>/`.
Without this skeleton, "feature" is a vague noun. With it, every feature has
the same shape, the same lifecycle hooks, and the same validation surface.

## Schema

Every feature directory MUST contain:

```
.claude/features/<name>/
├── feature.json   # machine-first manifest (REQUIRED, see fields below)
├── spec.md        # human-readable spec (REQUIRED)
├── contract.md    # what this feature reads, writes, invokes (REQUIRED)
├── test/          # end-to-end tests, runnable unattended (REQUIRED)
│   └── run.sh     # entrypoint; exit 0 = pass; exit non-zero = fail
└── scripts/       # optional, feature-local executables
```

### `feature.json` required fields

| Field                       | Type    | Notes                                                      |
|-----------------------------|---------|------------------------------------------------------------|
| `name`                      | string  | Lowercase kebab-case; must equal directory name            |
| `version`                   | string  | Semver (X.Y.Z)                                             |
| `owner.primary`             | string  | Named individual or team                                   |
| `owner.contact`             | string  | Optional; URL or email                                     |
| `status`                    | enum    | `active` \| `experimental` \| `deprecated` \| `archived`   |
| `tdd_state`                 | enum    | See "TDD states" below                                     |
| `deprecation.criterion`     | string  | Non-empty; the condition under which this is superseded    |
| `deprecation.successor`     | string? | Name of replacement feature, or `null`                     |
| `contract.reads`            | array   | Paths or patterns this feature reads                       |
| `contract.writes`           | array   | Paths or patterns this feature writes                      |
| `contract.invokes`          | array   | Other features, scripts, or tools this feature invokes     |
| `created`                   | string  | YYYY-MM-DD                                                 |
| `updated`                   | string  | YYYY-MM-DD                                                 |

### TDD states

`spec` → `test-red` → `impl` → `test-green` → `review` → `merged` → `deprecated`

Forward-only. Skipping is a hard ban (enforced by the `tdd-state-machine`
feature). The `tdd_state` field in `feature.json` is the canonical state.

## Validator

`scripts/validate-feature.sh <feature-dir>` returns:

| Exit | Meaning                                  |
|------|------------------------------------------|
| 0    | Conforms to schema                       |
| 1    | One or more violations (details on stderr) |
| 2    | Bad invocation (missing arg, bad path)   |

This script is the deterministic enforcement of the schema. If you find
yourself wanting to add a "soft" check that only warns, file a bug instead and
extend the validator with the new hard check.

## What this feature does NOT define

- **State transitions and gating.** That is `tdd-state-machine`.
- **Who may write to `.claude/`**. That is `breeder` + `claude-write-lockdown`.
- **Bug filing format.** That is `bug-filing`.
- **Branch / PR discipline.** That is `branch-per-feature` (under `hard-rules`).

Bounded scope: this feature owns the schema. Nothing more.

## Tests

`test/run.sh` runs `test/test-validator.sh`, which builds 14 fixture cases in a
temp directory and asserts the validator's exit code and stderr. Includes a
self-test (t14) that runs the validator against this very feature's directory.
