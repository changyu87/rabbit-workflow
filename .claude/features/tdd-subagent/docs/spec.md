---
feature: tdd-subagent
version: 5.27.1
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
Step-4 tdd-autonomous approval gate are the dispatcher's responsibility,
not the subagent's.

The `rabbit-feature-touch` orchestration skill that consumes this
feature's dispatch prompt is owned by `rabbit-feature`. This feature
owns the state-machine surface (Inv 31–44).

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
- `agents/rabbit-tdd-subagent.md` — the agent definition dispatched by
  callers using the assembled prompt. The agent manifest item is named
  `rabbit-tdd-subagent` (the agent `name:` frontmatter and the deployed
  `.claude/agents/rabbit-tdd-subagent.md` basename); the feature
  directory and the `dispatch-tdd-subagent.py` / `tdd-step.py` scripts
  keep their `tdd-subagent` names.

## Pre-Conditions

Callers MUST commit the spec file referenced by `--spec` BEFORE
invocation; the dispatcher's spec-authoring step must produce a clean
committed baseline so the embedded `{spec_content}` interpolation in
the assembled prompt reflects the post-edit state. Codification of the
upstream commit obligation lives in the caller's spec
(`rabbit-feature`).

## Invariants

`dispatch-tdd-subagent.py` delegates prompt assembly to
`.claude/features/contract/scripts/build-prompt.py` against the template at
`.claude/features/contract/templates/prompts/tdd-subagent.txt` (see Inv 44).
Every invariant below whose constraint applies to the content of the
dispatched prompt constrains that template file.

### Surface scope

1. **Owned surface.** This feature owns exactly three surface entries:
   `scripts/dispatch-tdd-subagent.py`, `scripts/tdd-step.py`, and
   `agents/rabbit-tdd-subagent.md`. The state-machine script `tdd-step.py`
   lives at `.claude/features/tdd-subagent/scripts/tdd-step.py`.
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
   `--affected-invariants N[,N,...]` (optional; comma-separated list of invariant numbers; when provided, the assembled prompt embeds ONLY the named invariants instead of the full ## Invariants section — see Inv 49 for semantics),
   `--code-review-full-loop` (boolean flag),
   `--max-iterations N` (default `3`, minimum `1`).

5. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

6. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

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
    - **Vendored mode** (`<repo_root>/.rabbit/.runtime/mode` is `vendored` or the legacy `plugin`): marker at `<repo_root>/.rabbit/.runtime/scope-active-<feature>` (`.runtime/` subdir of the rabbit install, `scope-active-` prefix without leading dot). The mode value is dual-accepted (`vendored`/`plugin`) to match scope-guard's `_VENDORED_MODES` set during the `plugin`->`vendored` rename coexistence window; a `vendored` install whose marker falls through to the standalone form leaves the subagent's in-scope writes blocked by scope-guard.
    The mode-detection MUST happen at prompt-assembly time (in `dispatch-tdd-subagent.py`, NOT at subagent execution time) so the assembled LOCK and UNLOCK lines contain the literal correct path for the current installation. Enforced by `test/test-prompt-lock-unlock-marker-path.py`.

13. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

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

19. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

20. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

21. **HANDOFF `closed_items` field.** The assembled prompt's HANDOFF
    JSON block declares `closed_items` as an empty list, retained on the
    HANDOFF schema for forward compatibility per Inv 22.

30. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

### HANDOFF schema

22. **Dual HANDOFF emission.** The assembled prompt instructs the
    subagent to emit two HANDOFF blocks at completion: a YAML-style
    `HANDOFF:` block (the human-readable view) followed immediately by
    a fenced JSON block prefixed `HANDOFF_JSON:` (the machine-first
    source of truth). The JSON block includes
    `handoff_schema_version: "1.1.0"` and the fields `feature`,
    `tdd_state`, `test_result`, `spec_compliance`, `tdd_report_path`,
    `closed_items`, `notes`. The `1.1.0` version also carries the
    additive `aborted_reason` and `discovered_issues` fields (Inv 55);
    existing producers emit valid 1.1.0 HANDOFFs without populating them.

### Bypass-marker preamble note

23. **Bypass-marker note emission (dual-read).** When EITHER the canonical
    `.rabbit-tdd-autonomous` OR the legacy `.rabbit-human-approval-bypass`
    exists at the repo root, the bypass is treated as active and the
    assembled prompt's preamble (before STEP 1) contains the exact string
    returned by `rabbit_print(_BYPASS_NOTE_TEXT, "📢", "yellow")` (the
    canonical preamble body lives in `dispatch-tdd-subagent.py` as the
    module-level `_BYPASS_NOTE_TEXT` constant; it names both marker forms
    and tells the reader to re-enable the gate via
    `/rabbit-tdd-autonomous false`). When neither marker is present, no such
    note appears. The dual-read accepts either marker name for the duration
    of the coexistence window: dispatch reads either. The bypass-note
    emission is presence-only; it is independent of the `tdd-autonomous`
    configurable's polarity (`true` activates the bypass, `false` re-enables
    the gate), which the dispatcher's Step 4 owns.

