# Features

A **feature** is a unit of capability in the rabbit workflow. Each feature lives
in its own directory under `.claude/features/<name>/` and bundles:

- Its **machine-first manifest** (`feature.json`) — the source of truth.
- Its **human-readable spec** (`spec.md`) — derived view, never authored alone.
- Its **contract** (`contract.md`) — what it reads, writes, and invokes.
- Its **end-to-end tests** (`test/run.sh` + supporting scripts) — runnable
  unattended; pass/fail by exit code.
- Optional `scripts/` — feature-local executables (validators, runners, etc.).

This layout is not optional. It is the schema enforced by
`feature-skeleton/scripts/validate-feature.sh`.

## Lifecycle (TDD steps)

Each feature carries an explicit `tdd_state` field in `feature.json`. Allowed
values, in order:

| State        | Meaning                                                     |
|--------------|-------------------------------------------------------------|
| `spec`       | Spec written; tests not yet authored.                       |
| `test-red`   | Tests authored; all failing as expected.                    |
| `impl`       | Implementation in progress; tests transitioning.            |
| `test-green` | All tests passing.                                          |
| `review`     | PR open; under review.                                      |
| `merged`     | PR merged into main.                                        |
| `deprecated` | Superseded; consult `deprecation.successor`.                |

States advance forward only. Skipping is a hard ban (see `tdd-state-machine`).

## Ownership and deprecation

Per `philosophy.md` §3 (Designed Deprecation), every feature manifest declares:

- An **owner** (named individual or team).
- A **version** (semver).
- A **deprecation criterion** — the condition under which it will be superseded.

A feature without these is not a reliable feature.

## Authoring discipline

- **Never edit `feature.json` and `spec.md` in lockstep.** `feature.json` is
  authored; `spec.md` is the prose view of the same information. If they drift,
  `feature.json` wins.
- **Never edit a feature outside a branch + PR** (see `branch-per-feature`).
- **Never write to `.claude/**` outside the `breeder` subagent** once the
  lockdown is active (see `claude-write-lockdown`).
