---
feature: rabbit-feature
version: 1.35.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.
status: active
---

# rabbit-feature — Spec

> Machine-targeted LLM-prose view. The structured source of truth is
> [`feature.json`](../feature.json) and
> [`contract.md`](./contract.md).

## Purpose

Owns the dispatcher-side feature-touch orchestration surface: the
`rabbit-feature-touch` skill plus three general-purpose helper skills
(`rabbit-feature-scope`, `rabbit-feature-scaffold`, `rabbit-feature-audit`)
and their backing scripts.

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
- `rabbit-feature-scaffold/SKILL.md` — feature-scaffolding skill.
- `rabbit-feature-audit/SKILL.md` — feature-conformance audit skill.

Scripts (under `scripts/`):

- `resolve-scope.py` — emits the Agent-dispatch prompt used by
  `rabbit-feature-scope`.
- `format-feature-context.py` — formats `find-feature.py list-json`
  output into the feature-context block consumed by `resolve-scope.py`.
- `scaffold-feature.py` — scaffolds a conforming feature directory at any
  path; invoked by `rabbit-feature-scaffold`.

Skill-local companion scripts (under `skills/<skill>/scripts/`, invoked from
their source path and not deployed):

- `skills/rabbit-feature-touch/scripts/feature-touch.py` — owns the
  `rabbit-feature-touch` skill's computed / mode-aware orchestration logic
  (the `resolve-spec-path` and `commit-spec` subcommands), so the SKILL.md
  body stays script-tier per the SKILL.md Authoring Standard
  (`spec-rules.md` §4).

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
   `Skill("rabbit-spec-update", args: "<feature-name> <request>")`.

7. **Step 4 dispatcher-side gate.** The SKILL.md Step 4 (Human Approval)
   explicitly states the gate "lives here, in the main session" and
   explains that subagents run to completion and cannot pause for user
   input, locking the gate to the dispatcher.

8. **Step 4 bypass mechanism.** The bypass authorization is the canonical
   file marker `.rabbit-tdd-autonomous` at the repo root. The SKILL.md
   names this canonical marker as the sole bypass mechanism and names
   `/rabbit-tdd-autonomous true|false` as the management command.
   Polarity: `true` writes the marker — autonomous/bypass ACTIVE;
   `false` (the default) removes it — the Step-4 gate is ACTIVE. The
   Step-4 consumer also dual-reads the marker `.rabbit-human-approval-bypass`
   for coexistence, but the SKILL.md documents the canonical marker.

9. **Step 4 bypass-check ordering.** The SKILL.md Step 4 documents the
   `.rabbit-tdd-autonomous` check as the FIRST action of the step,
   before any impl-suggestion surfacing or in-conversation wait.

12. **Step 4 alert routing via `emit_configurable_alert`.** The SKILL.md
    Step 4 bypass-active path MUST instruct the dispatcher to source the
    alert by invoking
    `contract.lib.runtime.emit_configurable_alert('rabbit-feature',
    'tdd-autonomous', repo_root=<repo-root>)`. The returned
    `print_result` carries the declared `alert-message` from
    `rabbit-feature/feature.json`'s OWN `tdd-autonomous` configurable
    (text, icon, color); sourcing the alert from this feature's own
    configurable keeps the read in-scope (no cross-feature read). The
    brand prefix `[🐇 rabbit 🐇]` is owned by
    `rabbit_print` (Inv 48 of `contract`), so the SKILL.md MUST NOT
    inline a hardcoded brand prefix or duplicate the alert-message text
    in prose. The SKILL.md Step 4 prose MUST still name the canonical
    marker path (`.rabbit-tdd-autonomous`) and the management command
    (`/rabbit-tdd-autonomous true|false`) as operational guidance for
    the user — both are operational (skill-specific) instructions
    distinct from the alert-message text. The sole source of truth for
    the alert text is the configurable's `alert-message` field.

14. **Red Flag — no main-session Write/Edit on features.** The SKILL.md
    Red Flags section forbids the main session from using Write or Edit
    on any file under `.claude/features/`. The documented exceptions
    are confirm-token overrides (Override Path) and `rabbit-spec-update`'s
    spec writes via the scope-guard path-pattern allowlist during Step 3.

15. **Red Flag — no main-session scope-marker creation.** The SKILL.md
    Red Flags section forbids the main session from creating
    `.rabbit-scope-active` (global) or `.rabbit-scope-active-<feature>`
    (per-feature) markers at the repo root. Scope markers are
    exclusively the TDD subagent's responsibility.