24. **Bypass-marker note channel.** `dispatch-tdd-subagent.py` emits the
    bypass preamble note solely by calling `rabbit_print` from
    `.claude/features/contract/scripts/rabbit_print.py`. The script
    contains no inline ANSI escape codes and no inline brand strings.

### `--human-approval-gate` branch (withdrawn)

25. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

26. *(Withdrawn; not part of the current design — see CHANGELOG.md.)*

### Agent definition

27. **Single state-machine path in agent doc.** `agents/rabbit-tdd-subagent.md`
    instructs the subagent to use the absolute `tdd-step.py` path
    supplied by the dispatched prompt. It does not describe a dual-path
    layout (agent-local OR feature-local).

57. **Agent manifest item name.** The agent manifest item
    is named `rabbit-tdd-subagent`. The agent definition source lives at
    `agents/rabbit-tdd-subagent.md` and its YAML frontmatter declares
    `name: rabbit-tdd-subagent`. The `publish_agent` manifest entry
    deploys it to `.claude/agents/rabbit-tdd-subagent.md`. The legacy
    `agents/tdd-subagent.md` source and the legacy deployed
    `.claude/agents/tdd-subagent.md` MUST NOT exist. This rename is
    scoped to the AGENT manifest item only: the feature directory
    (`.claude/features/tdd-subagent/`), the `dispatch-tdd-subagent.py`
    and `tdd-step.py` script basenames, and the agent-adjacent deployed
    scripts directory (`.claude/agents/tdd-subagent/scripts/`) all keep
    their `tdd-subagent` names.

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
         "agents/rabbit-tdd-subagent.md"}}` — deploys the agent
         definition. `publish_agent` is a convenience wrapper that
         auto-derives the dest as `.claude/agents/<basename of source>`,
         yielding `.claude/agents/rabbit-tdd-subagent.md`.
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
         from a colocated path.
    - `runtime` is `{}` — tdd-subagent owns no Claude Code event hook
      handlers (consistent with `surface.hooks: []`).
    - `configuration` is `[]` — tdd-subagent exposes no
      user-configurable toggles.

    The manifest is the meta-contract source of truth for what
    tdd-subagent deploys. The `publish_file` entries use `dest` to match
    the canonical `publish_file` shape.

### State machine — schema/behaviour

The 13 invariants in this section constrain `scripts/tdd-step.py` (the
state-machine surface this feature owns).

31. **Valid state set.** The valid `tdd_state` values are exactly:
    `spec`, `spec-update`, `test-red`, `impl`, `sync-deployed`,
    `test-green`, `deprecated`. `transition` rejects any other target
    value with exit `1`. The `sync-deployed` state lands the 8-step
    cycle's STEP 5 at the state-machine level (Inv 46).

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
    `.claude/features/tdd-subagent/scripts/tdd-step.py`. The
    `.claude/features/tdd-state-machine/` directory MUST NOT exist.

37. **Executable bit.** `scripts/tdd-step.py` is stored with the
    user-executable bit set (any mode satisfying `mode & 0o100`).

38. **`spec-update -> test-red` precondition.** The transition
    `spec-update -> test-red` is accepted only when at least one of the
    following holds:

    - `git diff HEAD` under the feature's spec dir is non-empty. The spec
      dir is resolved dual-read: `<feature-dir>/specs/`
      is preferred, with the legacy `<feature-dir>/docs/spec/` honoured as a
      fallback during the coexistence window. OR
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
    calls `contract.lib.checks.check_numbered_lists` against the feature's
    spec dir, resolved dual-read (`<feature-dir>/specs/` preferred, legacy
    `<feature-dir>/docs/spec/` fallback). A
    non-passed `CheckResult` emits a
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
    supplies the body. `scripts/dispatch-tdd-subagent.py` MUST NOT
    assemble the prompt inline via Python f-string — it MUST instead build
    a dict mapping each declared slot name to its computed value, invoke
    `python3 .claude/features/contract/scripts/build-prompt.py
    --callable-id tdd-subagent --slot <name>=<value>` (one `--slot`
    per slot) via subprocess, read the resulting prompt file from the
    path printed to stdout by the assembler, and write that file's
    contents to its own stdout. The dispatcher's CLI shape
    (`--scope`, `--spec`, `--impl-suggestion`, `--code-review-full-loop`,
    `--max-iterations`) and its argument validation MUST remain
    consistent with Inv 3 and Inv 4. The policy block is prepended by
    `build-prompt.py` from the entry's `inject` list. Enforced by
    `test/test-dispatch-uses-build-prompt.py` plus the `test-prompt-*.py`
    prompt-content tests.

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

    Enforced by `test/test-prompt-test-green-handles-failure.py`
    (asserts STEP 6 contains a nonzero-exit conditional naming
    `test_result: fail`, no literal `"test_result": "pass"` /
    `test_result: pass` appears in the template, and the `<pass|fail>`
    placeholder appears in the tdd-report, YAML HANDOFF, and JSON HANDOFF
    blocks). The template lives under the contract feature (Inv 57), so
    editing it is a cross-feature operation.

46. **STEP 5 SYNC-DEPLOYED — publish-sync the deployed copies before commit.** STEP 5 of the 8-step cycle (per Inv 8) MUST appear between IMPLEMENT (STEP 4) and CODE-REVIEW (STEP 6) and MUST instruct the subagent to: (a) enumerate every `publish_file`, `publish_hook`, `publish_skill`, and `publish_settings` entry in the feature-under-scope's `feature.json manifest`; (b) for each entry, invoke the corresponding `contract.lib.publish.<api>` function in-process (lazy-import from `.claude/features/contract/lib/publish.py`) — or, equivalently, invoke `run_publish_loop(target_root=<repo_root>)` scoped to this single feature via subprocess — so every deployed destination is byte-equal to its feature-local source-of-truth; (c) `git add` every deployed path that publishing modified, in addition to the already-staged feature-local source changes from STEP 4; (d) at the END of STEP 5, perform the SINGLE atomic commit `git commit -m "fix|feat(<feature>): <summary>"` covering BOTH the feature-local source changes (staged in STEP 4 per Inv 14) AND the deployed-copy sync (staged in step (c) above); (e) immediately after the commit, invoke `tdd-step.py transition <feature_dir> sync-deployed` to advance the state machine into `sync-deployed` (per Inv 31/32). If ANY publish call in step (b) returns a non-passed `CheckResult`, the subagent MUST stop, emit a fail-HANDOFF with `tdd_state: impl`, `test_result: not_run`, `spec_compliance: fail`, `tdd_report_path: null`, `notes: "SYNC-DEPLOYED failed: <api>(<source>) returned <message>"`, and MUST NOT proceed to CODE-REVIEW or commit. This keeps every deployed artifact byte-equal to its source at impl-commit time. Enforced by `test/test-prompt-sync-deployed-step.py` (asserts the template's STEP 5 header, the four publish APIs, the `git add` + single atomic commit, the post-commit `tdd-step.py transition <feature_dir> sync-deployed`, and the publish-failure fail-HANDOFF shape). The template lives under the contract feature (Inv 57), so editing it is a cross-feature operation. The `sync-deployed` state (Inv 31/32) lands the step at the state-machine level.

47. **`dispatch-tdd-subagent.py` plugin-mode root resolution.** `dispatch-tdd-subagent.py` MUST prefer the `RABBIT_ROOT` environment variable (set by `install.py` per rabbit-cage Inv 19) when resolving the repo root used to (a) locate `find-feature.py` at `<repo_root>/.claude/features/contract/scripts/find-feature.py`, and (b) pass as the `--repo` argument to the same `find-feature.py` invocation. Both uses share a single resolved `repo_root` value — the script MUST NOT split them across two different roots. Fallback ordering, highest precedence first:

    (a) `os.environ.get("RABBIT_ROOT")` — when set (plugin mode, set by `install.py main()` per rabbit-cage Inv 19), use verbatim. In plugin mode the value is `<host>/.rabbit/`, which (i) contains `.claude/features/contract/scripts/find-feature.py` at the expected relative location, and (ii) is recognized by `find-feature.py`'s plugin-mode dual-detection (contract Inv 23 amended form) via `<repo>/.runtime/mode == "plugin"` so the find returns both rabbit-internal MVP features AND `rabbit-project/features/` user-project features.

    (b) `git rev-parse --show-toplevel` (run in the process CURRENT WORKING DIRECTORY, per Inv 60) — fallback when `RABBIT_ROOT` is unset (standalone-workspace mode). The git toplevel is the rabbit-self repo root in standalone (or the operating worktree under worktree-isolated dispatch), which contains `.claude/features/contract/scripts/find-feature.py` directly.

    Enforced by `test/test-dispatch-plugin-mode-root.py` (standalone,
    plugin RABBIT_ROOT-set, and git-rev-parse-fallback regression scenarios).

48. **No doubled `.rabbit/.rabbit/` in assembled prompt paths.** The assembled prompt MUST NOT contain the literal substring `.rabbit/.rabbit/` anywhere — neither in STEP 1 LOCK (scope marker), STEP 7 mkdir, STEP 7 `Path:` for the tdd-report, STEP 8 UNLOCK, nor the HANDOFF block's `tdd_report_path` field.

    Path-construction discipline in `dispatch-tdd-subagent.py`:
    - The dispatcher MUST compute the canonical `tdd_report_path` at prompt-assembly time as `<rabbit_runtime_root(repo_root)>/tdd-report-<feature>.json`, where `rabbit_runtime_root` is rabbit-cage's canonical single-`.rabbit` runtime-root resolver (`.claude/features/rabbit-cage/lib/runtime_root.py`, rabbit-cage Inv 52). The dispatcher CROSS-FEATURE INVOKES that resolver (lazy-imported via `importlib` from the install's feature tree, mirroring rabbit-cage's `session-start-dispatcher.py::_canonical_runtime_root`), instead of probing on-disk mode markers with a bespoke heuristic. The resolver keys off the resolved `repo_root` basename, yielding:
      - **Vendored** (`basename(repo_root) == ".rabbit"`; the dispatcher resolves `repo_root` to `RABBIT_ROOT`, which IS the vendored `.rabbit` install dir per Inv 47): `<repo_root>/tdd-report-<feature>.json` — the resolver returns `repo_root` unchanged, so NO doubled `.rabbit/.rabbit/` segment.
      - **Standalone** (any other basename; `repo_root` is the git toplevel): `<repo_root>/.rabbit/tdd-report-<feature>.json`.
      Anchoring on the canonical resolver removes the prior divergence where the bespoke mode-marker probe fell through to the standalone form for a vendored-basename `repo_root` carrying no on-disk mode marker, doubling the segment. When the rabbit-cage feature tree is not co-located under `repo_root` (degenerate / partial install), the dispatcher falls back to the resolver's own inline basename rule, so the result is identical without the cross-feature dependency present.
    - The dispatcher plumbs the resolved `tdd_report_path` value into a single template slot (e.g. `{{tdd_report_path}}`) — every reference in STEP 7 and HANDOFF uses the SAME computed value.
    - Similarly, the mkdir target `mkdir -p <dir>` uses `os.path.dirname(tdd_report_path)`, so the directory is also per-mode-correct.
    - The scope marker path is already handled by the `{{scope_marker_path}}` slot per Inv 12 amended — verify no remaining hardcoded `{{repo_root}}/.rabbit-scope-active-...` lines exist in STEP 1 LOCK or STEP 8 UNLOCK template body, EXCEPT the descriptive prose block (Inv 7 'Scope marker convention' which documents the standalone naming convention as illustration — that's commentary, not an executable instruction).

    Enforced by `test/test-prompt-no-doubled-rabbit-paths.py` (standalone,
    plugin, and vendored scenarios; all assert the absence of the doubled
    substring, and the vendored scenario asserts the report path roots at the
    rabbit-root rather than falling through to the standalone `.rabbit/` form).

49. **`--affected-invariants` scoped spec embedding.** The assembled prompt's spec embedding behavior is gated by the optional `--affected-invariants N[,N,...]` flag (see Inv 4 flag set):

    (a) **Default (flag omitted)** — embed the entire feature spec.md inline in the SPEC section. No migration required for any caller.

    (b) **Scoped (flag provided)** — embed ONLY the named invariants from the ## Invariants section, sandwiched between the spec preamble (everything BEFORE the ## Invariants heading: frontmatter, Purpose, Surface, Dispatcher Behavior, scope-guard Semantics, Installer Behavior, etc.) and the spec footer (everything AFTER the last invariant: ## Tech Stack, ## Out of Scope, etc.). The ## Invariants heading itself is preserved; in place of all invariants, the dispatcher splices in: (i) the requested invariants in numeric ascending order, separated by blank lines; (ii) a single concluding note line:

        `> NOTE: scoped view of N selected invariants ({list}) from <feature> spec.md; for related-but-unembedded invariants run \`grep '^<num>\\.' <spec-path>\` against the spec.`

        where `<spec-path>` is the repo-relative path of the `--spec` file the caller supplied (this resolves dual-read: `.claude/features/<feature>/specs/spec.md` for migrated features, the legacy `.claude/features/<feature>/docs/spec/spec.md` otherwise). When `--spec` is not under the repo root, the hint falls back to the canonical `.claude/features/<feature>/specs/spec.md`.

    (c) **Invariant lookup** — invariants are identified by the regex `^([0-9]+)\.\s` at the start of a line within the ## Invariants section. An invariant body extends from its number line to the line BEFORE the next invariant number (or to the end of the ## Invariants section if it's the last). Withdrawn invariants (whose body is the one-line withdrawal notice) are recognized AND retrievable — passing a withdrawn invariant number yields that notice, so the subagent sees that the number is allocated-but-withdrawn rather than missing.

    (d) **Unknown number — fatal.** If any requested number does NOT match an existing invariant in the spec (including withdrawn invariant slots), the dispatcher exits with code 1 and a stderr line `error: --affected-invariants includes unknown invariant number(s) for <feature>: [N, M]; available: [1..29]`. No silent skip.

    (e) **Size win.** Scoped prompts are smaller than the full-spec form; the win scales with feature spec size. No worse than the unscoped form when omitted.

    (f) **Caller convention.** The impl-suggestion file (`<repo_root>/.rabbit/impl-suggestion-<feature>.json`) MAY include an optional top-level `affected_invariants: [N, M, ...]` field; the dispatcher caller (rabbit-feature-touch Step 5) MAY plumb that field into `--affected-invariants` when present. This is OPTIONAL and per-caller — the spec only mandates the dispatcher's behavior when the flag IS supplied; whether to supply it is the caller's choice.

    Enforced by `test/test-affected-invariants-flag.py` (flag-omitted
    baseline, valid-subset, unknown-number-fatal, and size-win scenarios).

