---
feature: tdd-subagent
version: 5.4.0
owner: rabbit-workflow team
template_version: 2.1.0
deprecation_criterion: When subagent dispatch is replaced by a different orchestration mechanism (e.g., direct rabbit-CLI orchestration without a dispatch-prompt assembler).
status: active
---

# tdd-subagent — Spec

## Purpose

Provides `dispatch-tdd-subagent.py` (a prompt assembler), `tdd-step.py`
(the forward-only TDD state machine), and the `tdd-subagent` agent
definition. The assembled prompt drives a single feature through the
8-step TDD cycle (LOCK → TEST-WRITE → TEST-RED → IMPLEMENT →
SYNC-DEPLOYED → CODE-REVIEW → TEST-GREEN → UNLOCK), invoking
`tdd-step.py` at each state transition. Spec context-loading and the
human-approval gate are the dispatcher's responsibility, not the
subagent's.

The `rabbit-feature-touch` orchestration skill that consumes this
feature's dispatch prompt is owned by `rabbit-feature`. The retired
`tdd-state-machine` feature was absorbed into this one at v4.0.0; its
14 invariants now appear below renumbered as Inv 31–44.

## Scripting Tech Stack

All scripts in this feature are Python 3 standard library. Bash is not
used in runtime scripts, test harnesses, or fixtures. The sole test
runner is `test/run.py`.

## Surface

- `scripts/dispatch-tdd-subagent.py` — assembles a per-feature TDD-cycle
  prompt to stdout; the script itself does not invoke any agent.