16. **Step 3 spec-commit obligation (mode-aware, script-backed).** The
    SKILL.md Step 3 documents the obligation to commit spec changes BEFORE
    Step 5 in PROSE and delegates the mode-aware execution to the companion
    `feature-touch.py commit-spec` subcommand (Inv 54), per the SKILL.md
    Authoring Standard's Script-Backed Orchestration rule
    (`spec-rules.md` §4): the mode-aware branching is a computed step, so it
    MUST NOT be assembled inline as a bash control-flow block.
    The prose obligation MUST remain (the literal phrase "Commit spec
    changes BEFORE Step 5", the commit message pattern
    `spec(<feature-name>): update spec for ...`, and the empty-diff-skip
    behaviour), and Step 3's body MUST invoke
    `feature-touch.py commit-spec <feature-name> "<summary>"`.
    The mode-aware mechanics themselves — detecting the rabbit mode from
    `<repo_root>/.rabbit/.runtime/mode`, resolving the standalone
    (`.claude/features/<name>/`, `git add`) vs plugin
    (`.rabbit/rabbit-project/features/<name>/`, `git add -f`) feature-dir
    and staging form, resolving the spec path (flat `docs/spec.md` preferred,
    `docs/spec/spec.md` fallback), skipping the commit on an empty staged
    diff, and otherwise committing with the message above — are OWNED BY
    the companion script and locked by
    `test/test-touch-skill-authoring-standard.py` (Inv 54), not by inline
    SKILL.md bash. Enforced by `test/test-touch-skill.py`
    (`test_inv16_step_3_spec_commit_obligation` for the prose obligation,
    `test_inv16_step_3_delegates_to_companion_script` for the script
    invocation).

51. **Spec path resolution (flat docs/ preferred, script-backed).** A
    feature's spec MUST be resolved preferring the flat `docs/spec.md` layout,
    falling back to the legacy `docs/spec/spec.md` for any not-yet-migrated
    nested-docs feature. Per the SKILL.md Authoring Standard
    (`spec-rules.md` §4 Script-Backed Orchestration), this computed
    resolution is owned by the companion `feature-touch.py resolve-spec-path`
    subcommand (Inv 54), not assembled inline. Step 5's `--spec` argument to
    `dispatch-tdd-subagent.py` MUST be sourced from
    `feature-touch.py resolve-spec-path <feature-name>`, and Step 3's
    spec-commit obligation resolves the same path via the `commit-spec`
    subcommand. Enforced by `test/test-touch-skill.py`
    (`test_inv56_step5_delegates_spec_path_to_companion`) for the Step 5
    delegation and by `test/test-touch-skill-authoring-standard.py`
    (`test_inv54_resolve_spec_path_prefers_flat_docs`) plus
    `test/test-touch-docs-resolver.py` (Inv 56) for the resolution behaviour.

52. **Step 5 dispatches the `rabbit-tdd-subagent` agent type.**
    The `rabbit-feature-touch` SKILL.md Step 5 Agent tool call MUST pass
    `subagent_type: rabbit-tdd-subagent` — the renamed dispatched agent
    type. This binds only the AGENT type; the prompt-assembler script path
    (`.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py`,
    feature-dir + script name unchanged) is unaffected and MUST remain. The
    bare agent type `tdd-subagent` MUST NOT appear in the SKILL.md outside
    that feature-dir/script-path reference. Enforced by
    `test/test-touch-skill.py`
    (`test_inv52_source_step5_dispatches_rabbit_tdd_subagent`,
    `test_inv52_deployed_step5_dispatches_rabbit_tdd_subagent`,
    `test_inv52_source_no_bare_old_agent_type`,
    `test_inv52_deployed_no_bare_old_agent_type`).

53. **§4 Script-Backed Orchestration — no model-assembled control-flow bash.**
    The `rabbit-feature-touch` SKILL.md body (source AND
    deployed) MUST NOT contain a fenced `bash` block that combines a runtime
    placeholder (e.g. `<feature-name>`, `<branch-name>`) with shell control
    flow (`if`/`then`/`else`/`for`/`while`/`case`) — such a block is a
    model-assembled orchestration step and violates the SKILL.md Authoring
    Standard (`spec-rules.md` §4 Script-Backed Orchestration). The two
    previously-inline computed steps — the Step 3 mode-aware spec-commit and
    the Step 5 spec-path resolution — MUST instead invoke the companion
    `feature-touch.py` script (`commit-spec` and `resolve-spec-path`
    subcommands respectively). Exceptions permitted inline: single read-only
    informational commands (no control flow) and script-invocation commands
    where the placeholder is a script ARGUMENT rather than assembled control
    flow (e.g. `git checkout -b <branch-name>`, the Step 4
    `emit_configurable_alert` informational call). Enforced by
    `test/test-touch-skill-authoring-standard.py`
    (`test_inv53_source_no_offending_bash_blocks`,
    `test_inv53_deployed_no_offending_bash_blocks`,
    `test_inv53_step3_invokes_companion_commit_spec`,
    `test_inv53_step5_invokes_companion_resolve_spec_path`).