### State machine — abort subcommand

The invariants below (Inv 50–54) define the abort mechanism extending the
state-machine surface (`tdd-step.py`). The HANDOFF JSON fields
`aborted_reason` and `discovered_issues` that abort callers populate are
defined in Inv 55.

50. **`abort` subcommand.** `tdd-step.py` MUST expose a fifth
    subcommand `abort <feature_dir> --reason <code>` (in addition to
    `show`, `next`, `transitions`, `transition` per the Surface
    section). The positional `<feature_dir>` matches the existing
    `transition` shape (Inv 14, Inv 46). `--reason <code>` is required —
    abort without a recorded reason is rejected with exit code `2`
    (invocation error). Reason codes are free-form short tags;
    convention is `<short-tag>` such as `blocked-by-<issue>`,
    `discovered-blocker`, `external-dep-missing`. The `abort` verb is
    semantically distinct from `--force` backward transitions (Inv 34):
    `abort` is for loop- or subagent-driven blocker handling; `--force`
    remains for human-driven rollback.

51. **`abort` acceptance / rejection by state.** `abort` is accepted
    when `feature.json.tdd_state` is one of `test-red`, `impl`, or
    `sync-deployed`. `abort` is rejected with exit code `1` and a
    stderr diagnostic when `tdd_state` is `spec`, `spec-update`, or
    `deprecated`. The `deprecated` rejection holds unconditionally
    (no `--force` override; Inv 35 still applies — `deprecated` is
    terminal in every direction including abort).
    Enforced by `test/test-abort-transition.py`.

