---
feature: rabbit-feature
version: 1.1.0
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

The skill is **dispatcher-side**: it resolves scope, creates branches,
invokes spec authoring, surfaces the human-approval gate, dispatches TDD
subagents, and verifies HANDOFFs. The **executor-side** — the TDD subagent,
its 9-step cycle, the `tdd-step.py` state machine, and the
`dispatch-tdd-subagent.py` prompt assembler — lives in the `tdd-subagent`
feature. The two features are coupled by an explicit cross-feature
contract: `rabbit-feature` invokes `tdd-subagent`'s scripts;
`tdd-subagent` provides them.

## Scripting Tech Stack

All scripts and tests in this feature are Python 3. Bash is not used
anywhere in this feature. Test runner is `test/run.py`.

## Surface

- `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`
  — orchestration skill triggered on any feature write/edit/delete/add.
  This is the authoritative source for the deployed
  `.claude/skills/rabbit-feature-touch/SKILL.md`, populated via the
  `build-contract.json` copy-file entry.
- `.claude/features/rabbit-feature/test/test-cross-feature-interface.py`
  — smoke test locking the cross-feature script interface.
- `.claude/features/rabbit-feature/test/test-build-source-points-to-rabbit-feature.py`
  — end-to-end test asserting `build-contract.json` deploys the skill
  from this feature (not from `tdd-subagent`).

## Invariants

1. `skills/rabbit-feature-touch/SKILL.md` is the authoritative source for
   the deployed `.claude/skills/rabbit-feature-touch/SKILL.md`, populated
   via the `build-contract.json` copy-file entry whose `source` field
   points at `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`.

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

4. The build source for the deployed skill is locked by
   `test/test-build-source-points-to-rabbit-feature.py`. The test parses
   `.claude/features/contract/build-contract.json`, locates the entry
   named `skills/rabbit-feature-touch/SKILL.md`, and asserts its
   `source` field equals
   `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`.
   If anything re-points the build to a different source, this test fails.

5. In `rabbit-feature-touch` Step 1 (normal mode), scope resolution is
   performed by invoking the `rabbit-feature-scope` Skill via the Skill
   tool (`Skill("rabbit-feature-scope", args: "<request>")`), NOT by
   shelling out to `resolve-scope.py` directly. The Skill emits a prompt
   for caller dispatch; the caller parses the JSON response
   `{"features": [...], "rationale": "..."}` to drive parallel dispatch.

6. `rabbit-feature-touch` SKILL.md describes a **seven-step** unified
   sequence (not six). The seven steps in order are: (1) Scope
   Resolution, (2) Create Branch, (3) Spec Authoring, (4) Human
   Approval, (5) Dispatch TDD Subagents, (6) Collect and Verify
   HANDOFFs, (7) PR / Hand Off. Both the overview heading and every
   step heading reflect this numbering.

7. Step 4 (Human Approval) is a **dispatcher-side** gate that lives in
   the main session, not inside the TDD subagent. The dispatcher reads
   the impl-suggestion JSON for each affected feature, surfaces a
   summary (request, spec changes, affected files, implementation
   approach) to the user, and waits for explicit approval before
   proceeding to Step 5 (Dispatch). The gate exists at the dispatcher
   because dispatched subagents run to completion and cannot pause for
   interactive user input.

8. Step 4 (Human Approval) is bypassable only when the user has
   explicitly requested autonomous execution. The bypass authorization
   is encoded as a hard file marker `.rabbit-human-approval-bypass` at
   the repo root, managed via the `/rabbit-config human-approval
   true|false` skill (owned by rabbit-cage; `false` writes the marker
   — gate disabled — and `true` deletes it). At Step 4, the dispatcher
   MUST check for this marker file: if it exists, the dispatcher skips
   the in-conversation wait, emits a visible `[rabbit]` warning naming
   the bypass marker and the path `/rabbit-config human-approval true`
   to revoke it, and passes `--human-approval-gate false` to the
   Step 5 `dispatch-tdd-subagent.py` invocation. If the marker is
   absent, the dispatcher surfaces the impl-suggestion summary and
   waits for explicit user approval.

