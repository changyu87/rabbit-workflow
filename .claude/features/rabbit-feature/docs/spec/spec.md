---
feature: rabbit-feature
version: 0.1.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.
status: active
---

# rabbit-feature — Spec

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Owns the `rabbit-feature-touch` orchestration skill. The skill ensures every
write, edit, delete, or add operation targeting a feature directory is gated
through the formal TDD state machine.

This feature is the **dispatcher-side surface** of feature work. The
**executor-side surface** — the TDD subagent, its 9-step cycle, the
`tdd-step.py` state machine, and the `dispatch-tdd-subagent.py` prompt
assembler — lives in the `tdd-subagent` feature. The two features are
coupled by an explicit cross-feature contract: `rabbit-feature` invokes
`tdd-subagent`'s scripts; `tdd-subagent` provides them.

## Scripting Tech Stack

All scripts and tests in this feature are Python 3. Bash is not used
anywhere in this feature. Test runner is `test/run.py`.

## Surface

- `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`
  — orchestration skill triggered on any feature write/edit/delete/add.
  In Cycle A this is a verbatim copy of
  `.claude/features/tdd-subagent/skills/rabbit-feature-touch/SKILL.md`;
  the deployed `.claude/skills/rabbit-feature-touch/` continues to be
  built from the `tdd-subagent` source until Cycle B re-points
  `build-contract.json`.
- `.claude/features/rabbit-feature/test/test-cross-feature-interface.py`
  — smoke test locking the cross-feature script interface.

## Invariants

1. `skills/rabbit-feature-touch/SKILL.md` content is a verbatim copy of
   `.claude/features/tdd-subagent/skills/rabbit-feature-touch/SKILL.md`.
   Verbatim means byte-identical in the body sections (the 7-step
   sequence, every Red Flag, and the Override Path). The YAML frontmatter
   `owner` field is the only permitted divergence (`rabbit-feature` here
   vs. `tdd-subagent` there); the `name`, `description`, `version`, and
   `deprecation_criterion` fields MUST match. This invariant holds until
   Cycle B retires the tdd-subagent source and re-points
   `build-contract.json`.

2. The skill invokes `tdd-subagent`'s `dispatch-tdd-subagent.py` and
   `tdd-step.py` as a hard cross-feature dependency declared in
   `contract.md` under `invokes.scripts`. The contract entry pins the
   expected CLI signature so any drift in the tdd-subagent script
   interface is caught by the smoke test in Invariant 3.

3. The cross-feature interface is locked by
   `test/test-cross-feature-interface.py`. The smoke test runs both:
   - `python3 .claude/features/tdd-subagent/scripts/tdd-step.py --help`
   - `python3 .claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py --help`
   Both invocations must exit 0 and print recognizable usage text. If
   either script's CLI surface changes (rename, removed flag, signature
   break), this test fails and `rabbit-feature` is forced into red state.

4. Cycle A does NOT update `build-contract.json` and does NOT delete the
   old skill source under
   `.claude/features/tdd-subagent/skills/rabbit-feature-touch/`. Those
   changes are deferred to Cycle B (the atomic switch). Until Cycle B
   commits, the deployed `.claude/skills/rabbit-feature-touch/` is
   sourced from `tdd-subagent` and `rabbit-feature`'s skill is dormant
   source only. This invariant guarantees zero duplicate-fire risk
   during the transition window.

## What this feature does NOT define

- The TDD subagent itself, its 9-step cycle, or the `tdd-step.py` state
  machine — owned by `tdd-subagent`.
- The build pipeline that copies skills into `.claude/skills/` — owned
  by `contract` via `build-contract.json`.
- Workspace structure declarations — owned by `contract` via
  `workspace-structure.json`.
- Scope resolution — owned by `rabbit-feature-scope`. (A future cycle
  may move `rabbit-feature-scope` into this feature; out of scope for
  Cycle A.)

## Tests

`test/run.py` runs the end-to-end suite. In Cycle A, the only test is
`test-cross-feature-interface.py` (Invariant 3).