52. **`abort` scope-marker release (mode-aware).** On accepted abort,
    `tdd-step.py` removes the scope-active marker for the named
    feature, honoring the same dual-mode path resolution as Inv 12:
    standalone mode (mode marker absent or content equals `standalone`)
    removes `<repo_root>/.rabbit-scope-active-<feature>`; plugin mode
    (`<repo_root>/.rabbit/.runtime/mode == 'plugin'`) removes
    `<repo_root>/.rabbit/.runtime/scope-active-<feature>`. Removal is
    best-effort idempotent — if neither marker exists, no error.
    Marker removal happens BEFORE the state rollback in Inv 53 so that
    an abort which crashes between the marker removal and the state
    rollback still leaves the scope unlocked (the subagent or a
    re-dispatched cycle can re-LOCK without manual cleanup). Enforced
    by `test/test-abort-releases-scope-lock.py` with tmpdir fixtures
    for both modes, matching `test-prompt-lock-unlock-marker-path.py`'s
    pattern.

53. **`abort` state rollback via `_pre_touch_state`.** On accepted
    abort, `tdd-step.py` rolls back `feature.json.tdd_state` to the
    value of an optional `feature.json._pre_touch_state` field if
    present; otherwise to `test-red` as a safe default. The
    `_pre_touch_state` field is OPTIONAL — it is set by upstream
    callers (e.g., `rabbit-feature-touch` may write it at
    branch-creation time) to capture the pre-touch state so abort can
    restore it accurately. When `_pre_touch_state` is absent, the
    `test-red` default ensures the feature returns to a re-runnable
    state (the entry point of the executor portion of the cycle).
    After rollback, `_pre_touch_state` is removed from `feature.json`
    — the value is consumed by the abort — so a subsequent
    `transition` call does not see a stale rollback target. Enforced
    by `test/test-abort-rollback-state.py`.