54. **Companion `feature-touch.py` script.** The
    `rabbit-feature-touch` skill ships a companion script at
    `skills/rabbit-feature-touch/scripts/feature-touch.py` that owns the
    skill's computed / mode-aware orchestration logic. It is executable,
    Python-3-stdlib-only, and exposes three subcommands:
    (a) `resolve-spec-path <feature-name>` — prints the repo-root-relative
        resolved spec path (flat `docs/spec.md` preferred, then legacy
        `docs/spec/spec.md`), mode-aware via
        `<repo_root>/.rabbit/.runtime/mode`.
    (b) `resolve-contract-path <feature-name>` — same preference order for the
        contract (flat `docs/contract.md` preferred, then legacy
        `docs/spec/contract.md`).
    (c) `commit-spec <feature-name> <summary>` — stages the feature dir with
        the mode-appropriate `git add` form (plugin mode uses `git add -f`),
        skips the commit on an empty staged spec diff, and otherwise commits
        with `spec(<feature-name>): update spec for <summary>`.
    A no-arg invocation prints usage naming the subcommands and exits 2.
    The script is declared in `contract.md.provides.scripts` (it is a
    skill-local companion invoked from its source path, not a deployed
    artifact, so it is not in the `manifest`; the `feature.json.surface`
    field is deprecated). Enforced by
    `test/test-touch-skill-authoring-standard.py`
    (`test_inv54_companion_exists_and_executable`,
    `test_inv54_companion_usage_lists_subcommands`,
    `test_inv54_companion_owns_mode_branching`,
    `test_inv54_resolve_spec_path_prefers_flat_docs`,
    `test_inv54_commit_spec_commits_change_and_skips_noop`).

55. **§4 Verbatim Policy Embedding — Red Flags cite canonical policy.**
    The `rabbit-feature-touch` SKILL.md Red Flags section,
    where it surfaces the main-session bounded-scope boundary, MUST cite the
    canonical policy source (`.claude/features/policy/philosophy.md` §2 and/or
    `.claude/features/policy/spec-rules.md` §2) rather than relying solely on
    a paraphrase, per the SKILL.md Authoring Standard
    (`spec-rules.md` §4 Verbatim Policy Embedding). Enforced by
    `test/test-touch-skill-authoring-standard.py`
    (`test_inv55_red_flags_cite_canonical_policy`).

56. **Flat `docs/` resolver preference.** The companion
    `feature-touch.py` spec/contract resolvers (`resolve-spec-path`,
    `resolve-contract-path`) MUST PREFER the flat `docs/` layout
    (`docs/spec.md`, `docs/contract.md` — the ratified migration target),
    falling back ONLY to the legacy `docs/spec/` layout. The dead `specs/`
    fallback is removed: every feature has migrated to flat `docs/`, so a
    stray `specs/` file is NOT resolved and is irrelevant to resolution.
    When neither a flat `docs/` nor a legacy `docs/spec/` file exists,
    resolution defaults to the flat `docs/` target so new resolutions point
    at the ratified location. The preference order is mode-aware (standalone
    and plugin feature-dir prefixes). Enforced by
    `test/test-touch-docs-resolver.py`.

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

### rabbit-feature-scaffold SKILL.md and scaffold-feature.py

32. **rabbit-feature-scaffold SKILL.md invocation.** The SKILL.md instructs
    the skill to invoke
    `python3 .claude/features/rabbit-feature/scripts/scaffold-feature.py`
    to scaffold the directory and to validate the result via
    `python3 .claude/features/contract/scripts/validate-feature.py`.

33. **scaffold-feature.py scaffolds a conforming feature dir.**
    `scripts/scaffold-feature.py` is executable and scaffolds a feature
    directory containing `feature.json` (with `template_version`),
    `docs/spec.md`, `docs/contract.md`, `docs/bugs/`, and `test/run.py`
    (no `test/run.sh`). New features are created at the flat `docs/` layout,
    NOT the legacy `docs/spec/` layout; the scaffolded directory passes
    `validate-feature.py` immediately.

