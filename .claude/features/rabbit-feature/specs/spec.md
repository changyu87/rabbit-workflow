---
feature: rabbit-feature
version: 1.22.0
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
(`rabbit-feature-scope`, `rabbit-feature-spec`, `rabbit-feature-scaffold`,
`rabbit-feature-audit`) and their backing scripts.

The executor-side TDD machinery (`dispatch-tdd-subagent.py`,
`tdd-step.py`, the 8-step TDD cycle) lives in `tdd-subagent`. This
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
- `rabbit-feature-scaffold/SKILL.md` — feature-scaffolding skill.
- `rabbit-feature-audit/SKILL.md` — feature-conformance audit skill.

Scripts (under `scripts/`):

- `resolve-scope.py` — emits the Agent-dispatch prompt used by
  `rabbit-feature-scope`.
- `format-feature-context.py` — formats `find-feature.py list-json`
  output into the feature-context block consumed by `resolve-scope.py`.
- `scaffold-feature.py` — scaffolds a conforming feature directory at any
  path; invoked by `rabbit-feature-scaffold`.

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

10. *(Retired — see CHANGELOG.md.)*

11. *(Retired — see CHANGELOG.md.)*

12. **Step 4 alert routing via `emit_configurable_alert`.** The SKILL.md
    Step 4 bypass-active path MUST instruct the dispatcher to source the
    alert by invoking
    `contract.lib.runtime.emit_configurable_alert('rabbit-cage',
    'human-approval', repo_root=<repo-root>)`. The returned
    `print_result` carries the centrally-declared `alert-message` from
    `rabbit-cage/feature.json`'s `human-approval` configurable (text,
    icon, color); the brand prefix `[🐇 rabbit 🐇]` is owned by
    `rabbit_print` (Inv 48 of `contract`), so the SKILL.md MUST NOT
    inline a hardcoded brand prefix or duplicate the alert-message text
    in prose. The SKILL.md Step 4 prose MUST still name the marker path
    (`.rabbit-human-approval-bypass`) and the revoke command
    (`/rabbit-config human-approval true`) as operational guidance for
    the user — both are operational (skill-specific) instructions
    distinct from the alert-message text. The sole source of truth for
    the alert text is the configurable's `alert-message` field.

13. *(Retired — see CHANGELOG.md.)*

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