54. **`tdd_state: blocked` is HANDOFF-only.** The `blocked` value
    emitted under the `tdd_state` key of the blocked-HANDOFF schema
    (Inv 10) is HANDOFF-only — it MUST NEVER appear as a persisted
    value in `feature.json.tdd_state`. HANDOFF JSON may
    carry state-like values that are not members of `_VALID_STATES`
    (Inv 31), and any future HANDOFF-only state values (such as a
    dispatcher-emitted `aborted`) follow
    the same rule. `_VALID_STATES` (Inv 31) remains the authoritative
    set of `feature.json.tdd_state` values; HANDOFF-emitted
    state-like values are a separate vocabulary used only on the wire
    between subagent and dispatcher.

55. **HANDOFF additive fields: `discovered_issues` and
    `aborted_reason`.** The HANDOFF JSON block (declared in Inv 22)
    carries two ADDITIVE fields under `handoff_schema_version: "1.1.0"`
    (the version-integer reservation is described in Inv 22; the
    fields themselves are defined by this invariant):

    - **`discovered_issues: [{title, body, labels}]`** — list of
      issues the subagent discovered during its cycle that warrant
      filing. Default `[]` (empty list, matching Inv 21's
      `closed_items` precedent). Each element MUST have
      `title: string`, `body: string`, `labels: [string]`. Populated
      by callers (e.g., the rabbit-auto-evolve dispatcher) that
      consume this field to file follow-up issues via rabbit-issue;
      the subagent itself never files issues.

    - **`aborted_reason: string | null`** — always-present-nullable
      (matching the `tdd_report_path: null` precedent: the key is
      always emitted, the value is `null` when not applicable).
      `null` in non-abort HANDOFFs. In abort HANDOFFs (emitted after
      the subagent invokes `tdd-step.py abort --reason <code>` per
      Inv 50), the value carries the same `<code>` passed to
      `--reason` (a free-form short tag such as `blocked-by-<issue>`).

    Both fields are ADDITIVE — the template MUST emit the default
    values (`[]` and `null`) in EVERY HANDOFF, including normal
    test-green completion HANDOFFs that do not populate either.
    Backward compatibility: consumers reading
    `handoff_schema_version: "1.1.0"` HANDOFFs see both fields
    always present, with defaults indicating "nothing to report."

    Enforced by `test/test-handoff-schema.py` (presence-and-default
    assertions for both fields in every template HANDOFF_JSON block, plus a
    populated-case parse test). The two fields appear in all three
    HANDOFF_JSON blocks of the template (STEP 5 fail-HANDOFF, STEP 7
    fail-HANDOFF, completion HANDOFF), which lives under the contract feature.