44. **scaffold-feature.py plugin-mode invocation.** Plugin-mode detection MUST walk UP from cwd to find the nearest ancestor directory `D` such that EITHER `D/.runtime/mode` exists with content `plugin` (cwd is inside `.rabbit/` itself) OR `D/.rabbit/.runtime/mode` exists with content `plugin` (cwd is inside the user-project root or any subdirectory thereof). On first match, plugin mode is active and the resolved `rabbit_root` is either `D` itself (first case) or `D/.rabbit` (second case); the user-project root is `rabbit_root.parent`. The walk terminates at the filesystem root; if no ancestor `.runtime/mode` or `.rabbit/.runtime/mode` is found, the script falls through cleanly to the standalone form `scaffold-feature.py <root> <name> [...]`. When plugin mode is detected, `scaffold-feature.py` honors the plugin-mode CLI form `scaffold-feature.py <name> <path-glob> [<path-glob>...]`. The walk-up replaces the original single-check semantics (which only looked at `<cwd>/.rabbit/.runtime/mode`) — that semantics failed silently when cwd was `.rabbit/` itself (the typical rabbit session cwd in plugin mode), because the script then looked for `.rabbit/.rabbit/.runtime/mode` which never exists. The detection happens before any argument parsing so a `<name>+<glob>` pair is never misinterpreted as a `<root>+<name>` pair. Enforced by 5 tests under `.claude/features/rabbit-feature/test/`: cwd=project root, cwd=.rabbit/ itself, cwd=arbitrary nested subdir of project, cwd outside any rabbit install (standalone fallback), and cwd=/ (filesystem root terminates cleanly).

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
    (b) `docs/spec.md` — a placeholder for the spec-creator subagent
        (dispatched via the `rabbit-spec-create` skill) to fill in.
    (c) `docs/contract.md` — empty contract placeholder mirroring
        the rabbit-self shape (frontmatter + `provides`/`reads`/
        `invokes`/`never` JSON block).
    Plugin-mode scaffolds use the flat `docs/` layout (the ratified
    migration target) and MUST NOT create the legacy `specs/` layout.
    They MUST NOT use the standalone-only `template_version` field or
    the rabbit-self `test/run.py` placeholder, because per-project
    features do not participate in the rabbit-self build/audit surface.

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

48. **Plugin-mode spec-create dispatch handoff.** After a successful
    scaffold, `scaffold-feature.py` prints to stdout a `NEXT:` line
    naming the `rabbit-spec-create` skill invocation and the equivalent
    `dispatch-spec-create.py` command line (the
    `.claude/features/rabbit-spec/scripts/dispatch-spec-create.py`
    invocation, with `--feature-name <name>` and a comma-joined
    `--paths` argument). The script itself MUST NOT invoke the
    subagent; subagent dispatch is the caller's responsibility (the
    skill / dispatcher layer reads the printed command and dispatches
    the spec-creator). This keeps `scaffold-feature.py` free of Agent/Skill tool
    coupling.

49. **rabbit-feature-scaffold SKILL.md documents plugin-mode invocation.**
    The SKILL.md describes both invocation forms — the standalone
    `<feature-name>` form and the plugin `<feature-name>
    <path-glob>+` form — and names the plugin-mode trigger
    (`<repo>/.rabbit/.runtime/mode` containing `plugin`). The SKILL.md
    also documents the two-step user flow in plugin mode: (1) invoke
    the skill, (2) dispatch the spec-creator subagent (via the
    `rabbit-spec-create` skill) using the command printed by
    `scaffold-feature.py`'s stdout `NEXT:` line.

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
    feature and its current owner (exit 1). A feature exempted by contract
    Inv 36b's status short-circuit skips the owner check and passes, mirroring
    `validate_feature`'s behaviour. The script exits 0 on pass, 1 on owner
    mismatch, and 2 on bad invocation. This is defense-in-depth catching
    future drift back to individual owners on repo-level
    features distributed as part of rabbit-workflow.

### Feature-level metadata

36. **Three-way version alignment.** `feature.json.version`,
    `docs/spec.md` frontmatter `version`, and `docs/contract.md`
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

### tdd-autonomous configurable + /rabbit-tdd-autonomous command

