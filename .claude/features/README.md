# Features

A **feature** is a unit of capability in the rabbit workflow. Each feature lives
in its own directory under `.claude/features/<name>/` and bundles:

- Its **structured manifest** (`feature.json`) — source of truth, parsed by
  deterministic tools (`jq`, validators).
- Its **prose spec** (`spec.md`) — derived view written for LLM consumption,
  never authored alone.
- Its **contract** (`contract.md`) — what it reads, writes, and invokes (also
  prose, also LLM-targeted).
- Its **end-to-end tests** (`test/run.sh` + supporting scripts) — runnable
  unattended; pass/fail by exit code.
- Optional `scripts/` — feature-local executables (validators, runners, etc.).

This layout is not optional. It is the schema enforced by
`contract/scripts/validate-feature.sh`.

> **All artifacts in rabbit are machine-targeted.** `feature.json` targets
> deterministic parsers; `spec.md` and `contract.md` target LLMs. The "prose"
> form exists because LLM context windows are narrow and structured JSON is
> low-density for narrative — not because there is a human reader. A human
> *can* read either, but neither is *authored for* a human.

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
  authored; `spec.md` is the LLM-prose view of the same information. If they
  drift, `feature.json` wins.
- **Never edit a feature outside a branch + PR** (see R1 in CLAUDE.md).
- **All feature writes go through a dispatched subagent** via `dispatch-feature-edit.sh` — the main session never edits directly (see Workflow Rules in CLAUDE.md).
