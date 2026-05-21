---
feature: rabbit-feature
version: 1.7.0
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

This feature also owns the `rabbit-feature-scope` skill and its
two scripts (`resolve-scope.py`, `format-feature-context.py`) which together
resolve a natural-language request to the set of features it will modify.

This feature also owns the `rabbit-feature-spec` skill, which authors
and updates feature specs and produces implementation-suggestion files
for whatever process invoked it.

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
- `.claude/features/rabbit-feature/skills/rabbit-feature-new/SKILL.md`
  — feature-scaffolding skill. Given a feature name, shells out to this
  feature's own `new-feature.py` script (see below) to create a conforming
  feature dir (`feature.json`, `docs/spec/spec.md`, `docs/spec/contract.md`,
  `test/run.py`), then validates the scaffold via
  `contract.lib.checks.validate_feature`.
- `.claude/features/rabbit-feature/scripts/new-feature.py`
  — feature-scaffolding script invoked by `rabbit-feature-new`. Creates a
  conforming feature directory at any path; preserves the stdin/stdout/exit
  code contract documented in the contract block. Moved from rabbit-cage
  in RABBIT-CAGE-BACKLOG-26.
- `.claude/features/rabbit-feature/skills/rabbit-feature-audit/SKILL.md`
  — feature-audit skill. Validates a single feature or sweeps every
  feature using `contract.lib.checks.validate_feature` and returns
  structured pass/fail findings per feature.
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
   — bypass ACTIVE — and `true` deletes it). At Step 4, the dispatcher
   MUST check for this marker file: if it exists, the dispatcher skips
   the in-conversation wait, emits a visible `[🐇 rabbit 🐇]` warning
   naming the bypass marker and the path `/rabbit-config
   human-approval true` to turn the bypass off, and passes
   `--human-approval-gate false` to the Step 5
   `dispatch-tdd-subagent.py` invocation. If the marker is absent, the
   dispatcher surfaces the impl-suggestion summary and waits for
   explicit user approval. The brand prefix in the warning MUST be the
   canonical emoji-framed form `[🐇 rabbit 🐇]` (per the `contract`
   feature's Inv 27 brand definition and Inv 29 producer rule), not
   the bare `[rabbit]` form; LLM-emitted operational messages follow
   the same brand convention as `rabbit_print` script output.

9. The dispatcher-side Step 4 check for `.rabbit-human-approval-bypass`
   MUST be documented in `rabbit-feature-touch` SKILL.md as the first
   action of Step 4 (Human Approval), BEFORE any in-conversation wait
   or impl-suggestion surfacing. When the marker is found, the warning
   emitted to the user MUST name both the marker path
   (`.rabbit-human-approval-bypass`) and the revoke command
   (`/rabbit-config human-approval true`) so the user can audit
   and revoke without searching, AND MUST use the canonical
   emoji-framed brand prefix `[🐇 rabbit 🐇]` (per Inv 8 — the bare
   `[rabbit]` form is a constitution violation). This invariant
   constrains SKILL.md documentation content; the underlying behaviour
   is Inv 8.
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
    scope-guard path-pattern allowlist (rabbit-cage Inv 64) which are
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
    (unified storage). The B/B mode `related_feature` extraction MUST use Python
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

24. **RETIRED in v1.4.0** — see CHANGELOG.

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

32. **RETIRED in v1.4.0** — see CHANGELOG.

### rabbit-feature-new (v1.5.0, BACKLOG-2)

33. `rabbit-feature` provides a `rabbit-feature-new` skill at
    `.claude/features/rabbit-feature/skills/rabbit-feature-new/SKILL.md`
    that scaffolds a new rabbit feature directory with the required
    structure (`feature.json`, `docs/spec/spec.md`,
    `docs/spec/contract.md`, `test/run.py`). The skill shells out to
    `.claude/features/rabbit-feature/scripts/new-feature.py` for the
    scaffold operation — this feature owns the scaffolder directly as
    of RABBIT-CAGE-BACKLOG-26 (moved from rabbit-cage); the prior
    cross-feature dependency is retired. After scaffolding, the skill
    MUST validate the new feature dir via
    `contract.lib.checks.validate_feature` and report the new feature
    directory path. The skill SKILL.md is declared in
    `feature.json.surface.skills` and `contract.md.provides.skills`;
    the scaffolder script is declared in
    `contract.md.provides.scripts`.

### rabbit-feature-audit (v1.6.0, BACKLOG-3)

34. `rabbit-feature` provides a `rabbit-feature-audit` skill at
    `.claude/features/rabbit-feature/skills/rabbit-feature-audit/SKILL.md`
    that validates rabbit feature directories using
    `contract.lib.checks.validate_feature`. Invocation signature:
    `Skill("rabbit-feature-audit", args: "all")` sweeps every feature
    under `.claude/features/` (retired features short-circuit per
    `validate_feature` semantics); `Skill("rabbit-feature-audit",
    args: "<feature-name>")` audits a single feature. Output is
    structured per-feature pass/fail with messages. The skill SKILL.md
    is declared in `feature.json.surface.skills` and
    `contract.md.provides.skills`. Depends on the contract library
    `validate_feature` (CONTRACT-BACKLOG-26, already landed).

35. **Read-comprehend-write contract for spec edits (BUG-6).**
    (Conceptually part of the "Absorbed from rabbit-spec" subsection
    above; physically placed here to keep document order monotonic
    with numeric order — BACKLOG-6.) The `rabbit-feature-spec` skill
    MUST Read the target feature's `docs/spec/spec.md` (via the Read
    tool, in-session) BEFORE issuing any Edit or Write tool call
    against that same file in the same session. Reading is mandatory
    comprehension, not optional context-gathering — it lets the actor
    understand current invariants, numbering, and section structure
    before mutating, and it satisfies Claude Code's per-session
    file-state guard that rejects Edits on un-Read files. The
    SKILL.md MUST express this as a hard MUST in Step 1 (Read
    Current State), and MUST repeat the obligation as a
    pre-condition note in Step 4 (Update the Spec). The
    obligation extends to any caller of the skill whose
    invocation path bypasses Step 1 (e.g., direct `Edit`
    invocation by a downstream consumer is forbidden if the
    consumer has not Read the file in-session). Rationale: in
    practice, omitting the Read step caused 4+ `File must be
    read first` tool errors across the 2026-05-20 session
    bug-wave dispatches; the failure mode is silent (the
    operator wastes an Edit attempt and a Read attempt, then
    re-tries the Edit) and corrosive to dispatch throughput.
    The invariant is enforced by an e2e regression test that
    parses the `rabbit-feature-spec` SKILL.md and asserts the
    canonical mandate phrasing appears in both Step 1 and
    Step 4.

