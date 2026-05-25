---
feature: rabbit-feature
version: 1.13.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.
status: active
---

# rabbit-feature — Spec

> Machine-targeted LLM-prose view. The structured source of truth is
> [`feature.json`](../../feature.json) and
> [`contract.md`](./contract.md).

## Purpose

Owns the dispatcher-side feature-touch orchestration surface: the
`rabbit-feature-touch` skill plus four general-purpose helper skills
(`rabbit-feature-scope`, `rabbit-feature-spec`, `rabbit-feature-new`,
`rabbit-feature-audit`) and their backing scripts.

The executor-side TDD machinery (`dispatch-tdd-subagent.py`,
`tdd-step.py`, the 7-step TDD cycle) lives in `tdd-subagent`. This
feature consumes it via the cross-feature contract declared in
`contract.md`.

## Scripting Tech Stack

Python 3 standard library only. The test runner is `test/run.py`.

## Surface

Skills (under `skills/`):

- `rabbit-feature-touch/SKILL.md` — orchestration skill triggered on any
  feature write, edit, delete, or add operation.
- `rabbit-feature-scope/SKILL.md` — general-purpose shared skill that
  resolves a natural-language request to the list of rabbit features its
  files would modify.
- `rabbit-feature-spec/SKILL.md` — general-purpose spec-authoring skill
  that updates a feature spec and writes an implementation-suggestion
  file.
- `rabbit-feature-new/SKILL.md` — feature-scaffolding skill.
- `rabbit-feature-audit/SKILL.md` — feature-conformance audit skill.

Scripts (under `scripts/`):

- `resolve-scope.py` — emits the Agent-dispatch prompt used by
  `rabbit-feature-scope`.
- `format-feature-context.py` — formats `find-feature.py list-json`
  output into the feature-context block consumed by `resolve-scope.py`.
- `new-feature.py` — scaffolds a conforming feature directory at any
  path; invoked by `rabbit-feature-new`.

## Invariants

### Build and cross-feature contract

1. **Build source.** The deployed `.claude/skills/rabbit-feature-touch/SKILL.md`
   is sourced from
   `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`.
   This feature's `feature.json` `manifest` declares a `publish_skill`
   entry whose `args.source` is `skills/rabbit-feature-touch/SKILL.md`
   (relative to the feature directory).

2. **Declared cross-feature script dependencies.** This feature invokes
   `.claude/features/tdd-subagent/scripts/tdd-step.py` and
   `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py`. Both
   are declared in `contract.md` under `invokes.scripts` with their
   CLI signatures pinned.

3. **Cross-feature CLI smoke.** A test in `test/` invokes `--help` on
   both `tdd-step.py` and `dispatch-tdd-subagent.py`; both must exit 0
   and print recognizable usage text.

### rabbit-feature-touch SKILL.md

4. **Seven-step sequence.** The SKILL.md documents seven numbered steps
   in this order:
   (1) Scope Resolution, (2) Create Branch, (3) Spec Authoring,
   (4) Human Approval, (5) Dispatch TDD Subagents,
   (6) Collect and Verify HANDOFFs, (7) PR / Hand Off.
   The overview section heading reflects the "Seven-Step" framing and
   every step heading reflects the documented number and name.

5. **Step 1 scope resolution via Skill tool.** In normal mode, the
   SKILL.md Step 1 instructs the dispatcher to resolve scope by
   invoking `Skill("rabbit-feature-scope", args: "<request>")`, not by
   shelling out to `resolve-scope.py`.

6. **Step 3 spec authoring via Skill tool.** The SKILL.md Step 3
   instructs the dispatcher to invoke
   `Skill("rabbit-feature-spec", args: "<feature-name> <request>")`.

7. **Step 4 dispatcher-side gate.** The SKILL.md Step 4 (Human Approval)
   explicitly states the gate "lives here, in the main session" and
   explains that subagents run to completion and cannot pause for user
   input, locking the gate to the dispatcher.

8. **Step 4 bypass mechanism.** The bypass authorization is the file
   marker `.rabbit-human-approval-bypass` at the repo root. The SKILL.md
   names this marker as the sole bypass mechanism and names
   `/rabbit-config human-approval true|false` as the management
   command (`false` writes the marker, `true` removes it).