57. **tdd-autonomous configurable owned here.** `rabbit-feature`'s
    `feature.json` `configuration[]` declares exactly one entry with
    `id`/`subcommand` `tdd-autonomous` — the approval gate over the
    TDD feature-touch Step-4 cycle. It declares `command:
    "rabbit-tdd-autonomous"` and `restart_required: true`. Its storage is a
    `marker-file` at the canonical bypass marker `.rabbit-tdd-autonomous`.
    Polarity: `default` is `"false"` — the Step-4 gate is ACTIVE by default
    with no bypass marker; `values.false` deletes `.rabbit-tdd-autonomous`
    (gate active) and `values.true` writes it (bypass active). `alert-on` is
    `"true"` and `alert-message.text` is exactly
    `TDD-AUTONOMOUS MODE ACTIVE — TDD cycle Step 4 (human approval) skipped`.
    The on-disk marker scripts (`set-evolve-mode.py`,
    `check-preconditions.py`) and the auto-evolve loop are unaffected — they
    mutate bypass markers via `contract.lib.mutation` directly — and the
    Step-4 gate consumer `dispatch-tdd-subagent.py` reads both
    `.rabbit-human-approval-bypass` and `.rabbit-tdd-autonomous`, so writing
    the canonical marker is honored. Enforced by
    `test/test-tdd-autonomous-configurable.py`.

58. **/rabbit-tdd-autonomous thin command.** `rabbit-feature` manifests the
    `/rabbit-tdd-autonomous true|false` command (a `publish_command` manifest
    entry for `commands/rabbit-tdd-autonomous.md`, listed in
    `surface.commands`). Its backing script
    `scripts/rabbit-tdd-autonomous-config.py` is a THIN wrapper: it reads
    rabbit-feature's own `feature.json configuration[]` `tdd-autonomous` entry
    and delegates ALL validation, mutation, and restart-prompt rendering to
    `contract.lib.config_dispatch.dispatch_config`; it MUST NOT re-implement the
    interpreter (no `_apply_template` / `_validate`). `tdd-autonomous true`
    writes `.rabbit-tdd-autonomous` and emits the branded restart prompt
    (restart_required); `tdd-autonomous false` deletes it; an unknown
    subcommand or value exits non-zero. The command frontmatter carries the six
    required keys (`name`, `description`, `version`, `owner`,
    `deprecation_criterion`, `template_version`) with owner exactly
    `rabbit-workflow team`. `/rabbit-tdd-autonomous` is the SOLE supported
    surface for this configurable. Enforced by
    `test/test-tdd-autonomous-command.py`.

59. **Per-feature tdd-autonomous override alert.** `rabbit-feature`'s
    `feature.json` `runtime[]` declares a `check_marker_alert` entry under BOTH
    `Stop` and `SessionStart` targeting `.rabbit-tdd-autonomous` with the
    canonical Step-4 bypass `alert` (`text` matching Inv 57's alert-message,
    `color: red`), consumed by the generic event dispatcher via
    `contract.lib.runtime.check_marker_alert`. The override alert is owned by
    this feature — the one that owns the gated behavior — rather than emitted
    from a central enumeration: the alert FIRES (red `print_result`) when the
    bypass marker is present and is SILENT (no banner) when absent. Enforced by
    `test/test-tdd-autonomous-alert.py`.

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

- `test-cross-feature-interface.py` — Inv 2, 3
- `test-touch-skill.py` — Inv 4, 5, 6, 7, 8, 9, 12, 14, 15, 16, 41, 51, 52
- `test-touch-skill-authoring-standard.py` — Inv 53, 54, 55
- `test-touch-docs-resolver.py` — Inv 56
- `test-scope-skill.py` — Inv 24
- `test-scope-scripts.py` — Inv 17, 18, 19, 20, 21, 22, 23, 25
- `test-new-feature-scaffolder.py` — Inv 33
- `test-audit-skill.py` — Inv 34, 35
- `test-audit-owner.py` — Inv 50
- `test-version-sync.py` — Inv 36
- `test-skill-md-frontmatter.py` — Inv 37
- `test-feature-json-summary.py` — Inv 38
- `test-contract-md.py` — Inv 39
- `test-manifest-shape.py` — Inv 40
- `test-manifest-deploys-correctly.py` — Inv 40
- `test-feature-new-plugin-mode.py` — Inv 44, 45, 46, 47, 48
- `test-new-skill.py` — Inv 32, 49
- `test-tdd-autonomous-configurable.py` — Inv 57
- `test-tdd-autonomous-command.py` — Inv 58
- `test-tdd-autonomous-alert.py` — Inv 59
