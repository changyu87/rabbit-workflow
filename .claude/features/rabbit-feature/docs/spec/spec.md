---
feature: rabbit-feature
version: 1.4.0
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

This feature also owns the absorbed `rabbit-feature-scope` skill and its
two scripts (`resolve-scope.py`, `format-feature-context.py`) which together
resolve a natural-language request to the set of features it will modify.
The skill, scripts, and tests live exclusively under this feature directory;
the source-of-truth has moved here, and the legacy `rabbit-feature-scope`
feature directory has been retired to a residual marker.

This feature also owns the absorbed `rabbit-feature-spec` skill (renamed
from `rabbit-spec`), which authors and updates feature specs and produces
implementation-suggestion files for whatever process invoked it. The
skill source is hosted exclusively under this feature; `build-contract.json`
and all callers (`rabbit-feature-touch` SKILL.md, `dispatch-tdd-subagent.py`)
now point at the new `rabbit-feature-spec` name and location.

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
- `.claude/features/rabbit-feature/skills/rabbit-feature-scope/SKILL.md`
  — absorbed shared skill that resolves a natural-language request to the
  list of rabbit features whose files the request will modify.
- `.claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md`
  — absorbed spec-authoring skill (renamed from `rabbit-spec`). Reads a
  feature's current spec, judges the request type, invokes superpowers as
  needed, updates the spec, and writes an impl-suggestion file for whoever
  invoked it.
- `.claude/features/rabbit-feature/scripts/resolve-scope.py`
  — absorbed script that builds the Agent-dispatch prompt used by
  `rabbit-feature-scope`.
- `.claude/features/rabbit-feature/scripts/format-feature-context.py`
  — absorbed helper that reads `find-feature.py list-json` output from
  stdin and writes the human-readable feature context block to stdout.
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
   `tdd-state-machine`'s `tdd-step.py` as hard cross-feature dependencies
   declared in `contract.md` under `invokes.scripts`. The contract entry
   pins the expected CLI signature so any drift in those script
   interfaces is caught by the smoke test in Invariant 3.

3. The cross-feature interface is locked by
   `test/test-cross-feature-interface.py`. The smoke test runs both:
   - `python3 .claude/features/tdd-state-machine/scripts/tdd-step.py --help`
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

### Absorbed from rabbit-feature-scope

The following invariants were re-homed from `rabbit-feature-scope` spec
v1.1.0 as part of the absorption. They govern the absorbed skill and
scripts now hosted under this feature.

13. `resolve-scope.py` emits a prompt to stdout only; it never calls
    Agent itself. (Absorbed from rabbit-feature-scope Inv 1.)

14. The dispatched Agent uses the default model — no Opus override.
    (Absorbed from rabbit-feature-scope Inv 2.)

15. `resolve-scope.py` uses `find-feature.py list-json` for feature
    enumeration; never reads `registry.json`. (Absorbed from
    rabbit-feature-scope Inv 3.)

16. Agent response JSON schema:
    `{"features": ["name1", ...], "rationale": "one sentence"}`.
    (Absorbed from rabbit-feature-scope Inv 4.)

17. `resolve-scope.py` is executable. (Absorbed from
    rabbit-feature-scope Inv 5.)

18. An empty `features` list `[]` is a valid response (no features
    touched). (Absorbed from rabbit-feature-scope Inv 6.)

19. `resolve-scope.py` contains no inline `python3 -c` calls or
    python3 heredocs; all Python logic is in
    `format-feature-context.py`. (Absorbed from rabbit-feature-scope
    Inv 7.)

20. `format-feature-context.py` reads JSON from stdin and writes the
    formatted feature context to stdout; it is invoked as
    `python3 format-feature-context.py`. (Absorbed from
    rabbit-feature-scope Inv 8.)

21. `rabbit-feature-scope` SKILL.md Usage section MUST present
    shell-executable commands and Claude tool-invocation pseudo-code
    in **separate code blocks with distinct fence labels**. The shell
    command that generates the prompt (`PROMPT=$(...)`) is in a
    ```bash``` fence; the `Agent(...)` tool invocation is in a
    non-shell fence (e.g., ```text```) and is preceded by a sentence
    explicitly stating that it is a Claude tool call and must NOT be
    shell-executed. (Absorbed from rabbit-feature-scope Inv 9.)

22. The assembled Agent prompt MUST NOT hardcode specific feature
    names (such as "contract" or "rabbit-cage") in its RULES section.
    Feature-specific guidance must be derived dynamically from the
    live feature list (via `find-feature.py list-json`) or generalized
    so it applies to any feature. (Absorbed from rabbit-feature-scope
    Inv 10.)

23. `format-feature-context.py` MUST tolerate `feature.json` files
    that are missing optional keys (e.g., `summary`, `tdd_state`,
    `version`, `deprecation_criterion`) without crashing. Use
    `.get(key, default)` semantics with sensible fallbacks; exit
    non-zero ONLY when JSON is malformed or fundamentally unusable
    (no `feature` key at all). (Absorbed from rabbit-feature-scope
    Inv 11.)

