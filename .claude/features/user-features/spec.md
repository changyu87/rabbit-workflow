# user-features

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).

## Purpose

Makes the rabbit feature schema usable on **any** project, not just on
rabbit's own `.claude/features/` directory. When a user installs rabbit
into their workspace and wants to start applying the same disciplined
feature-oriented workflow to their own code, this feature ships:

- A **scaffolder** (`scripts/new-feature.sh`) that creates a properly-shaped
  feature directory at any path.
- A **sweep validator** (`scripts/validate-all.sh`) that runs the
  feature-skeleton validator across every feature in a root.
- An **`$FEATURES_ROOT` env override** so user-mode invocations don't have
  to repeat the path.

This satisfies the user's request (rule #11): "for any non-rabbit feature,
such as user owned project, follow the same pattern as #5, #6 and #8 but
under a user specified local folder such as projA/features/."

## How user mode works

After `install.sh` puts `.claude/` and `CLAUDE.md` into the user's
workspace, the user can apply the rabbit pattern to their own project at
any path. Example:

```bash
# Scaffold a new feature in the user's own project
bash .claude/features/user-features/scripts/new-feature.sh \
    projA/features auth-redirect --owner alice

# Sweep all features in projA
FEATURES_ROOT=projA/features \
    bash .claude/features/user-features/scripts/validate-all.sh
```

The scaffolded feature has:

- `feature.json` — `tdd_state: spec`, `status: experimental`,
  `version: 0.1.0`, `owner.primary: $USER` (or `--owner` value).
- `spec.md`, `contract.md` — LLM-prose templates with `TODO:` placeholders.
- `test/run.sh` — placeholder that exits non-zero (honest TDD red, since
  no tests are authored yet).

The user is expected to:

1. Edit the placeholders.
2. Author real tests in `test/test-*.sh` and `test/run.sh`.
3. Use `tdd-state-machine/scripts/tdd-step.sh transition <dir> test-red`
   once tests exist and fail.
4. Implement, advance to `impl`, then `test-green`, etc.

## Scripts

### `scripts/new-feature.sh`

```
new-feature.sh <root> <name> [--owner <name>] [--description <desc>]
```

Validates `<name>` (lowercase kebab-case, max 50 chars), creates `<root>/`
if missing (mkdir -p), refuses to overwrite an existing `<root>/<name>/`.
After scaffolding, optionally invokes `feature-skeleton/scripts/
validate-feature.sh` if reachable, and reports PASS/WARNING. The
WARNING is expected — the scaffolded feature has TODO placeholders that
won't pass strict validation until filled in.

Exit: `0` success, `1` invalid name or target exists, `2` invocation error.

### `scripts/validate-all.sh`

```
validate-all.sh [<features-root>] [--validator <path>]
```

Defaults `<features-root>` from `$FEATURES_ROOT` env, then `.claude/features`.
Auto-detects the feature-skeleton validator (well-known relative paths) if
`--validator` is omitted. Iterates every `*/` subdir of the root that
contains a `feature.json`, runs the validator on each, prints a per-feature
PASS/FAIL line, and aggregates a summary.

Exit: `0` all pass (or vacuous), `1` one or more fail, `2` validator
not found.

## Honest scope notes

- The scaffolded `test/run.sh` exits non-zero by design. This is honest TDD
  red: a feature with no real tests should not silently "pass". The user
  authors real tests, then transitions `tdd_state` to `test-red` (which
  also expects non-zero) and onward.
- The scripts intentionally do NOT honor the `claude-write-lockdown` deny
  rules — those rules only constrain `Write`/`Edit` tool calls inside
  `.claude/`. User-mode features live OUTSIDE `.claude/` (e.g. at
  `projA/features/`), where the lockdown does not apply.
- The breeder subagent's "sole writer to `.claude/`" rule does NOT extend
  to user-mode feature paths. The user controls their own project.

## What this feature does NOT define

- The schema itself — that is `feature-skeleton`.
- TDD state transitions — that is `tdd-state-machine`.
- Bug filing for user features — `bug-filing` works for any `$BUG_ROOT`,
  including user-project paths.
- Slash commands or subagent wrappers around these scripts — out of scope
  for v1; users invoke the bash directly.

## Tests

`test/run.sh` runs two test files (16 cases):

- `test-new-feature.sh` (10) — scaffold creates required files; default
  field values; test/run.sh executable and red; refuses overwrite; rejects
  invalid names; `--owner` honored; works at arbitrary paths; auto-creates
  parent dirs; contract.md has required headers.
- `test-validate-all.sh` (6) — empty root vacuous pass; all-pass; one-fail
  detection; non-feature subdirs skipped; `$FEATURES_ROOT` env honored;
  missing validator reported clearly.