## What this feature does NOT define

- The TDD subagent itself, its 9-step cycle, or the `tdd-step.py` state
  machine — owned by `tdd-subagent`.
- The build pipeline that copies skills into `.claude/skills/` — owned
  by `contract` via `build-contract.json` (this feature consumes the
  build via the copy-file entry but does not define it).
- Workspace structure declarations — owned by `contract` via
  `workspace-structure.json`.

## Tests

`test/run.py` runs the end-to-end suite. The active tests are:
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
- `test-backlog-1-inv-5-8-coverage.py` — coverage assertions for
  Inv 5 (rabbit-feature-scope invocation) and Inv 8 (Step 4 marker).
- `test-bug-5-skillmd-brand-prefix.py` — Invariant 8/9 brand-prefix
  enforcement in SKILL.md Step 4 bypass warning (BUG-5).
- `test-bug-6-spec-skill-read-before-edit.py` — Invariant 35
  Read-comprehend-Write contract for rabbit-feature-spec (BUG-6).
- `test-contract-cross-feature-deps.py` — contract.md reads/invokes
  consistency with actual code behaviour.
- `test-skill-md-validate-feature-cli.py` — rabbit-feature-audit
  skill correctly references `validate_feature` library API.
- `test-skill-rabbit-feature-audit.py` — Invariant 34 (audit skill
  surface declaration and behaviour).
- `test-skill-rabbit-feature-new.py` — Invariant 33 (new skill
  surface declaration and behaviour).
- `test-skill-rabbit-feature-audit.py` — Invariant 34.