9. **Step 4 bypass-check ordering.** The SKILL.md Step 4 documents the
   `.rabbit-human-approval-bypass` check as the FIRST action of the
   step, before any impl-suggestion surfacing or in-conversation wait.

10. *(Retired — see CHANGELOG.md, TDD-SUBAGENT-BACKLOG-19 cascade.)*

11. *(Retired — see CHANGELOG.md, TDD-SUBAGENT-BACKLOG-19 cascade.)*

12. **Step 4 brand prefix.** The SKILL.md Step 4 bypass-active warning
    uses the canonical brand prefix `[🐇 rabbit 🐇]` and names both
    the marker path (`.rabbit-human-approval-bypass`) and the revoke
    command (`/rabbit-config human-approval true`) in the warning
    text.

13. **B/B mode reads `item.json`.** The SKILL.md B/B mode reads the
    linked item JSON from `<item-dir>/item.json` (never `bug.json`) and
    extracts the `related_feature` field via Python 3 (never `jq`,
    which is not a declared dependency of this feature).

14. **Red Flag — no main-session Write/Edit on features.** The SKILL.md
    Red Flags section forbids the main session from using Write or Edit
    on any file under `.claude/features/`. The documented exceptions
    are confirm-token overrides (Override Path) and
    `rabbit-feature-spec`'s spec writes via the scope-guard path-pattern
    allowlist during Step 3.

15. **Red Flag — no main-session scope-marker creation.** The SKILL.md
    Red Flags section forbids the main session from creating
    `.rabbit-scope-active` (global) or `.rabbit-scope-active-<feature>`
    (per-feature) markers at the repo root. Scope markers are
    exclusively the TDD subagent's responsibility.

16. **Step 3 spec-commit obligation.** The SKILL.md Step 3 documents
    the obligation to commit spec changes BEFORE Step 5: after
    `rabbit-feature-spec` returns, the dispatcher stages modifications
    under `.claude/features/<feature-name>/` and commits with message
    pattern `spec(<feature-name>): update spec for <one-line request
    summary>`. The commit is skipped only when the staged diff against
    `docs/spec/spec.md` is empty.

### rabbit-feature-scope SKILL.md and scripts

17. **resolve-scope.py emits prompt only.** `scripts/resolve-scope.py`
    writes a prompt to stdout and never invokes Agent itself.

18. **Default Agent model.** The Agent dispatched by callers of
    `rabbit-feature-scope` uses the default model (no Opus override
    in the prompt or the SKILL.md instructions).

19. **Feature enumeration via `find-feature.py list-json`.**
    `scripts/resolve-scope.py` uses
    `python3 .claude/features/contract/scripts/find-feature.py <repo-root> list-json`
    to enumerate features and never reads `registry.json`.

20. **Agent response schema.** The Agent invoked by
    `rabbit-feature-scope` returns
    `{"features": ["name", ...], "rationale": "one sentence"}`. An
    empty `features` list is a valid response.

21. **resolve-scope.py is executable and pure-shell.**
    `scripts/resolve-scope.py` has the executable bit set and contains
    no inline `python3 -c` calls or python3 heredocs; all Python logic
    lives in `format-feature-context.py`.

22. **format-feature-context.py stdin/stdout contract.**
    `scripts/format-feature-context.py` reads JSON from stdin and
    writes the formatted feature-context block to stdout. It is invoked
    as `python3 format-feature-context.py`.

23. **format-feature-context.py tolerates missing optional keys.** The
    script tolerates a `feature.json` missing optional keys (`summary`,
    `tdd_state`, `version`, `deprecation_criterion`) without crashing.
    A missing `feature` key is the only fatal condition.

24. **rabbit-feature-scope SKILL.md fence separation.** The Usage
    section presents the shell command and the Agent tool invocation
    in separate fenced code blocks with distinct fence labels (e.g.,
    ```bash``` for the shell command, ```text``` for the tool call).
    The Agent block is preceded by a sentence stating it is a Claude
    tool call and MUST NOT be shell-executed.

25. **Scope Agent prompt is feature-agnostic.** The prompt assembled by
    `resolve-scope.py` does not hardcode specific feature names (such
    as `contract` or `rabbit-cage`) in its RULES section. Feature-
    specific guidance derives from the live feature list emitted by
    `find-feature.py list-json` or is generalized.

### rabbit-feature-spec SKILL.md