16. **Step 3 spec-commit obligation (mode-aware).** The SKILL.md Step 3
    documents the obligation to commit spec changes BEFORE Step 5: after
    `rabbit-spec-update` returns, the dispatcher resolves a `feature_dir`
    by detecting the rabbit mode from `<repo_root>/.rabbit/.runtime/mode`
    (the same dual-mode pattern documented by `rabbit-feature-scaffold`'s
    `## Modes` section):
    - **Standalone mode** (marker absent or content equals `standalone`):
      `feature_dir = .claude/features/<feature-name>/`. The git add form is
      `git add <feature_dir>`.
    - **Plugin mode** (marker content equals `plugin`):
      `feature_dir = .rabbit/rabbit-project/features/<feature-name>/`. The
      git add form is `git add -f <feature_dir>` — the `-f` is REQUIRED
      because the host user-project's `.gitignore` typically ignores
      `.rabbit/`, and without `-f` the add silently produces an empty
      staged diff, the commit-skip branch trivially passes, and no commit
      lands. The `git add -f` ensures the spec change is actually staged
      so the conditional diff-check + commit produces a real commit
      against the host repo.
    The commit message pattern remains
    `spec(<feature-name>): update spec for <one-line request summary>`.
    The commit is skipped only when the staged diff against the resolved
    spec path (`<feature_dir>/specs/spec.md` preferred, with a
    `<feature_dir>/docs/spec/spec.md` fallback for not-yet-migrated
    features per issue #399) is empty.
    Enforced by `test/test-touch-skill.py` which asserts the SKILL.md
    Step 3 body contains both branches (standalone path + plugin path
    with `-f`) and explicitly references `.rabbit/.runtime/mode` as the
    mode-detection source. The Step 3 spec-commit diff check and the
    Step 5 `--spec` dispatch argument resolve the spec path with
    `specs/spec.md` preferred and a `docs/spec/spec.md` fallback (Inv 51).

51. **Spec path resolution (specs/ preferred).** The
    `rabbit-feature-touch` SKILL.md MUST resolve a feature's spec at
    `specs/spec.md`, preferring that path and falling back to the legacy
    `docs/spec/spec.md` only for not-yet-migrated features (issue #399
    dual-read). Step 3's spec-commit diff check and Step 5's `--spec`
    argument to `dispatch-tdd-subagent.py` MUST both point at the
    `specs/spec.md` layout, and the SKILL.md MUST document the
    `docs/spec/spec.md` fallback. Enforced by `test/test-touch-skill.py`
    (`test_inv399_skill_prefers_specs_layout`).

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
    skill to update the target feature's resolved `spec.md`
    (`.claude/features/<feature-name>/specs/spec.md`, with a
    `docs/spec/spec.md` fallback for not-yet-migrated features per issue
    #399) BEFORE writing the impl-suggestion file.

30. **Read-comprehend-write on spec edits.** The SKILL.md MUST express
    as a hard MUST in Step 1 (Read Current State) that the skill Read
    the target feature's resolved `spec.md` (`specs/spec.md` preferred,
    `docs/spec/spec.md` fallback) via the Read tool
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

### rabbit-feature-scaffold SKILL.md and scaffold-feature.py

32. **rabbit-feature-scaffold SKILL.md invocation.** The SKILL.md instructs
    the skill to invoke
    `python3 .claude/features/rabbit-feature/scripts/scaffold-feature.py`
    to scaffold the directory and to validate the result via
    `python3 .claude/features/contract/scripts/validate-feature.py`.

33. **scaffold-feature.py scaffolds a conforming feature dir.**
    `scripts/scaffold-feature.py` is executable and scaffolds a feature
    directory containing `feature.json` (with `template_version`),
    `specs/spec.md`, `specs/contract.md`, and `test/run.py`
    (no `test/run.sh`). New features are created at the `specs/` layout
    (issue #399); the scaffolded directory passes `validate-feature.py`
    immediately (which dual-reads `specs/` then `docs/spec/`).

44. **scaffold-feature.py plugin-mode invocation.** Plugin-mode detection MUST walk UP from cwd to find the nearest ancestor directory `D` such that EITHER `D/.runtime/mode` exists with content `plugin` (cwd is inside `.rabbit/` itself) OR `D/.rabbit/.runtime/mode` exists with content `plugin` (cwd is inside the user-project root or any subdirectory thereof). On first match, plugin mode is active and the resolved `rabbit_root` is either `D` itself (first case) or `D/.rabbit` (second case); the user-project root is `rabbit_root.parent`. The walk terminates at the filesystem root; if no ancestor `.runtime/mode` or `.rabbit/.runtime/mode` is found, the script falls through cleanly to the standalone form `scaffold-feature.py <root> <name> [...]`. When plugin mode is detected, `scaffold-feature.py` honors the plugin-mode CLI form `scaffold-feature.py <name> <path-glob> [<path-glob>...]`. The walk-up replaces the original single-check semantics (which only looked at `<cwd>/.rabbit/.runtime/mode`) — that semantics failed silently when cwd was `.rabbit/` itself (the typical rabbit session cwd in plugin mode), because the script then looked for `.rabbit/.rabbit/.runtime/mode` which never exists. The detection happens before any argument parsing so a `<name>+<glob>` pair is never misinterpreted as a `<root>+<name>` pair. Enforced by 5 tests under `.claude/features/rabbit-feature/test/`: cwd=project root, cwd=.rabbit/ itself (regression for #267), cwd=arbitrary nested subdir of project, cwd outside any rabbit install (standalone fallback), and cwd=/ (filesystem root terminates cleanly).

45. **Plugin-mode path-glob validation.** In plugin mode,
    `scaffold-feature.py` enforces three pre-registration validations against
    every supplied path-glob:
    (a) **Boundary** — the literal anchor of each glob (the path
        prefix up to the first segment containing a glob metacharacter)
        MUST resolve under the user-project root. Globs whose anchor
        escapes the root (e.g., `../../etc/**`) are rejected with an
        error naming the boundary; the post-resolution match list is
        also screened for symlink escapes.
    (b) **Non-empty match** — the union of matches across all globs
        MUST contain at least one filesystem path. A feature whose
        globs match zero files is rejected as a typo guard.
    (c) **No overlap with declared features** — for every match
        produced by the new globs, no existing entry in
        `<repo>/.rabbit/rabbit-project/project-map.json` may already
        declare a glob that matches the same path. On conflict the
        error names both the conflicting path (repo-relative) and the
        incumbent feature.
    Any of (a), (b), or (c) failing aborts the scaffold with exit code 1
    and leaves both the filesystem and `project-map.json` untouched.

46. **Plugin-mode scaffold location and shape.** In plugin mode, the
    scaffold target is `<repo>/.rabbit/rabbit-project/features/<name>/`.
    The scaffold contains exactly three files:
    (a) `feature.json` declaring `name`, `version` (`0.1.0`),
        `owner` (defaulted from `$USER`), `paths` (the declared globs
        verbatim), `created` (ISO 8601 UTC `YYYY-MM-DDTHH:MM:SSZ`),
        and `deprecation_criterion: null`.
    (b) `specs/spec.md` — a placeholder seeded for the spec-seeder
        subagent to fill in.
    (c) `specs/contract.md` — empty contract placeholder mirroring
        the rabbit-self shape (frontmatter + `provides`/`reads`/
        `invokes`/`never` JSON block).
    Plugin-mode scaffolds MUST NOT use the standalone-only
    `template_version` field or the rabbit-self `test/run.py`
    placeholder, because per-project features do not participate in the
    rabbit-self build/audit surface.

47. **Plugin-mode project-map registration.** On successful scaffold,
    `scaffold-feature.py` registers the new feature in
    `<repo>/.rabbit/rabbit-project/project-map.json` (created if
    absent) under
    `features.<name> = {"paths": [<glob>, ...],
    "feature_dir": "rabbit-project/features/<name>"}`. The whole
    written document MUST conform to
    `.claude/features/contract/schemas/project-map.json.schema.json`
    (top-level `schema_version: "1.0.0"` and `features` map only).
    Validation runs against the would-be-written object BEFORE the
    write; on schema failure the write is skipped and exit is 1.

48. **Plugin-mode spec-seeder dispatch handoff.** After a successful
    scaffold, `scaffold-feature.py` prints to stdout the literal
    `dispatch-spec-seeder.py` command line (the
    `.claude/features/spec-seeder/scripts/dispatch-spec-seeder.py`
    invocation, with `--feature-name <name>` and a comma-joined
    `--paths` argument). The script itself MUST NOT invoke the
    subagent; subagent dispatch is the caller's responsibility (the
    skill / dispatcher layer reads the printed command and dispatches
    the seeder). This keeps `scaffold-feature.py` free of Agent/Skill tool
    coupling.

49. **rabbit-feature-scaffold SKILL.md documents plugin-mode invocation.**
    The SKILL.md describes both invocation forms — the standalone
    `<feature-name>` form and the plugin `<feature-name>
    <path-glob>+` form — and names the plugin-mode trigger
    (`<repo>/.rabbit/.runtime/mode` containing `plugin`). The SKILL.md
    also documents the two-step user flow in plugin mode: (1) invoke
    the skill, (2) dispatch the spec-seeder subagent using the
    command printed by `scaffold-feature.py`'s stdout `NEXT:` line.

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

50. **rabbit-feature-audit enforces team ownership.** The
    `rabbit-feature-audit` SKILL.md instructs the skill to invoke
    `python3 .claude/features/rabbit-feature/scripts/audit-owner.py
    <feature-dir>` for each target and to fold its result into the
    per-feature finding — a target PASSES only when BOTH
    `validate-feature.py` and `audit-owner.py` pass. `audit-owner.py`
    requires `feature.json` `owner` to equal exactly `rabbit-workflow team`;
    any other (individual) owner FAILS with a message naming the offending
    feature and its current owner (exit 1). Retired features
    (`status: retired`) short-circuit to pass, mirroring `validate_feature`'s
    Inv 36b retired short-circuit. The script exits 0 on pass, 1 on owner
    mismatch, and 2 on bad invocation. This is defense-in-depth (issue #416
    Part C) catching future drift back to individual owners on repo-level
    features distributed as part of rabbit-workflow.

### Feature-level metadata

36. **Three-way version alignment.** `feature.json.version`,
    `specs/spec.md` frontmatter `version`, and `specs/contract.md`
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

42. *(Retired — see CHANGELOG.md.)*

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

### Prompt-contract declaration

43. **`prompts` section declares all five skills.**
    `.claude/features/rabbit-feature/feature.json` MUST declare a
    `prompts` array containing EXACTLY FIVE entries, one per skill
    surfaced by this feature, with these field values:
    (a) `{"id": "rabbit-feature-touch", "kind": "skill", "inject":
        [".claude/features/policy/philosophy.md",
         ".claude/features/policy/spec-rules.md",
         ".claude/features/policy/coding-rules.md"],
        "slots": ["args"]}` — orchestrates code changes and spec edits;
        needs the full policy bundle.
    (b) `{"id": "rabbit-feature-spec", "kind": "skill", "inject":
        [".claude/features/policy/philosophy.md",
         ".claude/features/policy/spec-rules.md"],
        "slots": ["args"]}` — authors specs; needs spec-rules but not
        coding-rules.
    (c) `{"id": "rabbit-feature-scaffold", "kind": "skill", "inject":
        [".claude/features/policy/philosophy.md",
         ".claude/features/policy/coding-rules.md"],
        "slots": ["args"]}` — scaffolds code; needs coding-rules.
    (d) `{"id": "rabbit-feature-audit", "kind": "skill", "inject":
        [".claude/features/policy/philosophy.md",
         ".claude/features/policy/coding-rules.md"],
        "slots": ["args"]}` — validates code; needs coding-rules for
        context.
    (e) `{"id": "rabbit-feature-scope", "kind": "skill", "inject":
        [".claude/features/policy/philosophy.md"], "slots": ["args"]}`
        — JSON classifier; philosophy only.
    Each entry's matching template at
    `.claude/features/contract/templates/prompts/<id>.txt` (the
    passthrough body created by contract Inv 57 in Phase A.4) declares
    the single ``args`` placeholder matching the entry's
    `slots: ["args"]`. Enforced by `test/test-prompts-declared.py`,
    which loads `feature.json` and asserts the five entries exist with
    the ids and inject lists named above.

## What this feature does NOT define

- The TDD subagent's 8-step cycle, the `tdd-step.py` state machine, or
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
- `test-touch-skill.py` — Inv 4, 5, 6, 7, 8, 9, 12, 14, 15, 16, 41
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
- `test-prompts-declared.py` — Inv 43
- `test-feature-new-plugin-mode.py` — Inv 44, 45, 46, 47, 48
- `test-new-skill.py` — Inv 32, 49
