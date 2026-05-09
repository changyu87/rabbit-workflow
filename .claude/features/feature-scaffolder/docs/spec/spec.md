# feature-scaffolder

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).

## Purpose

Two scripts that create and validate feature directories at any path. Used
by callers (the main session, the rabbit-breeder, or the user directly)
who need to bootstrap a new feature or sweep-validate a tree of them.

The work model is **unified** — there is no "user mode" vs "rabbit dev mode".
The scaffolder works the same whether the path is `.claude/features/<x>/`
(rabbit improving itself) or `projA/features/<y>/` (a host project applying
the rabbit discipline) or anywhere else. Same scripts, same output, same
validation. Only the path differs.

## Scripts

### `scripts/new-feature.sh`

```
new-feature.sh <root> <name> [--owner <name>] [--description <desc>]
```

Validates `<name>` (lowercase kebab-case, max 50 chars), creates `<root>/`
if missing (mkdir -p), refuses to overwrite an existing `<root>/<name>/`.

Creates the standard skeleton:
- `feature.json` — `tdd_state: spec`, `status: experimental`,
  `version: 0.1.0`, `owner.primary: $USER` (or `--owner` value),
  `deprecation.criterion: TODO: ...`.
- `spec.md`, `contract.md` — LLM-prose templates with `TODO:` placeholders.
- `test/run.sh` — placeholder that exits non-zero (honest TDD red, since
  no real tests exist yet).

After scaffolding, optionally invokes
`feature-skeleton/scripts/validate-feature.sh` if reachable; reports
`PASS` or `WARNING`. The `WARNING` is expected on a fresh skeleton — the
TODO placeholders make strict validation fail until they are filled in.

Exit: `0` success, `1` invalid name or target exists, `2` invocation error.

### `scripts/validate-all.sh`

```
validate-all.sh [<features-root>] [--validator <path>]
```

Defaults `<features-root>` from `$FEATURES_ROOT` env, then `.claude/features`.
Auto-detects the feature-skeleton validator (well-known relative paths) if
`--validator` is omitted. Iterates every `*/` subdir of the root that
contains a `feature.json`, runs the validator on each, prints a per-feature
`PASS:` / `FAIL:` line, and aggregates a summary.

Exit: `0` all pass (or vacuous), `1` one or more fail, `2` validator
not found.

## Concrete examples

```bash
# Scaffold a new feature in your project
bash .claude/features/feature-scaffolder/scripts/new-feature.sh \
    projA/features auth-redirect --owner alice

# Sweep all features in projA
FEATURES_ROOT=projA/features \
    bash .claude/features/feature-scaffolder/scripts/validate-all.sh

# Same scripts, applied to rabbit's own .claude/features/
bash .claude/features/feature-scaffolder/scripts/new-feature.sh \
    .claude/features new-rabbit-feature --owner rabbit-team

# Sweep rabbit's own features (default $FEATURES_ROOT is .claude/features)
bash .claude/features/feature-scaffolder/scripts/validate-all.sh
```

## Honest scope notes

- The scaffolded `test/run.sh` exits non-zero by design. A feature with
  no real tests should not silently "pass". The user authors real tests,
  then transitions `tdd_state` to `test-red` (which expects failing tests)
  and onward.
- The scripts themselves are NOT subject to the `scope-guard` hook —
  they're invoked directly by the user or the dispatcher, not by an
  in-flight breeder. When THEY write to a feature dir, the dispatcher (or
  the user) is responsible for setting `<scope>/.rabbit-scope-active`
  beforehand if that path is under the active scope-guard discipline.
- For scaffolding into a fresh path that doesn't yet have a `feature.json`,
  the scope-guard hook treats it as "not a feature dir" and allows the
  write. After `new-feature.sh` creates `feature.json`, subsequent writes
  will be subject to the marker check. The dispatcher should set the marker
  immediately after scaffolding if it intends to do further writes.

## What this feature does NOT define

- The schema itself — that is `feature-skeleton`.
- TDD state transitions — that is `tdd-state-machine`.
- Bug filing — `bug-filing` works for any `$BUG_ROOT`.
- Slash commands or subagent wrappers around these scripts — out of scope
  for v1; callers invoke the bash directly.
- The scope-guard hook — that is `scope-guard` (PR #12).

## Tests

`test/run.sh` runs two test files (16 cases):

- `test-new-feature.sh` (10) — scaffold creates required files; default
  field values; test/run.sh executable and red; refuses overwrite; rejects
  invalid names; `--owner` honored; works at arbitrary paths; auto-creates
  parent dirs; contract.md has required headers.
- `test-validate-all.sh` (6) — empty root vacuous pass; all-pass; one-fail
  detection; non-feature subdirs skipped; `$FEATURES_ROOT` env honored;
  missing validator reported clearly.