- `scripts/tdd-step.py` — the forward-only TDD state machine
  (`show | next | transitions | transition`); invoked by the assembled
  prompt at each state transition (and directly by any other caller that
  needs to advance a feature's `tdd_state`).
- `agents/tdd-subagent.md` — the agent definition dispatched by callers
  using the assembled prompt.

## Pre-Conditions

Callers MUST commit the spec file referenced by `--spec` BEFORE
invocation; the dispatcher's spec-authoring step must produce a clean
committed baseline so the embedded `{spec_content}` interpolation in
the assembled prompt reflects the post-edit state. Codification of the
upstream commit obligation lives in the caller's spec
(`rabbit-feature`).

## Invariants

**Note on the prompt-contract migration.** As of the CONTRACT-BACKLOG-1
Phase B cycle, `dispatch-tdd-subagent.py` no longer assembles its
output via an inline Python f-string. Instead it builds a slot dict and
delegates assembly to `.claude/features/contract/scripts/build-prompt.py`,
which substitutes against the template at
`.claude/features/contract/templates/prompts/tdd-subagent.txt` (landed
by contract Inv 57) and prepends the policy block from the entry's
`inject` list. Every invariant below whose constraint applies to the
content of the dispatched prompt (Inv 7–22, plus the assembled output
referenced by Inv 23/24) MUST be read as constraining the template
file's content rather than any inline f-string in the dispatch script.
Invariants 23 and 24 retain their script-level constraint on how the
`bypass_preamble_note` slot value is COMPUTED (via `rabbit_print`),
but where that value APPEARS in the dispatched output is governed by
the template's `{{bypass_preamble_note}}` placeholder.

### Surface scope

1. **Owned surface.** This feature owns exactly three surface entries:
   `scripts/dispatch-tdd-subagent.py`, `scripts/tdd-step.py`, and
   `agents/tdd-subagent.md`. The state-machine script `tdd-step.py`
   lives at `.claude/features/tdd-subagent/scripts/tdd-step.py`
   (absorbed from the retired `tdd-state-machine` feature at v4.0.0).
   The `.claude/features/tdd-state-machine/` directory MUST NOT exist.

2. **`feature.json` surface fields.** `surface.hooks`, `surface.commands`,
   and `surface.skills` in `feature.json` are each `[]`. This feature
   exposes no hooks, commands, or skills.

### Dispatch script — CLI shape

3. **Output mode.** `dispatch-tdd-subagent.py` writes the assembled
   prompt to stdout and exits without invoking any agent. Exit codes:
   `0` success, `2` invocation error (missing required flag, missing
   `--spec` file, `--max-iterations < 1`, unknown `--scope` feature).

4. **Flag set.** `dispatch-tdd-subagent.py` accepts exactly these flags:
   `--scope` (required), `--spec` (required),
   `--impl-suggestion` (optional path),
   `--code-review-full-loop` (boolean flag),
   `--max-iterations N` (default `3`, minimum `1`).

5. *(Retired — see CHANGELOG.md.)*

6. *(Retired — see CHANGELOG.md.)*

### Dispatch script — prompt content

7. **Scope marker convention.** The assembled prompt instructs the
   subagent to use `.rabbit-scope-active-<feature-name>` as its sole
   scope marker, written at LOCK and removed at UNLOCK. Distinct
   per-feature markers permit simultaneous dispatch across features.

8. **8-step section banners.** The assembled prompt contains a labelled
   section per step using the names `LOCK`, `TEST-WRITE`, `TEST-RED`,
   `IMPLEMENT`, `SYNC-DEPLOYED`, `CODE-REVIEW`, `TEST-GREEN`, `UNLOCK`,
   in that order, numbered STEP 1 through STEP 8. Spec context-loading
   and human approval are owned by the dispatcher (`rabbit-feature-touch`)
   and absent from the assembled prompt.

9. **E2E test rule.** The assembled prompt declares that every spec
   behaviour MUST have a corresponding end-to-end test, and that the
   subagent adds missing e2e tests in TEST-WRITE.

10. **Scope-boundary red flag.** The assembled prompt forbids the
    subagent from creating any `.rabbit-scope-active-<X>` marker where
    `<X>` differs from the declared scope feature. If implementation
    requires writing under another feature's directory, the subagent
    STOPS and emits a blocked HANDOFF with fields `tdd_state: blocked`,
    `test_result: not_run`, `cross_feature_dependency: <X>`,
    `unwritten_paths: [<path>, ...]`, and `notes: <one sentence>`.

11. **SKILL.md routing rule.** The assembled prompt's IMPLEMENT step
    instructs the subagent to invoke
    `Skill("skill-creator:skill-creator")` before editing any file whose
    basename is `SKILL.md`. Direct Write/Edit on a `SKILL.md` is
    forbidden.

12. **LOCK / UNLOCK marker discipline (mode-aware).** The assembled prompt's LOCK step writes ONE scope marker and registers no shell trap; the UNLOCK step removes the same marker after the chore commit and before HANDOFF. The marker path is mode-aware, matching rabbit-cage's scope-guard expectation per Inv 17(b):
    - **Standalone mode** (mode marker absent or `standalone`): marker at `<repo_root>/.rabbit-scope-active-<feature>` (repo-root, dashed-name form).
    - **Plugin mode** (`<repo_root>/.rabbit/.runtime/mode == 'plugin'`): marker at `<repo_root>/.rabbit/.runtime/scope-active-<feature>` (`.runtime/` subdir of the rabbit install, `scope-active-` prefix without leading dot).
    The mode-detection MUST happen at prompt-assembly time (in `dispatch-tdd-subagent.py`, NOT at subagent execution time) so that the assembled LOCK and UNLOCK lines contain the literal correct path for the current installation. Before this invariant was made mode-aware, the assembled prompt always emitted the standalone path, which produced an inert scope marker in plugin mode (scope-guard couldn't find it at the expected `<rabbit_root>/.runtime/scope-active-<name>` location) and made plugin-mode TDD cycles silently bypass scope discipline. Enforced by `test/test-prompt-lock-unlock-marker-path.py` which asserts: (a) in standalone mode (no `.rabbit/.runtime/mode` set), assembled prompt's LOCK line ends with `.rabbit-scope-active-<feature>` and UNLOCK matches; (b) in plugin mode (`.rabbit/.runtime/mode='plugin'`), assembled prompt's LOCK line ends with `.rabbit/.runtime/scope-active-<feature>` (note the slash-separated `.runtime/scope-active-` form, not the dashed standalone form) and UNLOCK matches. Both subprocess scenarios run dispatch-tdd-subagent.py against tmpdir fixtures.

13. *(Retired — see CHANGELOG.md.)*

14. **IMPLEMENT/SYNC-DEPLOYED commit ordering.** Within the IMPLEMENT step,
    the assembled prompt instructs the subagent to write code (Edit/Write)
    and stage the feature-local changes (`git add <feature_dir>/`) but to
    DEFER the commit until the end of SYNC-DEPLOYED (per Inv 46). The
    `tdd-step.py transition <feature_dir> impl` call happens at the end
    of IMPLEMENT (post-stage, pre-commit) so the impl state advance
    records "code written" without the commit yet.

15. **TEST-GREEN impl-SHA capture.** The assembled prompt's TEST-GREEN
    step captures `IMPL_SHA=$(git rev-parse HEAD)` and writes
    `<repo_root>/.rabbit/tdd-report-<feature>.json` with `impl_commit`
    bound to that SHA, BEFORE the UNLOCK chore commit advances HEAD.

16. **UNLOCK chore commit.** The assembled prompt's UNLOCK step commits
    the `feature.json` `tdd_state: test-green` transition with message
    pattern `chore(<feature>): advance tdd_state to test-green` BEFORE
    emitting HANDOFF.

17. **CODE-REVIEW skill invocation.** The assembled prompt's CODE-REVIEW
    step invokes `Skill("superpowers:requesting-code-review")`. The
    skill name is exact and case-sensitive.

18. **Read-before-Edit warning.** The assembled prompt's IMPLEMENT step
    states that any `Edit`/`Write` against an existing file MUST be
    preceded by a `Read` in the same session, as the Claude Code Edit
    tool rejects edits on un-Read files.

19. *(Retired — see CHANGELOG.md.)*

20. *(Retired — see CHANGELOG.md.)*

21. **HANDOFF `closed_items` field.** The assembled prompt's HANDOFF
    JSON block declares `closed_items` as an empty list (the field is
    retained on the HANDOFF schema for forward compatibility per Inv 22
    even though the dispatcher no longer emits item-close instructions).

30. *(Retired — see CHANGELOG.md.)*

### HANDOFF schema

22. **Dual HANDOFF emission.** The assembled prompt instructs the
    subagent to emit two HANDOFF blocks at completion: a YAML-style
    `HANDOFF:` block (the human-readable view) followed immediately by
    a fenced JSON block prefixed `HANDOFF_JSON:` (the machine-first
    source of truth). The JSON block includes
    `handoff_schema_version: "1.0.0"` and the fields `feature`,
    `tdd_state`, `test_result`, `spec_compliance`, `tdd_report_path`,
    `closed_items`, `notes`.

### Bypass-marker preamble note

23. **Bypass-marker note emission.** When `.rabbit-human-approval-bypass`
    exists at the repo root, the assembled prompt's preamble (before
    STEP 1) contains the exact string returned by
    `rabbit_print(_BYPASS_NOTE_TEXT, "📢", "yellow")` (the canonical
    preamble body lives in `dispatch-tdd-subagent.py` as the module-level
    `_BYPASS_NOTE_TEXT` constant). When the marker is absent, no such
    note appears.

24. **Bypass-marker note channel.** `dispatch-tdd-subagent.py` emits the
    bypass preamble note solely by calling `rabbit_print` from
    `.claude/features/contract/scripts/rabbit_print.py`. The script
    contains no inline ANSI escape codes and no inline brand strings.

### `--human-approval-gate` branch (retired)

25. *(Retired — see CHANGELOG.md.)*

26. *(Retired — see CHANGELOG.md.)*

### Agent definition

27. **Single state-machine path in agent doc.** `agents/tdd-subagent.md`
    instructs the subagent to use the absolute `tdd-step.py` path
    supplied by the dispatched prompt. It does not describe a dual-path
    layout (agent-local OR feature-local).

### `feature.json` schema

28. **`feature.json` schema source.** The canonical `feature.json`
    schema lives at
    `.claude/features/contract/schemas/feature.json.schema.json`. This
    feature's `feature.json` conforms to that schema. Test fixtures in
    this feature use the same flat field shape (`name`, `version`,
    `owner`, `tdd_state`, `summary`, `surface`, `deprecation_criterion`).

29. **Meta-contract sections.** `feature.json` MUST
    declare the meta-contract sections `manifest`, `runtime`, and
    `configuration`. The shapes are exactly:

    - `manifest` is a list of length 3 whose entries are, in order:
      1. `{"api": "publish_agent", "args": {"source":
         "agents/tdd-subagent.md"}}` — deploys the agent definition.
         `publish_agent` is a convenience wrapper that auto-derives the
         dest as `.claude/agents/<basename of source>`, yielding
         `.claude/agents/tdd-subagent.md`.
      2. `{"api": "publish_file", "args": {"source":
         "scripts/dispatch-tdd-subagent.py", "dest":
         ".claude/agents/tdd-subagent/scripts/dispatch-tdd-subagent.py"}}`
         — deploys the dispatch script into the agent's adjacent scripts
         directory. `publish_file` requires explicit `dest` because the
         deployment path is NOT the `.claude/agents/<basename>` location
         that `publish_agent` would derive.
      3. `{"api": "publish_file", "args": {"source":
         "scripts/tdd-step.py", "dest":
         ".claude/agents/tdd-subagent/scripts/tdd-step.py"}}` — deploys
         the state-machine script into the agent's adjacent scripts
         directory so the dispatched subagent can invoke `tdd-step.py`
         from a colocated path. (Pre-v4.0.0 this entry lived on
         `tdd-state-machine`'s manifest as a cross-feature publish_file;
         post-absorption the source path is intra-feature.)
    - `runtime` is `{}` — tdd-subagent owns no Claude Code event hook
      handlers (consistent with `surface.hooks: []`).
    - `configuration` is `[]` — tdd-subagent exposes no
      user-configurable toggles.

    The manifest is the meta-contract source of truth for what
    tdd-subagent deploys. The `publish_file` entries use `dest` to match
    the canonical `publish_file` shape.

### State machine — schema/behaviour

The 13 invariants in this section were absorbed from the retired
`tdd-state-machine` feature at v4.0.0. They constrain
`scripts/tdd-step.py`.

31. **Valid state set.** The valid `tdd_state` values are exactly:
    `spec`, `spec-update`, `test-red`, `impl`, `sync-deployed`,
    `test-green`, `deprecated`. `transition` rejects any other target
    value with exit `1`. The `sync-deployed` state was added in v5.1.0
    per Inv 46 to land the 8-step cycle's new step at the state-machine
    level.

32. **Primary forward order.** The primary forward order is:
    `spec -> spec-update -> test-red -> impl -> sync-deployed ->
    test-green -> deprecated`. Without `--force`, a transition is
    accepted only when the new state is the primary forward target of
    the current state (or the alternate target defined in Inv 33).

33. **Alternate forward edge.** From `test-green`, the alternate forward
    target `spec-update` is accepted without `--force`. This is the only
    alternate forward edge in the state machine and lets a feature start
    a fresh cycle without going through `deprecated`.

34. **Backward transitions require `--force`.** Any transition that is
    not a forward edge (per Inv 32 or Inv 33) is rejected with exit `1`
    unless `--force` is supplied. With `--force`, a transition between
    any two non-terminal states is accepted.

35. **`deprecated` is terminal.** From `deprecated`, every transition is
    rejected with exit `1`, including when `--force` is supplied.

36. **`tdd-step.py` location.** `scripts/tdd-step.py` MUST be present at
    `.claude/features/tdd-subagent/scripts/tdd-step.py`. The retired
    `.claude/features/tdd-state-machine/` directory MUST NOT exist.

37. **Executable bit.** `scripts/tdd-step.py` is stored with the
    user-executable bit set (any mode satisfying `mode & 0o100`; in
    practice `0o755` or `0o775` depending on the contributor's umask).

38. **`spec-update -> test-red` precondition.** The transition
    `spec-update -> test-red` is accepted only when at least one of the
    following holds:

    - `git diff HEAD` under `<feature-dir>/docs/spec/` is non-empty, OR
    - `--spec-no-change-reason <reason>` is supplied with a non-empty
      reason; the reason is persisted on `feature.json` as
      `spec_no_change_reason`.

    When neither holds, the transition is denied with exit `1`.

39. **Branding render via `rabbit_print`.** `tdd-step.py` MUST render
    every transition message through the centralised `rabbit_print`
    module loaded from `.claude/features/contract/scripts/rabbit_print.py`.
    Accepted transitions emit
    `rabbit_print("{CUR} -> {NEW}", "🔧", "green")` on stdout (ANSI
    green, `[🐇 rabbit 🐇]` brand). Forced transitions additionally
    emit `rabbit_print("FORCED: {CUR} -> {NEW}", "🔧", "red")` on
    stderr (ANSI red). State names are uppercased at the call site.

40. **`test-green` enforcement-check hook.** After a successful
    transition into `test-green`, `tdd-step.py` calls each of the
    following functions from `contract.lib.checks` in-process:

    - `check_tests_non_interactive`
    - `check_sentinel`
    - `check_naming`
    - `check_imports_resolve`
    - `check_symlinks_resolve`
    - `check_template_producer_consistency`

    A non-passed `CheckResult` from any of these emits a non-empty
    warning via `rabbit_print` on stderr. The hook is best-effort and
    never blocks the transition.

41. **`spec-update -> test-red` numbered-list check.** After a
    successful transition `spec-update -> test-red`, `tdd-step.py`
    calls `contract.lib.checks.check_numbered_lists` against
    `<feature-dir>/docs/spec/`. A non-passed `CheckResult` emits a
    warning via `rabbit_print` on stderr but does NOT block the
    transition. The Inv 38 gate remains the only blocking precondition
    for this transition.

42. **In-process library imports (no subprocess to CLI shims).** The
    check functions used by Inv 40 and Inv 41 are imported from the
    `contract.lib.checks` library module at
    `.claude/features/contract/lib/checks.py` and invoked in-process.
    `tdd-step.py` MUST NOT fan out via `subprocess` to the
    `.claude/features/contract/scripts/enforcement/check-*.py` CLI
    shims for any of these checks.

43. **`tdd-step.py` manifest entry.** `feature.json`'s `manifest` (per
    Inv 29) contains the third entry that publishes `tdd-step.py` to
    the agent's adjacent scripts directory. The intra-feature source
    path (`scripts/tdd-step.py`) and the agent-adjacent dest
    (`.claude/agents/tdd-subagent/scripts/tdd-step.py`) together
    declare the deployment of this script.

44. **`feature.json` `prompts` section + dispatcher uses `build-prompt.py`.**
    `feature.json` MUST declare a `prompts` array containing EXACTLY ONE
    entry with these field values:
    - `id: "tdd-subagent"`
    - `kind: "subagent"`
    - `inject: [".claude/features/policy/philosophy.md", ".claude/features/policy/spec-rules.md", ".claude/features/policy/coding-rules.md"]`
    - `slots: ["feature_name", "spec_content", "impl_suggestion_block", "bypass_preamble_note", "feature_dir", "tdd_step_py", "repo_root", "max_iterations", "code_review_loop_note"]`

    The matching template at
    `.claude/features/contract/templates/prompts/tdd-subagent.txt`
    (landed by contract Inv 57) supplies the body. `scripts/dispatch-tdd-subagent.py`
    MUST NOT assemble the prompt inline via Python f-string — it MUST
    instead build a dict mapping each declared slot name to its
    computed value, invoke
    `python3 .claude/features/contract/scripts/build-prompt.py
    --callable-id tdd-subagent --slot <name>=<value>` (one `--slot`
    per slot) via subprocess, read the resulting prompt file from the
    path printed to stdout by the assembler, and write that file's
    contents to its own stdout. The dispatcher's CLI shape
    (`--scope`, `--spec`, `--impl-suggestion`, `--code-review-full-loop`,
    `--max-iterations`) and its argument validation MUST remain
    consistent with Inv 3 and Inv 4. The previous
    `_policy_block` helper function and its call site (which
    subprocessed to `policy-block.py`) MUST be removed — the policy
    block is now prepended by `build-prompt.py` from the entry's
    `inject` list per contract Inv 54. Enforced by
    `test/test-dispatch-uses-build-prompt.py`; the existing 23
    prompt-content tests (test-prompt-structure.py,
    test-prompt-lock-unlock.py, test-prompt-scope-boundary.py,
    test-prompt-implement-rules.py, test-prompt-commit-order.py,
    test-prompt-code-review.py, test-bypass-marker-note.py, etc.) act
    as the regression net confirming the dispatched output is
    byte-equivalent to the prior f-string assembly.

45. **TEST-GREEN must emit `test_result: fail` on nonzero run.py exit.**
    The dispatched-subagent template at
    `.claude/features/contract/templates/prompts/tdd-subagent.txt`
    governs what the dispatched subagent says. It MUST satisfy three
    properties at STEP 6 (TEST-GREEN) and HANDOFF:

    (a) **Nonzero-exit conditional in STEP 6.** STEP 6 MUST contain
    explicit instructions that if `python3 <feature_dir>/test/run.py`
    exits nonzero, the subagent STOPS immediately and emits a
    fail-HANDOFF (both YAML and JSON forms) carrying `tdd_state: impl`,
    `test_result: fail`, `spec_compliance: fail`, `tdd_report_path:
    null`, and a `notes` field naming the exit-code failure. The
    subagent MUST NOT proceed to STEP 7 (UNLOCK) when run.py exits
    nonzero — i.e., no `chore(<feature>): advance tdd_state to
    test-green` commit, no scope-marker removal in the normal-path
    flow, and no test-green HANDOFF emission. Pre-existing failures,
    out-of-scope failures, and "I think this one is unrelated"
    triage are NOT acceptable subagent-side judgments — the subagent
    reports the exit code faithfully and uses the `notes` field if
    additional context is warranted.

    (b) **No hard-coded `pass` literal for `test_result`.** The
    template MUST NOT contain the literal text `"test_result": "pass"`
    or `test_result: pass` anywhere in its tdd-report block, YAML
    HANDOFF block, or JSON HANDOFF block. The value MUST appear as a
    `<pass|fail>` placeholder (with whatever quoting the format
    requires) so the subagent is forced to substitute the actual
    outcome rather than copying the literal `pass` from the template.

    (c) **Template version bump.** The template's
    `template_version` marker is bumped from `1.0.0` to `1.1.0` to
    signal this behavioral change (subagents following v1.0.0 cannot
    emit `test_result: fail` from the normal completion path).

    Enforced by `test/test-prompt-test-green-handles-failure.py`
    which reads the template at
    `.claude/features/contract/templates/prompts/tdd-subagent.txt`
    and asserts (i) STEP 6 section contains a nonzero-exit conditional
    naming `test_result: fail`, (ii) no literal `"test_result": "pass"`
    or `test_result: pass` appears anywhere in the template, (iii)
    `<pass|fail>` placeholder appears in the tdd-report block, YAML
    HANDOFF block, and JSON HANDOFF block. The template file itself
    lives under the contract feature's `templates/prompts/` directory
    (per contract Inv 57); editing it is a cross-feature operation
    relative to tdd-subagent's scope, so this invariant's
    implementation MAY require a coordinated edit on the contract
    feature or a scope-override on the template file.

46. **STEP 5 SYNC-DEPLOYED — publish-sync the deployed copies before commit.** STEP 5 of the 8-step cycle (per Inv 8) MUST appear between IMPLEMENT (STEP 4) and CODE-REVIEW (STEP 6) and MUST instruct the subagent to: (a) enumerate every `publish_file`, `publish_hook`, `publish_skill`, and `publish_settings` entry in the feature-under-scope's `feature.json manifest`; (b) for each entry, invoke the corresponding `contract.lib.publish.<api>` function in-process (lazy-import from `.claude/features/contract/lib/publish.py`) — or, equivalently, invoke `run_publish_loop(target_root=<repo_root>)` scoped to this single feature via subprocess — so every deployed destination is byte-equal to its feature-local source-of-truth; (c) `git add` every deployed path that publishing modified, in addition to the already-staged feature-local source changes from STEP 4; (d) at the END of STEP 5, perform the SINGLE atomic commit `git commit -m "fix|feat(<feature>): <summary>"` covering BOTH the feature-local source changes (staged in STEP 4 per Inv 14) AND the deployed-copy sync (staged in step (c) above); (e) immediately after the commit, invoke `tdd-step.py transition <feature_dir> sync-deployed` to advance the state machine into `sync-deployed` (per Inv 31/32). If ANY publish call in step (b) returns a non-passed `CheckResult`, the subagent MUST stop, emit a fail-HANDOFF with `tdd_state: impl`, `test_result: not_run`, `spec_compliance: fail`, `tdd_report_path: null`, `notes: "SYNC-DEPLOYED failed: <api>(<source>) returned <message>"`, and MUST NOT proceed to CODE-REVIEW or commit. This makes the feature-local/deployed-copy drift class — the source of 4 fix-up commits between PRs #257 and #270 — impossible by construction: every deployed artifact is byte-equal to its source AT impl-commit time, not later when `check_manifest_drift` re-syncs at the next Stop hook. Enforced by `test/test-prompt-sync-deployed-step.py` which reads the template at `.claude/features/contract/templates/prompts/tdd-subagent.txt` and asserts: (i) STEP 5 section header is `SYNC-DEPLOYED`, (ii) step body names `publish_file`, `publish_hook`, `publish_skill`, and `publish_settings` explicitly, (iii) step body instructs `git add` of deployed paths AND the single atomic commit at end-of-step, (iv) step body instructs `tdd-step.py transition <feature_dir> sync-deployed` AFTER the commit, (v) step body specifies the fail-HANDOFF shape on publish failure with `tdd_state: impl`. The template file edit is a cross-feature operation relative to tdd-subagent's scope (template lives under contract per Inv 57) and MAY require a coordinated edit on the contract feature or a scope-override on the template file. The new `sync-deployed` state in the `tdd-step.py` state machine (Inv 31/32) lands the step at the state-machine level alongside the prompt-level step.

47. **`dispatch-tdd-subagent.py` plugin-mode root resolution.** `dispatch-tdd-subagent.py` MUST prefer the `RABBIT_ROOT` environment variable (set by `install.py` per rabbit-cage Inv 19) when resolving the repo root used to (a) locate `find-feature.py` at `<repo_root>/.claude/features/contract/scripts/find-feature.py`, and (b) pass as the `--repo` argument to the same `find-feature.py` invocation. Both uses share a single resolved `repo_root` value — the script MUST NOT split them across two different roots. Fallback ordering, highest precedence first:

    (a) `os.environ.get("RABBIT_ROOT")` — when set (plugin mode, set by `install.py main()` per rabbit-cage Inv 19), use verbatim. In plugin mode the value is `<host>/.rabbit/`, which (i) contains `.claude/features/contract/scripts/find-feature.py` at the expected relative location, and (ii) is recognized by `find-feature.py`'s plugin-mode dual-detection (contract Inv 23 amended form) via `<repo>/.runtime/mode == "plugin"` so the find returns both rabbit-internal MVP features AND `rabbit-project/features/` user-project features.

    (b) `git rev-parse --show-toplevel` (run with `cwd=<script_dir>`) — fallback when `RABBIT_ROOT` is unset (standalone-workspace mode). The git toplevel is the rabbit-self repo root in standalone, which contains `.claude/features/contract/scripts/find-feature.py` directly.

    Mirroring constraint: this matches the resolution pattern already in `rabbit-feature/scripts/resolve-scope.py` (lines ~60–70), so any caller of `find-feature.py` in the rabbit ecosystem uses the same precedence ladder. Divergence between the two sites was the root cause of #301/#302 — `resolve-scope.py` used `RABBIT_ROOT` correctly but `dispatch-tdd-subagent.py` jumped straight to `git rev-parse`, producing `<host_root>` and then a non-existent `find-feature.py` path in plugin installs.

    Enforced by `test/test-dispatch-plugin-mode-root.py` (new), which:
    - Scenario A (standalone): unset `RABBIT_ROOT`, set cwd to a tmpdir containing `.git/` and `.claude/features/contract/scripts/find-feature.py`, invoke `dispatch-tdd-subagent.py --scope <known-feature> ...`, assert the call succeeds and finds the feature.
    - Scenario B (plugin, RABBIT_ROOT set): set `RABBIT_ROOT=<tmp>/.rabbit`, populate `<tmp>/.rabbit/.claude/features/contract/scripts/find-feature.py` + `<tmp>/.rabbit/.runtime/mode='plugin'` + `<tmp>/.rabbit/rabbit-project/features/run-ingest/feature.json`, invoke the dispatcher with `--scope run-ingest`, assert it succeeds and locates the project feature.
    - Scenario C (regression for #301): plugin layout, RABBIT_ROOT set, assert the dispatcher does NOT fall back to git rev-parse (a stale `<host>/.claude/...` path) — verify by setting `<tmp>` to a directory that has `.git/` at host level but NO `.claude/` at host level; correct behavior must use `RABBIT_ROOT` and not error on the missing host-level `.claude/`.

48. **No doubled `.rabbit/.rabbit/` in assembled prompt paths.** The assembled prompt MUST NOT contain the literal substring `.rabbit/.rabbit/` anywhere — neither in STEP 1 LOCK (scope marker), STEP 7 mkdir, STEP 7 `Path:` for the tdd-report, STEP 8 UNLOCK, nor the HANDOFF block's `tdd_report_path` field. The doubling occurs when the template hardcodes `{{repo_root}}/.rabbit/<rest>` BUT the dispatcher's `repo_root` resolves to `RABBIT_ROOT` (= `<host>/.rabbit/`) per Inv 47 — the result is `<host>/.rabbit/.rabbit/<rest>`, a non-existent path.

    The fix is path-construction discipline in `dispatch-tdd-subagent.py`:
    - The dispatcher MUST compute the canonical `tdd_report_path` at prompt-assembly time, choosing per mode:
      - **Plugin** (RABBIT_ROOT set, or `.rabbit/.runtime/mode == 'plugin'` detected): `<rabbit_root>/tdd-report-<feature>.json` where `<rabbit_root>` is the resolved `RABBIT_ROOT`.
      - **Standalone**: `<repo_root>/.rabbit/tdd-report-<feature>.json` where `<repo_root>` is the git toplevel.
    - The dispatcher plumbs the resolved `tdd_report_path` value into a single template slot (e.g. `{{tdd_report_path}}`) — every reference in STEP 7 and HANDOFF uses the SAME computed value.
    - Similarly, the mkdir target `mkdir -p <dir>` uses `os.path.dirname(tdd_report_path)`, so the directory is also per-mode-correct.
    - The scope marker path is already handled by the `{{scope_marker_path}}` slot per Inv 12 amended — verify no remaining hardcoded `{{repo_root}}/.rabbit-scope-active-...` lines exist in STEP 1 LOCK or STEP 8 UNLOCK template body, EXCEPT the descriptive prose block (Inv 7 'Scope marker convention' which documents the standalone naming convention as illustration — that's commentary, not an executable instruction).

    Enforced by `test/test-prompt-no-doubled-rabbit-paths.py`:
    - Scenario A: standalone tmpdir (no RABBIT_ROOT env, no `.rabbit/.runtime/mode`). Invoke dispatch.py via subprocess; assert the full assembled stdout does NOT contain the substring `.rabbit/.rabbit/`.
    - Scenario B: plugin tmpdir (`.rabbit/.runtime/mode='plugin'` + `RABBIT_ROOT=<tmp>/.rabbit`). Invoke dispatch.py; assert the assembled stdout does NOT contain `.rabbit/.rabbit/` AND the STEP 7 `Path:` line ends with `<tmp>/.rabbit/tdd-report-<feature>.json` (single `.rabbit/`, not doubled).
    - Both scenarios pin the absence of the doubled substring as a single, easy-to-grep regression assertion.

## Out of Scope

- Deployment of the assembled scripts into `.claude/agents/` — owned by
  the `contract` feature.
- The `rabbit-feature-touch` orchestration skill and its SKILL.md
  content — owned by `rabbit-feature`.
- Validation of the `feature.json` schema (this feature relies on the
  schema; the contract feature owns and validates it).
- The confirm-token bypass authorization protocol (writing
  `.rabbit-scope-override` and `.rabbit-scope-active`) — implemented by
  the `rabbit-cage` scope-guard and documented in `rabbit-feature`'s
  SKILL.md.