### Downstream test-suite discovery

56. **STEP 5 SYNC-DEPLOYED — downstream test-suite discovery on
    delete/rename.** When the cycle DELETES or RENAMES any file under
    `.claude/features/<feature>/`, the dispatched subagent's scope —
    bounded to the primary feature and features it directly edits — does
    NOT cover other features whose test fixtures or install closures
    INDIRECTLY reference the removed path. The failure class this guards
    against: deleting files under one feature can silently break another
    feature whose `install.py` and test fixtures reference the removed
    paths, because that downstream feature's `test/run.py` never runs in
    a scope bounded to the editing feature.

    The dispatched-subagent template at
    `.claude/features/contract/templates/prompts/tdd-subagent.txt` MUST,
    in its STEP 5 SYNC-DEPLOYED section (which runs AFTER IMPLEMENT and
    BEFORE CODE-REVIEW, per Inv 8/46 — the 8-step banner count is fixed,
    so this requirement folds into STEP 5 rather than adding a STEP 9),
    instruct the subagent to:

    (a) **Detect deletes/renames.** Enumerate every file the cycle
        DELETED or RENAMED under `.claude/features/<feature>/` (e.g. via
        `git diff --diff-filter=DR --name-only` against the cycle's
        base, or the equivalent rename detection).

    (b) **Discover downstream consumers.** For each deleted/renamed path,
        `grep` every `.claude/features/*/test/` directory for references
        to that path (basename and/or relative path). Each matching
        feature is a downstream consumer whose suite has an indirect
        dependency on the removed artifact.

    (c) **Run downstream suites.** For each discovered downstream
        feature, run `python3 .claude/features/<downstream>/test/run.py`
        IN ADDITION to the primary feature's own suite.

    (d) **Block on failure.** If any downstream `test/run.py` exits
        nonzero, the subagent MUST NOT proceed to CODE-REVIEW; it emits
        a fail-HANDOFF (`tdd_state: impl`, `test_result: fail`,
        `spec_compliance: fail`, `tdd_report_path: null`) whose `notes`
        names the failing downstream feature and exit code. A passing
        downstream sweep (or no deletes/renames at all) proceeds
        normally.

    The template lives under the contract feature (Inv 57), so editing it
    is a cross-feature operation. Enforced by
    `test/test-prompt-downstream-test-discovery.py` (asserts the STEP 5
    region of both the template and the assembled prompt names the
    delete/rename trigger, instructs a grep of feature `test/` directories,
    runs downstream `test/run.py`, and references downstream suites).

57. **`rabbit-tdd-subagent` agent definition enables the `Skill` tool.** The
    agent definition at `agents/rabbit-tdd-subagent.md` declares a `tools:`
    frontmatter list, and that list MUST include `Skill` (alongside `Read`,
    `Write`, `Edit`, `Bash`, `Glob`, `Grep`). Without it the subagent cannot
    honor two of its own prompt-mandated steps: Inv 11's SKILL.md-routing rule
    (`Skill("skill-creator:skill-creator")` before editing any `SKILL.md`) and
    Inv 17's CODE-REVIEW step (`Skill("superpowers:requesting-code-review")`).
    The tool addition takes effect for newly-dispatched subagents only after
    the agent definition is re-published (`publish_agent`) and the Claude
    session reloads agent definitions.

    Enforced by `test/test-agent-skill-tool.py`, which asserts the `tools:`
    list in BOTH the source and deployed agent definitions contains `Skill`
    (and still contains the original six tools).