26. **Frontmatter declares `model: opus`.** The `rabbit-feature-spec`
    SKILL.md YAML frontmatter declares `model: opus`.

27. **Request classification gates superpowers.** The SKILL.md instructs
    the skill to judge whether a request is open-ended or specific
    BEFORE deciding which superpowers to invoke. Open-ended requests
    invoke `superpowers:brainstorming` followed by
    `superpowers:writing-plans`; specific requests invoke
    `superpowers:writing-plans` only.

28. **impl-suggestion file output.** The SKILL.md instructs the skill
    to write `.rabbit/impl-suggestion-<feature-name>.json` conforming
    to `schema_version: 1.0.0`. The documented `generated_at` field
    format is ISO 8601 UTC in the shape `YYYY-MM-DDTHH:MM:SSZ`
    (no fractional seconds, no timezone offset).

29. **Spec update precedes impl-suggestion.** The SKILL.md instructs the
    skill to update
    `.claude/features/<feature-name>/docs/spec/spec.md` BEFORE writing
    the impl-suggestion file.

30. **Read-comprehend-write on spec edits.** The SKILL.md MUST express
    as a hard MUST in Step 1 (Read Current State) that the skill Read
    the target feature's `docs/spec/spec.md` via the Read tool
    in-session, and MUST repeat the obligation as a pre-condition note
    in Step 4 (Update the Spec). Reading is mandatory comprehension
    before any Edit or Write on that file.