9. The dispatcher-side Step 4 check for `.rabbit-human-approval-bypass`
   MUST be documented in `rabbit-feature-touch` SKILL.md as the first
   action of Step 4 (Human Approval), BEFORE any in-conversation wait
   or impl-suggestion surfacing. When the marker is found, the warning
   emitted to the user MUST name both the marker path
   (`.rabbit-human-approval-bypass`) and the revoke command
   (`/rabbit-config human-approval true`) so the user can audit and
   revoke without searching. This invariant constrains SKILL.md
   documentation content; the underlying behaviour is Inv 8.
   (Re-homed from tdd-subagent Inv 15 v1.19.0 per BACKLOG-12.)

10. `rabbit-feature-touch` SKILL.md Red Flags section MUST include the
    rule: the main session orchestrator MUST NOT use Write or Edit
    tools on any file under `.claude/features/`. All feature-code
    edits are the TDD subagent's job, performed under an active scope
    marker. The main session role is orchestration only — resolve
    scope, create branch, invoke rabbit-spec, surface impl-suggestion,
    dispatch subagent, verify HANDOFF. Exceptions exist for explicit
    confirm-token overrides (see Override Path — tdd-subagent
    Confirm-Token Bypass Path) and for `spec.md` writes under the
    scope-guard path-pattern allowlist (rabbit-cage Inv 20) which are
    invoked by `rabbit-spec` during Step 3.
    (Re-homed from tdd-subagent Inv 17 v1.19.0 per BACKLOG-12.)

11. `rabbit-feature-touch` SKILL.md Red Flags section MUST include the
    rule: the main session MUST NOT create `.rabbit-scope-active`
    (global) or `.rabbit-scope-active-<feature>` (per-feature) scope
    markers at the repo root. Scope markers are exclusively the TDD
    subagent's responsibility, written as the first action at LOCK
    (Step 3 of the subagent's named steps). Main-session-authored
    markers bypass scope-guard's intended boundary and have caused
    constitution violations (PR #93). This rule is distinct from
    tdd-subagent Inv 14 (which prohibits the SUBAGENT from creating
    out-of-scope markers): this invariant prohibits the MAIN SESSION
    from creating any marker at all.
    (Re-homed from tdd-subagent Inv 18 v1.19.0 per BACKLOG-12.)

12. `rabbit-feature-touch` SKILL.md B/B mode MUST read the item JSON
    from `<item-dir>/item.json`, never from `<item-dir>/bug.json`. The
    rabbit-file schema uses `item.json` for both bug and backlog types
    (unified storage); `bug.json` is a legacy path that no longer
    exists. The B/B mode `related_feature` extraction MUST use Python
    3 (always available; `jq` is not a declared dependency of this
    feature):
    `FEATURE=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('related_feature',''))" <item-dir>/item.json)`.
    This invariant constrains tdd-subagent's data contract with the
    B/B caller, but the SKILL.md content lives here.
    (Re-homed from tdd-subagent Inv 26 v1.19.0 per BACKLOG-12.)

## What this feature does NOT define

- The TDD subagent itself, its 9-step cycle, or the `tdd-step.py` state
  machine — owned by `tdd-subagent`.
- The build pipeline that copies skills into `.claude/skills/` — owned
  by `contract` via `build-contract.json` (this feature consumes the
  build via the copy-file entry but does not define it).
- Workspace structure declarations — owned by `contract` via
  `workspace-structure.json`.
- Scope resolution — owned by `rabbit-feature-scope`.

## Tests

`test/run.py` runs the end-to-end suite:
- `test-cross-feature-interface.py` — Invariant 3
- `test-build-source-points-to-rabbit-feature.py` — Invariant 4