64. **PR-body close-reference authoring convention.** The agent definition
    at `agents/rabbit-tdd-subagent.md` MUST embed a PR-body authoring
    convention governing issue-closing keywords, so a subagent never writes
    an enumeration that GitHub's auto-close or the merge close-ref parser
    mistakes for an issue close-reference. The convention states:

    (a) **Forbidden enumeration form.** PR bodies, commit messages, and
        HANDOFF notes MUST NOT use `Fix #N` / `Fixes #N` / `Closes #N` for
        NON-issue enumeration (e.g. a `Fix #<n>` series listing several
        sub-fixes) — those parse as issue close-references and can wrongly
        close the same-numbered issues.

    (b) **Plain enumeration instead.** Use a `Fix <n>` series or `Part N/M`
        for non-issue enumeration (no `#`).

    (c) **Reserved closing keyword.** The closing keyword is reserved for the
        ACTUAL target issue: write exactly `Closes #<issue>` for the one
        issue the cycle resolves.

    The convention lives in the agent definition (a deployed surface via
    `publish_agent`), so the tightened guidance takes effect for
    newly-dispatched subagents only after the agent definition is
    re-published. Enforced by `test/test-prbody-close-ref-convention.py`,
    which asserts the convention tokens appear in BOTH the source and
    deployed agent definitions.

58. **Assembled-prompt paths are repo-RELATIVE, not main-repo-absolute.**
    The four filesystem-path slots `dispatch-tdd-subagent.py`
    interpolates into the assembled prompt — `feature_dir`, `tdd_step_py`,
    `scope_marker_path`, `tdd_report_path` — MUST be emitted as paths RELATIVE
    to the repository root (i.e. `os.path.relpath(<abs>, repo_root)`), and the
    `repo_root` slot itself MUST be emitted as `.` (the current directory).
    The subagent resolves every baked path from its CURRENT WORKING DIRECTORY,
    so a worktree-isolated dispatch (rabbit-auto-evolve Inv 28, cwd
    `.claude/worktrees/<name>`) and a non-isolated dispatch (cwd = repo root)
    both resolve correctly from one prompt. Mode DETECTION at assembly time
    still uses absolute paths internally (it must `os.path.exists` real
    markers); only the emitted SLOT STRINGS are relative.

    Enforced by `test/test-prompt-relative-paths.py` (e2e): the assembled
    prompt contains NO occurrence of the absolute `repo_root` prefix and the
    `feature_dir` / `tdd_step_py` / `scope_marker_path` / `tdd_report_path`
    references appear in their repo-relative form.

59. **Spec/contract path resolution prefers the flat `docs/` layout.**
    Both owned scripts resolve a feature's `spec.md` and `contract.md`
    by preferring the flat `<feature-dir>/docs/<name>` file and falling
    back to `<feature-dir>/specs/<name>` when the `docs/` file is absent;
    when neither exists the `specs/` candidate is the canonical reported
    path. The `docs/` tree may hold sibling subdirectories (e.g.
    `docs/bugs/`); resolution targets the flat `docs/<name>` file only and
    never such a subdirectory.

    - `tdd-step.py` exposes a `resolve_spec_path(feature_dir, name)` helper
      implementing this precedence. The `spec-update -> test-red`
      precondition (Inv 38) diffs the flat `docs/spec.md` and
      `docs/contract.md` candidates in addition to the `specs/` and legacy
      `docs/spec/` candidates, so a spec change under any supported layout
      satisfies the gate. The numbered-list check (Inv 41) runs against the
      resolved `spec.md` and `contract.md` files (flat `docs/` preferred,
      `specs/` then legacy `docs/spec/` as fallbacks), never the whole
      `docs/` tree.
    - `dispatch-tdd-subagent.py` emits a scoped-view grep hint that points
      at the actual `--spec` path the caller resolved; when that path is
      outside the repository root it falls back to the feature's flat
      `docs/spec.md` when that file exists under the repository root, else
      the `specs/spec.md` layout.

    Enforced by `test/test-docs-resolver.py` (e2e): `resolve_spec_path`
    returns the `docs/` file when present, the `specs/` file when only that
    exists, and `docs/` wins when both exist (for both `spec.md` and
    `contract.md`); the `spec-update -> test-red` gate accepts a spec edit
    under the flat `docs/` layout; the numbered-list hook runs against the
    flat `docs/` layout without crashing; and `dispatch-tdd-subagent.py`
    assembles a prompt from a `--spec` under `docs/` whose scoped grep hint
    names the `docs/spec.md` path.

60. **Repo-root resolution targets the operating worktree (cwd), not the
    script's own location.** Both owned scripts' `_repo_root` resolver MUST
    derive the repository root from the CURRENT WORKING DIRECTORY of the
    running process — `git rev-parse --show-toplevel` run in the process cwd
    — and MUST NOT derive it from the script's own directory
    (`git -C <script_dir> …`). The `RABBIT_ROOT` environment variable
    (plugin mode, Inv 47) still takes precedence verbatim when set; cwd-based
    git resolution is the fallback when `RABBIT_ROOT` is unset.

    Under worktree-isolated dispatch (rabbit-auto-evolve Inv 28) the subagent
    invokes the MAIN deployed copy of `tdd-step.py` while OPERATING in its
    worktree; the process cwd is the worktree under isolation and the main
    repo on the headless path, so cwd-based resolution is correct for BOTH.
    This is the resolver-side complement to Inv 58.

    Enforced by `test/test-repo-root-cwd-resolution.py` (e2e: a real git repo
    plus a linked worktree; cwd-in-worktree returns the worktree toplevel,
    cwd-in-main returns the main toplevel, and `RABBIT_ROOT` set wins verbatim).