31. **Process-agnostic SKILL.md.** The SKILL.md MUST NOT identify a
    specific caller (e.g., "you are Step 3 in rabbit-feature-touch") as
    the primary or sole invocation context, and MUST NOT reference a
    specific downstream consumer (e.g., "the TDD subagent reads this
    file") as a guaranteed next step. The "What You Do NOT Do" section
    MUST NOT name specific skills it must not invoke; only generic
    rules ("do not invoke other skills") are acceptable.

### rabbit-feature-new SKILL.md and new-feature.py

32. **rabbit-feature-new SKILL.md invocation.** The SKILL.md instructs
    the skill to invoke
    `python3 .claude/features/rabbit-feature/scripts/new-feature.py`
    to scaffold the directory and to validate the result via
    `python3 .claude/features/contract/scripts/validate-feature.py`.

33. **new-feature.py scaffolds a conforming feature dir.**
    `scripts/new-feature.py` is executable and scaffolds a feature
    directory containing `feature.json` (with `template_version`),
    `docs/spec/spec.md`, `docs/spec/contract.md`, and `test/run.py`
    (no `test/run.sh`). The scaffolded directory passes
    `validate-feature.py` immediately.

### rabbit-feature-audit SKILL.md

34. **rabbit-feature-audit invocation surface.** The SKILL.md accepts
    `Skill("rabbit-feature-audit", args: "all")` to sweep every
    immediate subdirectory of `.claude/features/`, and
    `Skill("rabbit-feature-audit", args: "<feature-name>")` to audit a
    single feature.

35. **rabbit-feature-audit uses validate-feature.py.** For each
    target, the SKILL.md instructs the skill to invoke
    `python3 .claude/features/contract/scripts/validate-feature.py
    <feature-dir>` and to emit per-feature pass/fail output.

### Feature-level metadata

36. **Three-way version alignment.** `feature.json.version`,
    `docs/spec/spec.md` frontmatter `version`, and `docs/spec/contract.md`
    frontmatter `version` MUST match exactly.

37. **SKILL.md frontmatter completeness.** Every SKILL.md declared in
    `feature.json.surface.skills` declares non-empty `version`,
    `owner`, and `deprecation_criterion` fields in its YAML frontmatter.

38. **feature.json summary mentions every skill.**
    `feature.json.summary` mentions by name every skill declared in
    `feature.json.surface.skills`.

39. **Surface and contract consistency.** Every skill listed in
    `feature.json.surface.skills` has a corresponding entry under
    `contract.md.provides.skills`. Every cross-feature file or script
    that this feature's code reads or invokes has a corresponding entry
    under `contract.md.reads.files` or `contract.md.invokes.scripts`.

### Manifest-driven deployment

40. **Manifest declares deployment.** `rabbit-feature.feature.json`
    declares a `manifest` array of N publish API calls, one per skill
    in `skills/`. The manifest is the meta-contract source of truth
    for what `rabbit-feature` deploys. Each manifest entry is
    `{"api": "publish_skill", "args":
    {"source": "skills/<name>/SKILL.md"}}`, and the union of manifest
    entries deploys the set of `.claude/skills/<name>/SKILL.md`
    artifacts byte-identically.

### B/B item materialization

42. **B/B item materialization documented.** The `rabbit-feature-touch`
    SKILL.md B/B mode documentation MUST explicitly describe how a
    caller materializes a bug/backlog item into a local working-tree
    mirror before passing the path to
    `dispatch-tdd-subagent.py --linked-item`. The documentation MUST
    cover all four of the following points:
    (a) **Why materialization is needed** — the dedicated B/B branch
    `origin/bug-backlog-files` is never checked out in the
    dispatcher's working tree, so the canonical item.json is not
    reachable as a working-tree path.
    (b) **The local mirror path layout** —
    `.rabbit/rabbit/features/<feature>/<type>s/<id>/item.json`, which
    mirrors the rabbit-file storage layout
    (`rabbit/features/<feature>/<type>s/<id>/`) under a `.rabbit/`
    prefix (`.rabbit/` is gitignored by contract).
    (c) **The git command to fetch item.json** from
    `origin/bug-backlog-files` into the local mirror path — using
    `git show origin/bug-backlog-files:rabbit/features/<feature>/<type>s/<id>/item.json`
    redirected to the local mirror path (after `mkdir -p` of the
    parent directory).
    (d) **What gets passed to `--linked-item`** — the local mirror
    directory path (the directory containing the freshly materialized
    `item.json`), NOT the canonical
    `rabbit/features/<feature>/<type>s/<id>/` path on the dedicated
    branch.
    The materialization documentation MUST appear in the B/B mode
    section of
    `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`
    and MUST also be present byte-identical in the deployed copy
    `.claude/skills/rabbit-feature-touch/SKILL.md`.

### Dispatcher continuity

41. **Dispatcher continuity directive.** The `rabbit-feature-touch`
    SKILL.md MUST contain an explicit dispatcher-continuity directive
    stating that once Step 1 begins, the dispatcher MUST NOT end its
    turn until Step 7 (PR / Hand Off) completes or an explicit failure
    is reported to the user. The directive MUST explicitly state that
    a subagent returning a HANDOFF is a phase boundary inside the
    dispatcher's own ongoing turn, NOT a turn boundary, and that the
    dispatcher continues to the next step immediately. The directive
    MUST appear in both the source SKILL.md
    (`.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md`)
    and the deployed copy (`.claude/skills/rabbit-feature-touch/SKILL.md`),
    byte-identical, so that the published surface enforces the same
    continuity contract. Placement is at the discretion of the author
    but must be prominent enough that a fresh dispatcher reading the
    SKILL.md sees the directive before reaching Step 7 (suggested
    placement: near the Overview, or as the closing paragraph after
    Step 7's body).

## What this feature does NOT define

- The TDD subagent's 7-step cycle, the `tdd-step.py` state machine, or
  the `dispatch-tdd-subagent.py` prompt assembler — owned by
  `tdd-subagent`.
- The build pipeline that copies skills into `.claude/skills/` — owned
  by `contract`. This feature consumes the pipeline; it does not define
  it.
- `workspace-structure.json` content — owned by `contract`.

## Tests

`test/run.py` runs every `test-*.py` under `test/`. The active tests are
listed below, each tagged with the invariant(s) it covers.

- `test-build-source.py` — Inv 1
- `test-cross-feature-interface.py` — Inv 2, 3
- `test-touch-skill.py` — Inv 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 41, 42
- `test-scope-skill.py` — Inv 24
- `test-scope-scripts.py` — Inv 17, 18, 19, 20, 21, 22, 23, 25
- `test-spec-skill.py` — Inv 26, 27, 28, 29, 30, 31
- `test-new-skill.py` — Inv 32
- `test-new-feature-scaffolder.py` — Inv 33
- `test-audit-skill.py` — Inv 34, 35
- `test-version-sync.py` — Inv 36
- `test-skill-md-frontmatter.py` — Inv 37
- `test-feature-json-summary.py` — Inv 38
- `test-contract-md.py` — Inv 39
- `test-manifest-shape.py` — Inv 40
- `test-manifest-deploys-correctly.py` — Inv 40