24. **RETIRED in v1.4.0.** Previously required absorbed surface to be
    byte-identical to the `rabbit-feature-scope` sources while both
    directories coexisted. The legacy source directory was retired in
    a subsequent cleanup; the absorbed artifacts under this feature
    are now the authoritative source and no comparison target remains.
    The locking test `test-absorbed-rabbit-feature-scope.py` has been
    removed.

### Absorbed from rabbit-spec

The following invariants were re-homed from `rabbit-spec` spec v1.3.0 as
part of the absorption + rename. They govern the absorbed
`rabbit-feature-spec` skill (formerly `rabbit-spec`) now hosted under this
feature.

25. The absorbed skill SKILL.md MUST declare `model: opus` in its YAML
    frontmatter. (Absorbed from rabbit-spec Inv 1.)

26. The absorbed skill MUST judge whether a request is open-ended or
    specific before deciding which superpowers to invoke (open →
    brainstorming + writing-plans; specific → writing-plans only).
    (Absorbed from rabbit-spec Inv 2.)

27. The absorbed skill MUST write `.rabbit/impl-suggestion-<feature>.json`
    conforming to schema_version 1.0.0 on every invocation. (Absorbed
    from rabbit-spec Inv 3.)

28. The absorbed skill MAY read any file in the target feature directory
    freely. (Absorbed from rabbit-spec Inv 4.)

29. The absorbed skill MUST update `docs/spec/spec.md` in the target
    feature directory BEFORE writing the impl-suggestion file.
    (Absorbed from rabbit-spec Inv 5.)

30. The absorbed skill SKILL.md MUST be process-agnostic. It MUST NOT
    identify any specific caller (e.g., "you are invoked as Step 3 in
    rabbit-feature-touch") as the primary or sole invocation context,
    and MUST NOT reference a specific downstream consumer (e.g., "the
    TDD subagent reads this file") as a guaranteed next step.
    (Absorbed from rabbit-spec Inv 7.)

31. The absorbed skill SKILL.md "What You Do NOT Do" section MUST NOT
    instruct the skill to avoid invoking specific named skills (e.g.,
    rabbit-feature-touch). A generic rule like "do not invoke other
    skills" is acceptable; a process-specific one is not.
    (Absorbed from rabbit-spec Inv 8.)

32. **RETIRED in v1.4.0.** Previously locked the byte-identical
    absorption of the `rabbit-spec` skill (renamed to
    `rabbit-feature-spec`) while both directories coexisted. The
    legacy `rabbit-spec` directory has been retired; the absorbed
    `rabbit-feature-spec` skill under this feature is now the
    authoritative source. The rename remains load-bearing — the
    SKILL.md `name:` field is `rabbit-feature-spec` and the
    self-reference in `description`/body uses that name — but this
    is enforced by the live SKILL.md content under this feature,
    not by a cross-source comparison. The locking test
    `test-absorbed-rabbit-spec.py` has been removed.

## What this feature does NOT define

- The TDD subagent itself, its 9-step cycle, or the `tdd-step.py` state
  machine — owned by `tdd-subagent`.
- The build pipeline that copies skills into `.claude/skills/` — owned
  by `contract` via `build-contract.json` (this feature consumes the
  build via the copy-file entry but does not define it).
- Workspace structure declarations — owned by `contract` via
  `workspace-structure.json`.

## Tests

`test/run.py` runs the end-to-end suite. The active tests after the
v1.4.0 post-consolidation cleanup are:
- `test-cross-feature-interface.py` — Invariant 3.
- `test-build-source-points-to-rabbit-feature.py` — Invariant 4.
- `test-rabbit-feature-bug-2-surface-reads-declared.py` — declared
  surface and contract reads consistency.
- `test-rabbit-feature-touch-uses-feature-spec.py` — the touch
  SKILL.md invokes `rabbit-feature-spec` (not legacy `rabbit-spec`).
- `test-skill-md-bb-mode-item-json.py` — Invariant 12.
- `test-skill-md-red-flags-no-marker.py` — Invariant 11.
- `test-skill-md-red-flags-no-write.py` — Invariant 10.
- `test-skill-md-step-4-bypass-doc.py` — Invariant 9.
- `test-skill-md-resolve-scope-path.py` — the scope-skill SKILL.md
  references the absorbed `resolve-scope.py` path under
  `.claude/features/rabbit-feature/scripts/` (post-consolidation
  bug fix, BUG-3).
- `test-inv9-version-sync.py` — feature.json/spec.md version sync.
- `test-bug-9-generated-at-format.py` — impl-suggestion timestamp
  format.

Inv 24 and Inv 32 (byte-identical absorption locks) are RETIRED at
v1.4.0; the associated locking tests were removed. Many absorbed
tests that pointed at retired source paths (legacy
`rabbit-feature-scope` and `rabbit-spec` directories) were deleted
in the same cleanup — the surviving authoritative content lives
under this feature's SKILL.md, scripts, and contract files, which
are checked directly by the surviving tests above.
