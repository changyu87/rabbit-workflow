---
feature: contract
version: 1.20.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native workflow contract mechanism that supersedes this feature's template, schema, and dispatch responsibilities
status: active
---

# contract — Spec

## Purpose

Owns all cross-feature templates, schemas, dispatch scripts, and enforcement scripts; provides but never directly modifies other features.

## Surface

**templates/**
- `.claude/features/contract/templates/spec-template.md`
- `.claude/features/contract/templates/contract-template.md`
- `.claude/features/contract/templates/bug-template.json`
- `.claude/features/contract/templates/triage-template.md`
- `.claude/features/contract/templates/feature-json-template.json`
- `.claude/features/contract/templates/subagent-launch-template.txt`
- `.claude/features/contract/templates/project-map-template.json`
- `.claude/features/contract/templates/registry-template.json`
- `.claude/features/contract/templates/skill-template.md`
- `.claude/features/contract/templates/command-template.md`

**schemas/**
- `.claude/features/contract/schemas/feature.json.schema.json`
- `.claude/features/contract/schemas/bug.json.schema.json`
- `.claude/features/contract/schemas/project-map.json.schema.json`
- `.claude/features/contract/schemas/rabbit-print.schema.json`
- `.claude/features/contract/schemas/rabbit-print-messages.json`
- `.claude/features/contract/schemas/build-contract.schema.json`
- `.claude/features/contract/schemas/workspace-structure.json`

**data/**
- `.claude/features/contract/build-contract.json`

**declarations/**
- `.claude/workspace-structure.json`

**scripts/** (Python — sole scripting tech stack)
- `.claude/features/contract/scripts/policy-block.py`
- `.claude/features/contract/scripts/find-feature.py`
- `.claude/features/contract/scripts/validate-feature.py`
- `.claude/features/contract/scripts/rabbit_print.py`

**lib/** (Python — importable library, not CLI)
- `.claude/features/contract/lib/__init__.py`
- `.claude/features/contract/lib/checks.py`

**skills/**
- (none — `rabbit-workspace-map` retired in CONTRACT-BACKLOG-27)

**scripts/enforcement/** (Python — sole scripting tech stack)
- `.claude/features/contract/scripts/enforcement/check-imports-resolve.py`
- `.claude/features/contract/scripts/enforcement/check-naming.py`
- `.claude/features/contract/scripts/enforcement/check-sentinel.py`
- `.claude/features/contract/scripts/enforcement/check-symlinks-resolve.py`
- `.claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.py`
- `.claude/features/contract/scripts/enforcement/check-tests-non-interactive.py`
- `.claude/features/contract/scripts/enforcement/check-numbered-lists.py`

## Invariants

1. Every file in `templates/` carries a `template_version` field.
2. All scripts in `scripts/` and `scripts/enforcement/` are executable.
3. Every schema file in `schemas/` is valid JSON.
4. The `[rabbit]` print system is split into three artifacts (CONTRACT-BACKLOG-20):
   (a) `rabbit-print-messages.json` — the registry data file holding the
       brand prefix, bar, color palette, and every message entry (each
       entry has `icon`, `color`, `text` fields). This is the SINGLE
       SOURCE OF TRUTH for message bodies; editing a message means
       editing this file only.
   (b) `rabbit-print.schema.json` — the JSON Schema that validates
       `rabbit-print-messages.json`. Defines the required structure but
       does NOT carry message bodies.
   (c) `rabbit_print.py` — the shared renderer. Consumers (rabbit-cage
       hooks, tdd-subagent scripts) import this module and call
       `rabbit_print(message_id, **kwargs) -> str` or
       `rabbit_subline(text, color="green") -> str` to get a fully
       composed ANSI-colored string. Direct ANSI/brand/bar composition
       outside this module is forbidden — producers MUST go through
       the renderer.
5. `workspace-structure.json` exists at `.claude/features/contract/schemas/workspace-structure.json`, is valid JSON, and defines a node-tree schema: documents conforming to it must have `schema_version`, `owner`, `root`, `nodes` at top level; each node must have `name`, `required`, `description`, `children`.
6. `build-contract.json` exists at `.claude/features/contract/build-contract.json`, is valid JSON, and validates against `.claude/features/contract/schemas/build-contract.schema.json`.
7. All `copy-file` targets declared in `build-contract.json` have a `source` field whose path exists on disk (relative to the repo root).
8. `relink.sh` does NOT exist at `.claude/features/contract/scripts/relink.sh`. No `.sh` files exist anywhere in `scripts/` or `scripts/enforcement/`; Python is the sole scripting tech stack.
9. `.claude/workspace-structure.json` exists, is valid JSON, conforms to the `workspace-structure.json` schema (requires `schema_version`, `owner`, `root`, `nodes` at top level), has `root` equal to `"rabbit"`, and declares nodes for `features`, `skills`, `hooks`, and `commands`.
10. `check-naming.py` documents that the `rbt-` prefix is fully deprecated with no remaining valid use cases; comments and flag messages in that script must not reference `rbt-` as a valid or recommended prefix. The current naming policy is: user-facing artifacts use `rabbit-`; the `rbt-` prefix is banned.
11. Boolean CLI flag values and subcommand values across the rabbit workflow use the literal strings `true` and `false` exclusively. The values `enabled`, `disabled`, `on`, `off`, `yes`, `no` are prohibited as boolean values (action verbs like `lock`, `unlock`, `add`, `remove` remain allowed when the subcommand itself denotes an action, not a boolean state).
12. CLI flag names, subcommand names, and configuration variable names in the rabbit workflow MUST be positive-streamlined: they describe what is present/active, never what is absent/disabled. Names beginning with `no-`, `disable-`, `skip-`, `without-`, or any negating prefix are prohibited. If such a name exists, it must be renamed to describe what IS active when the flag/variable is true. Boolean state is encoded in the value (`true`/`false`), never in the name.
13. `check-tests-non-interactive.py` MUST scan Python test files (`.py`) under `<feature-dir>/test/`, not shell scripts (`.sh`). The repo is Python-only (rabbit-cage Inv 17, rabbit-file Tech Stack); a `.sh`-only scanner is silently vacuous on every invocation. The script MUST detect Python interactive constructs that would block an end-to-end run: bare `input(` calls, `getpass.getpass(`, `click.prompt(`, `click.confirm(`, and any `sys.stdin.read*()` call that is not preceded by an `isatty()` guard or a piped-input fixture. A violation MUST exit 1 with stderr naming the file and the offending construct.
14. `validate-feature.py` MUST check for `test/run.py` (the Python test runner), not `test/run.sh`. The Python-only stack means `test/run.sh` does not exist; checking for it is silently vacuous and rejects valid features. References to `.sh` test runners are banned across all contract enforcement scripts.
15. `check-naming.py` MUST enforce that the deprecated prefix `rbt-` is banned (matches rabbit-cage Inv 67). The legacy literal `rwf-` is incorrect — `rwf-` was never a banned prefix in this repo; `rbt-` is. The script's banned-prefix list MUST be exactly `["rbt-"]`.
16. `.claude/features/contract/scripts/policy-block.py` (and every other Python script under `.claude/features/contract/scripts/` or `.claude/features/contract/scripts/enforcement/`) MUST have a module-level docstring describing its purpose, usage, and exit codes. `print_usage()` functions that print `__doc__` MUST therefore print non-empty text. A `None` usage output is a silent failure mode.
17. `.claude/features/contract/test/run.py` MUST invoke every active `test-*.py` file in the test directory. Tests intentionally excluded (e.g., archived, superseded) MUST be moved out of the test directory or renamed with a leading underscore (`_test-...py`). Dead test files referencing deleted scripts (e.g., `test-relink-no-skills.py` referencing the removed `relink.sh`) MUST be deleted, not skipped.
18. `feature.json.schema.json` MUST NOT require `bugs_root` (item storage was consolidated into rabbit-file's `bug-backlog-files` branch; per-feature `bugs_root` paths no longer apply) and MUST permit the optional top-level `updated` field used by rabbit-cage and other features for the last-modified date. The schema MUST be permissive enough to validate every actual feature.json in the repo without modification.
19. `check-template-schema-producer-consistency.py` MUST reference only producers that exist. Any reference to `file-bug.sh`, `relink.sh`, or other deleted producers is dead code and MUST be removed. The producer list MUST be derived from the current `build-contract.json` or another live source, not from hardcoded names.
20. `check-sentinel.py` MUST scan `.py` files (Python-only stack per Inv 8), not `.sh` files. The script's behavior on a `.sh`-only walk in a Python-only repo is silently vacuous.
21. `bug-template.json` MUST use the field name `template_version` (matching every other template). The legacy `_template_version` underscore-prefix form is prohibited; templates MUST have consistent metadata field names.
22. `feature-json-template.json` MUST validate against `feature.json.schema.json` (i.e., the template MUST be a legal `feature.json`). Templates carrying top-level fields the schema rejects (e.g., when `additionalProperties: false`) are broken by construction.
23. `find-feature.py` MUST close all opened file handles (use `with open()` context managers) and MUST scan ONLY `.claude/features/` for feature directories — not any directory whose basename happens to be `features` (project-side, dependency vendor dirs, etc.). Scope is `.claude/features/` exclusively.
24. `check-symlinks-resolve.py` MUST follow symlinks at any depth (use `find -L` or equivalent with no maxdepth limit), or document why a finite depth is sufficient. Hard-coding `maxdepth=3` silently misses symlinks nested deeper, producing false-OK results.
25. `check-imports-resolve.py` import-target regex MUST cover all paths where imports can appear: `.claude/features/`, `.claude/hooks/`, `.claude/skills/`, `.claude/commands/`, `.claude/agents/`. The current `.claude/features/`-only pattern misses imports from deployed surface files, producing false-OK on real drift.
26. `workspace-structure.json` schema field naming MUST be internally consistent: either all snake_case or all camelCase, not mixed. The current mixed-case form (camelCase metadata keys with snake_case enforcement targets) confuses readers and triggers spurious schema-vs-data mismatches.
27. `rabbit-print-messages.json` exists at `.claude/features/contract/schemas/rabbit-print-messages.json`, is valid JSON, and conforms to `rabbit-print.schema.json`. Top-level keys (required): `schema_version`, `owner`, `deprecation_criterion`, `brand` (the prefix string, exactly `"[🐇 rabbit 🐇]"`), `bar` (the decoration string, exactly `"━━━"`), `colors` (object mapping color name to `{ansi: <code>, reset: <code>}`; required keys `green` = `[32m`/`[0m`, `red` = `[31m`/`[0m`, and `yellow` = `[33m`/`[0m`), and `messages` (object mapping message-id to `{icon, color, text}` where `icon` is a single emoji string, `color` is a key into `colors`, and `text` is the body string with `{name}` placeholders for runtime substitution). The required message-ids are: `welcome` (✅ green), `policy-drift` (⚠️ red), `surface-drift` (🔄 red), `scope-guard-off` (🔓 red), `scope-guard-bypassed` (🔓 red), `human-approval-bypass` (🔑 red), `bypass-permissions-active` (🚨 red), `dispatch-bypass-note` (📢 yellow), `skills-updated` (✨ green), `policy-refreshed` (🔄 green), `tdd-transition` (🔧 green), `tdd-forced` (🔧 red). The previously-required `r1-branch` id was removed alongside the rabbit-cage R1 enforcement hook (rabbit-cage Inv 41). `bypass-permissions-active` was added in PR #151 alongside rabbit-cage Inv 61 (BACKLOG-27). `dispatch-bypass-note` and the `yellow` color were added in BACKLOG-29 alongside the tdd-subagent BUG-57 fix that routes the dispatch-tdd-subagent.py bypass preamble through this registry. Adding new message-ids is permitted; removing or renaming an id is a breaking change requiring a coexistence window per the Designed Deprecation principle.
28. `rabbit_print.py` exists at `.claude/features/contract/scripts/rabbit_print.py` and is an importable Python 3 module (underscore form is required by Python's import system; the rest of contract's scripts use hyphens because they are CLI tools, not importable modules). The module exposes:
    (a) `rabbit_print(message_id: str, **kwargs) -> str` — low-level renderer; returns `f"{ansi}{brand} {icon} {bar} {text} {bar} {icon}{reset}"` where `text` has its `{name}` placeholders substituted from `kwargs`. Raises `KeyError` on unknown `message_id` or missing placeholder.
    (b) `rabbit_subline(text: str, color: str = "green") -> str` — sub-line renderer; returns `f"{ansi}{brand} {text}{reset}"`.
    (c) `rabbit_block(*lines: str) -> str` — block assembler; returns `"\n" + "\n".join(lines)`. The leading newline is the contract that Claude Code renders the `[🐇 rabbit 🐇]` output on its own row (not inline with `Stop says:` / `SessionStart says:` chrome). `rabbit_block` is the SINGLE authoritative place the leading newline lives — no caller, no other renderer, embeds `"\n"` at the start of a message.
    (d) Named wrapper functions, one per message-id, that thinly delegate to `rabbit_print`:
        `welcome() -> str`
        `policy_drift() -> str`
        `surface_drift(files: str) -> str` — `files` is the comma-joined list of rebuilt target names that the sync-check hook collected from the drift-detection pass (e.g. `"hooks/sync-check.py, settings.json"`). Required (no default) so callers cannot silently emit an empty file list; the rendered message reads `Surface drift detected — rebuilt: {files}` (BACKLOG-21).
        `scope_guard_off() -> str`
        `scope_guard_bypassed() -> str`
        `human_approval_bypass() -> str`
        `bypass_permissions_active() -> str`
        `dispatch_bypass_note() -> str`
        `skills_updated(names: str) -> str`
        `policy_refreshed() -> str`
        `tdd_transition(from_state: str, to_state: str) -> str`
        `tdd_forced(from_state: str, to_state: str) -> str`
      Each wrapper signature exposes exactly the kwargs its message-id requires — no `**kwargs`, no extra parameters. State-name placeholders (`from_state`, `to_state`) for `tdd_transition` and `tdd_forced` are upcased by the wrapper (`s.upper()`) so callers pass internal lowercase names without ceremony.
    All functions load the registry from disk on first use and cache it. The module MUST NOT print to stdout or stderr; it returns strings only. The module's `__all__` declares exactly these names: `rabbit_print`, `rabbit_subline`, `rabbit_block`, and every named wrapper above.
29. Every producer that emits a `[rabbit]` message MUST go through `rabbit_print.py`. The canonical producer set (the SINGLE SOURCE OF TRUTH for this invariant) is the following five scripts: `.claude/features/rabbit-cage/hooks/sync-check.py`, `.claude/features/rabbit-cage/hooks/session-init.py`, `.claude/features/rabbit-cage/hooks/refresh.py`, `.claude/features/tdd-state-machine/scripts/tdd-step.py`, and `.claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py`. (The legacy `tdd-subagent/scripts/tdd-step.py` path is retired; the script was relocated to `tdd-state-machine` during post-Cycle B consolidation. The `dispatch-tdd-subagent.py` script was added in BACKLOG-29 when its inline bypass preamble — previously a constitution violation per BUG-57 — was routed through the new `dispatch_bypass_note()` wrapper.) The mandatory call shape for hook producers is `rabbit_block(<named_wrapper>(), ...)` or `rabbit_block(<named_wrapper>(), rabbit_subline(...), ...)`. Prompt-assembly producers (dispatch-tdd-subagent.py) embed the wrapper output as a string inside the assembled prompt (no `rabbit_block` wrapping since the output is prompt text, not a systemMessage value). Direct calls to `rabbit_print("message-id", ...)` at producer call sites are forbidden — the named wrappers are the public API for producers. Direct in-line ANSI escape codes (`\x1b[3...`), direct brand-prefix strings (`[🐇 rabbit 🐇]` or the legacy `[rabbit]`), bar strings (`━━━`), or leading `"\n"` characters in systemMessage values outside `rabbit_block` are likewise forbidden. The single function `rabbit_block` is the only place the leading newline appears for hook-emitted systemMessages.
30. The `build-contract.json` copy-file entry whose `name` is `skills/rabbit-feature-touch/SKILL.md` MUST have its `source` field pointing at `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md` (the rabbit-feature feature owns the skill source post-Cycle B). The destination remains `.claude/skills/rabbit-feature-touch/SKILL.md`. The verification test is owned by rabbit-feature (`test/test-build-source-points-to-rabbit-feature.py`, rabbit-feature spec Inv 4), not by contract — this invariant exists in contract because contract owns `build-contract.json`, but the cross-feature drift detection lives where the affected consumer is. The legacy `tdd-subagent` source path for this entry is retired as of Cycle B.
31. `.claude/workspace-structure.json` MUST declare nodes for every feature that exists on disk under `.claude/features/`. Newly created features MUST be added to the declaration in the same TDD cycle that scaffolds them. The regression is enforced by `test-workspace-declares-all-features.py`, which compares the on-disk feature set against the declaration directly.
32. `validate-feature.py` MUST NOT require a per-feature `docs/bugs/` directory. Per Inv 14, bug storage is centralized to `<repo-root>/.claude/bugs/<feature-name>/`; the legacy per-feature `docs/bugs/` directory no longer applies. The script is feature-level structure validation only (feature.json, docs/spec/spec.md, docs/spec/contract.md, test/run.py) — not bug-storage validation. A feature directory that is otherwise valid (correct feature.json, spec.md, contract.md, executable test/run.py) but lacks `docs/bugs/` MUST validate successfully.
33. `check-numbered-lists.py` MUST exist at `.claude/features/contract/scripts/enforcement/check-numbered-lists.py`, be executable, and reject Markdown files whose ordered-list items or headings use decimal sub-numbers (e.g. `1.1`, `1.2.3`, `## 2.6 Foo`) or letter-suffixed numbering (e.g. `1a`, `3a)`, `## 3a Foo`). The script accepts file paths and/or directories as positional arguments and recursively scans `.md` files. The required in-scope paths for the contract test runner are: `.claude/features/**/docs/spec/*.md`, `.claude/features/**/skills/**/SKILL.md`, `.claude/features/**/agents/**/*.md`, `.claude/features/policy/*.md`, `.claude/features/contract/docs/**/*.md`, and top-level `CLAUDE.md` / `README.md` at the repo root. Out-of-scope (skipped): `archive/**`, `docs/superpowers/**`, and the rabbit-file `bug-backlog-files` branch tree. Exit 0 on no violations; exit 1 on any violation, with each violation printed to stderr as `<path>:<line>: <pattern> <line-content>`. The contract `test/run.py` MUST invoke this script against the live in-scope set and fail if any violation is reported.
34. Every Python script under `.claude/features/contract/scripts/` (excluding `enforcement/`) MUST have at least one production caller outside the contract feature itself. A "production caller" is any reference in `.claude/` (excluding `archive/`, `__pycache__/`, and the contract feature's own `scripts/`, `tests/`, and `docs/spec/` directories) — i.e. a hook, a command, an agent, a skill, another feature's spec, or another feature's script. Scripts without a production caller are dead code and MUST be deleted per the Designed Deprecation principle. The `test-no-dead-contract-scripts.py` regression test enforces this invariant by grepping the `.claude/` tree for each script's basename and failing if no qualifying caller exists. Deprecation criterion for the regression test: when an automated dead-code detector spanning the whole repo is wired into the Stop hook.
35. Post-consolidation deployment mappings are locked in `build-contract.json`:
    (a) The `skills/rabbit-feature-spec/SKILL.md` copy-file entry MUST have `source` = `.claude/features/rabbit-feature/skills/rabbit-feature-spec/SKILL.md` and `destination` = `.claude/skills/rabbit-feature-spec/SKILL.md`. The legacy entry named `skills/rabbit-spec/SKILL.md` MUST NOT exist. The orphan deployed directory `.claude/skills/rabbit-spec/` MUST NOT exist on disk.
    (b) The `agents/tdd-subagent/scripts/tdd-step.py` copy-file entry MUST have `source` = `.claude/features/tdd-state-machine/scripts/tdd-step.py` (sibling scripts `tdd-context.py` and `tdd-drift-check.py` likewise sourced from `tdd-state-machine`). The legacy `.claude/features/tdd-subagent/scripts/*.py` source paths are retired post-consolidation; only `dispatch-tdd-subagent.py` remains in tdd-subagent.
    The verification tests for (a) and (b) live in `test/test-rabbit-feature-spec-deployment.py` and `test/test-build-contract-tdd-state-machine-sources.py` respectively. This invariant exists in contract because contract owns `build-contract.json`.
36. Retirement semantics for features: `feature.json` MAY carry a top-level `status` field with enum values `"active"` (default when omitted) or `"retired"`. A retired feature signals that its surface has been absorbed into a successor feature; the directory remains on disk as a tombstone but the feature is no longer actively developed.
    (a) `feature.json.schema.json` MUST declare the `status` field with `enum: ["active", "retired"]` and document the default as `"active"`.
    (b) `validate-feature.py` MUST short-circuit (exit 0 with a `RETIRED:` notice) when `feature.json` has `status: retired`. Retired features are exempt from the standard structural checks (spec.md, contract.md, test/run.py, deprecation_criterion) because their successor owns the live surface.
    (c) `.claude/workspace-structure.json` MUST mark retired features as `required: false` so future declaration-vs-disk audits do not flag tombstone directories as missing. The currently retired features are `rabbit-spec` and `rabbit-feature-scope` (both absorbed into `rabbit-feature` per the rename/consolidation work). (The legacy `workspace-map.py --audit` runtime check was retired in CONTRACT-BACKLOG-27.)
37. Contract MUST expose a library module at `.claude/features/contract/lib/checks.py` that holds the enforcement / validation logic for each `scripts/enforcement/check-*.py` script (the formerly extracted-deferred `check-no-main-edits.py` and `check-opus-for-planning-agents.py` were retired in CONTRACT-BACKLOG-27, so no library function is required for them) and for `scripts/validate-feature.py`. The CLI scripts in `scripts/enforcement/` and `scripts/validate-feature.py` MUST be thin wrappers (~10 lines) that import from `contract.lib.checks`, call the matching function, print the returned messages, and exit 0 / 1.
    (a) The library MUST export a `CheckResult` dataclass with exactly two fields: `passed: bool` and `messages: list[str]`. Each library function returns a `CheckResult`. Messages are human-readable lines (one per issue) that the CLI shim prints to stderr on failure or stdout on success.
    (b) Required function names and signatures: `check_tests_non_interactive(feature_dir: str) -> CheckResult`, `check_sentinel(path: str) -> CheckResult`, `check_naming(root: str) -> CheckResult`, `check_imports_resolve(feature_dir: str) -> CheckResult`, `check_symlinks_resolve(root: str) -> CheckResult`, `check_template_producer_consistency(template_path: str) -> CheckResult`, `check_numbered_lists(targets: list[str]) -> CheckResult`, `validate_feature(feature_dir: str) -> CheckResult`.
    (c) `lib/__init__.py` MUST exist so the package is importable (empty file is sufficient).
    (d) Library functions MUST NOT call `sys.exit`, MUST NOT print to stdout / stderr, and MUST NOT raise on contract-violation conditions — all outcomes flow through the returned `CheckResult`. Invocation errors (missing file, bad JSON, etc.) are reflected as `passed=False` with descriptive messages.
    (e) CLI consumers of the existing scripts (notably `tdd-step.py`) continue to call the CLI shims with their existing argv shape; the refactor is backward-compatible at the CLI boundary. Rewiring those consumers to import the library directly is out of scope for this invariant.

38. **Cross-feature invariant-monotonic-order enforcement (BACKLOG-30 folded scope).** Contract MUST expose `check_invariant_monotonic_order(feature_dirs: list[str]) -> CheckResult` in `lib/checks.py`, a CLI shim at `.claude/features/contract/scripts/enforcement/check-invariant-monotonic-order.py`, and a regression test `test/test-check-invariant-monotonic-order.py` wired into `test/run.py`. The check parses each feature's `docs/spec/spec.md`, walks its `## Invariants` / `### Invariants` sections, extracts top-level numbered items (`^(\d+)\.`), and asserts numbers appear in strictly increasing order WITHIN each section. A `KNOWN_ISSUES` allowlist inside the library function permits features pending a renumber to be skipped from enforcement; the current value is `[]` (all renumbers landed: contract in CONTRACT-BACKLOG-31, rabbit-feature in PR #162, rabbit-cage in RABBIT-CAGE-BACKLOG-30). Operators MUST add an entry only when a renumber cycle is in flight, and MUST remove it once the renumber lands. Features absent from `KNOWN_ISSUES` are validated; any monotonicity violation FAILs the test with a clear `<feature>:<section>: <prev_num> → <next_num>` diagnostic. Features added later are validated automatically (no per-feature opt-in needed).

39. **Retired-invariant log (BACKLOG-30 F8 partial).** `.claude/features/contract/CHANGELOG.md` MUST exist, carry YAML frontmatter (`feature: contract`, `owner: rabbit-workflow team`, `deprecation_criterion`), and serve as the tombstone log for invariants previously declared in `docs/spec/spec.md` and since retired. Each tombstone entry MUST name the original invariant number (as it appeared in spec.md at the time of retirement), a one-line "what it asserted + why retired" summary, and the backlog ID that drove the retirement. Tombstone numbers in CHANGELOG.md record historical numbers and are NOT updated when spec.md is renumbered (e.g., the CONTRACT-BACKLOG-31 monotonic renumber closed all gaps in spec.md without rewriting CHANGELOG tombstones). The CHANGELOG MUST also carry a top-of-file note for each significant renumber event naming the cycle that performed it. Post-renumber, CHANGELOG tombstone numbers may numerically collide with new-numbering active invariants — this collision is benign because CHANGELOG entries are clearly scoped to "historical numbers" by file/section heading, and the gap-correspondence test was retired alongside the renumber.

## Template marker convention

Every template file in `templates/` MUST carry exactly one `template_version` marker. The marker placement depends on the template's body language:

- **JSON templates** — top-level `"template_version"` field (e.g. `bug-template.json`, `feature-json-template.json`).
- **Markdown templates with YAML frontmatter** — `template_version:` key inside the frontmatter (e.g. `skill-template.md`, `command-template.md`).
- **Markdown templates without frontmatter** — HTML comment `<!-- template_version: X.Y.Z -->` on the first non-empty line (e.g. `handoff-template.md`, `triage-template.md`, `spec-update-template.txt`).
- **Markdown templates with Jinja-style placeholders** — `{# template_version: X.Y.Z #}` on the first line (e.g. `spec-template.md`, `contract-template.md`).
- **Plain-text templates** — `# template_version: X.Y.Z` comment on a leading line (e.g. `subagent-launch-template.txt`).

The legacy `_template_version` underscore-prefix form is prohibited (Inv 21); `test-templates-have-version.py` uses a word-boundary regex that rejects it. `handoff-template.md` is the reference marker for HTML-comment style.

## Invariant enforcement limitations

Some invariants are **test-only** — the test suite verifies them at CI time, but no edit-time hook prevents drift between runs.

- **Inv 6** (build-contract validation): only `test-build-contract.py` verifies that `build-contract.json` validates against `build-contract.schema.json`. There is no edit-time enforcement; an unvalidated `build-contract.json` will only be flagged when tests run. This is acceptable because the contract is small and changes infrequently; promoting it to a hook would add startup latency disproportionate to the protection delivered.

## CLI Naming Convention

All CLI flags, subcommand values, and configuration variable names in the
rabbit workflow follow two rules. These rules apply to scripts under any
feature's `scripts/`, `skills/<name>/scripts/`, and `hooks/`, and to
subcommand values exposed by skills like `/rabbit-config`.

**Rule 1 — Boolean values use `true`/`false` exclusively.**

Boolean CLI flag values and subcommand values use the literal strings
`true` and `false`. Do NOT use:

- `enabled` / `disabled`
- `on` / `off`
- `yes` / `no`
- `lock` / `unlock` for boolean state (action verbs are fine when the
  command itself is the action — e.g. `permissions lock` is an action,
  not a boolean value)

Examples:
- PREFER: `--human-approval-gate true`, `/rabbit-config human-approval true`
- AVOID:  `--human-approval-gate enabled`, `/rabbit-config human-approval bypass`

**Rule 2 — Names must be positive-streamlined.**

Flag names, subcommand names, and configuration variable names describe
what is present or enabled, not what is absent or disabled. If a name
would otherwise begin with `no-`, `disable-`, `skip-`, `without-`, or
any negating prefix, rewrite it to describe what IS active when the
flag/variable is true.

Examples:
- PREFER: `--human-approval-gate`, `--enable-review`, `bypass-marker-present`
- AVOID:  `--no-human-approval`, `--disable-review`, `--skip-review`

The rule is mechanical: read the name without context. If the name
describes an absence or negation, rename it. Boolean state is encoded
in the value (`true`/`false`), never in the name.

**Rationale.** Negated names compose poorly with boolean values
(`--no-human-approval false` means "do require approval" — three
negations to parse). Positive names compose cleanly
(`--human-approval-gate false` means "no gate"). Consistent
`true`/`false` values mean no per-flag value vocabulary to memorize.

## Out of Scope

- This feature does not directly edit any other feature's files.