61. **Oversized prompt slots bypass the argv 128 KB cap.**
    `dispatch-tdd-subagent.py` MUST assemble the prompt without ever passing
    a single `--slot name=value` argv string longer than Linux's
    `MAX_ARG_STRLEN` (128 KB per argument, independent of `ARG_MAX`) to
    `build-prompt.py`. Large slot values — `spec_content` and
    `impl_suggestion_block` in particular, which routinely exceed 128 KB for
    big features (e.g. the ~148 KB rabbit-auto-evolve spec) — MUST be routed
    through a channel that is NOT subject to the per-argument limit, so the
    subprocess `exec()` can never raise
    `OSError: [Errno 7] Argument list too long`.

    The dispatcher passes any slot whose `name=value` argv form exceeds a
    budget below `MAX_ARG_STRLEN` as a tiny, collision-proof sentinel token
    (built from `os.urandom`, wrapped in `0x1e` record-separator control
    chars that never appear in spec/template prose and are legal in an argv
    string) and substitutes the real value back into the assembled prompt —
    via a single `str.replace` per oversized slot — AFTER `build-prompt.py`
    returns its file. `build-prompt.py` and the prompt template are owned by
    the `contract` feature (Out of Scope here), so the dispatcher MUST NOT
    change `build-prompt.py`'s CLI; the sentinel round-trip is entirely
    internal to the dispatcher. Slots small enough to stay under the budget
    are passed as-is (byte-identical argv and prompt), preserving Inv 44's
    "one `--slot` per declared slot" subprocess shape.

    Enforced by `test/test-large-slot-no-argv-limit.py` (e2e): dispatching
    with a `spec_content` payload larger than 128 KB returns exit 0, emits no
    `Argument list too long` on stderr, and the assembled prompt contains the
    oversized body verbatim (no truncation).

62. **`rabbit_print` import resolves from the repo root, not a fixed
    `parents[N]` offset.** `tdd-step.py` loads the contract feature's
    `rabbit_print` module (per Inv 39) at import time, from
    `<repo_root>/.claude/features/contract/scripts/rabbit_print.py`. Because
    `tdd-step.py` is published to two locations at DIFFERENT depths (the source
    `.claude/features/tdd-subagent/scripts/` and the deployed
    `.claude/agents/tdd-subagent/scripts/`), a fixed `parents[N]` offset cannot
    resolve the contract-scripts directory from both. The import-time resolver
    MUST anchor on the repository root, building the contract-scripts path as
    `<repo_root>/.claude/features/contract/scripts`. Resolution precedence,
    highest first: (a) `RABBIT_ROOT` (plugin mode, Inv 47) when set; (b) the
    cwd-based `git rev-parse --show-toplevel` (consistent with Inv 60); (c) a
    robust upward walk from the script's own location for the first ancestor
    containing `.claude/features/contract/scripts/rabbit_print.py`. Each
    candidate root is accepted only when `rabbit_print.py` actually exists
    under it.

    Enforced by `test/test-rabbit-print-import-from-deployed.py` (e2e: a real
    git repo staging both the source and deployed layouts plus the contract
    `rabbit_print.py`; `tdd-step.py --help` from each copy loads the module and
    exits 0).

63. **`--spec` resolution is full-vendor-safe (no dispatch-contract
    change).** `dispatch-tdd-subagent.py` resolves the `--spec` value
    relative to the process CURRENT WORKING DIRECTORY: the path flows
    unaltered into `os.path.isfile(args.spec)` (the Inv 3 fail-fast guard)
    and `_read_file(args.spec)` (the `{spec_content}` embed), both of which
    resolve a relative path against cwd. The dispatch boundary therefore
    needs NO mode-aware spec-path rewriting. When the cycle invokes the
    dispatcher from inside a self-contained vendored worktree — whose whole
    tracked checkout is co-located, so the cycle runs with cwd at the rabbit
    runtime root — the spec resolves cwd-relative exactly as in standalone
    mode, where the dispatcher runs at the repo root. The per-mode feature
    ROOT differs (standalone scans `.claude/features/`, vendored adds
    `rabbit-project/features/`), but the `--spec` RESOLUTION is the same
    cwd-relative lookup in both, so the dispatch contract is full-vendor-safe
    unchanged.

    Enforced by `test/test-spec-cwd-relative-full-vendor.py` (e2e: a
    standalone layout and a self-contained vendored-worktree layout; the
    live dispatcher runs with cwd at each operating root and a cwd-relative
    `--spec`, and both assert the resolved spec body is embedded in the
    assembled prompt).

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
