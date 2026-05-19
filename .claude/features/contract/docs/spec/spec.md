---
feature: contract
version: 1.15.0
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
- `.claude/features/contract/schemas/registry.json.schema.json`
- `.claude/features/contract/schemas/bug.json.schema.json`
- `.claude/features/contract/schemas/project-map.json.schema.json`
- `.claude/features/contract/schemas/rabbit-print.schema.json`
- `.claude/features/contract/schemas/rabbit-print-messages.json`
- `.claude/features/contract/schemas/workspace-map.json.schema.json`
- `.claude/features/contract/schemas/build-contract.schema.json`
- `.claude/features/contract/schemas/workspace-structure.json`

**data/**
- `.claude/features/contract/build-contract.json`

**declarations/**
- `.claude/workspace-structure.json`

**scripts/** (Python — sole scripting tech stack)
- `.claude/features/contract/scripts/policy-block.py`
- `.claude/features/contract/scripts/dispatch-feature-edit.py`
- `.claude/features/contract/scripts/dispatch-spec-update.py`
- `.claude/features/contract/scripts/render-template.py`
- `.claude/features/contract/scripts/check-maps-consistent.py`
- `.claude/features/contract/scripts/find-feature.py`
- `.claude/features/contract/scripts/rabbit-triage.py`
- `.claude/features/contract/scripts/validate-feature.py`
- `.claude/features/contract/scripts/workspace-map.py`
- `.claude/features/contract/scripts/audit-orphan-storage.py`
- `.claude/features/contract/scripts/rabbit_print.py`

**skills/**
- `.claude/features/contract/skills/rabbit-workspace-map/SKILL.md`

**scripts/enforcement/** (Python — sole scripting tech stack)
- `.claude/features/contract/scripts/enforcement/check-imports-resolve.py`
- `.claude/features/contract/scripts/enforcement/check-naming.py`
- `.claude/features/contract/scripts/enforcement/check-no-main-edits.py`
- `.claude/features/contract/scripts/enforcement/check-opus-for-planning-agents.py`
- `.claude/features/contract/scripts/enforcement/check-sentinel.py`
- `.claude/features/contract/scripts/enforcement/check-symlinks-resolve.py`
- `.claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.py`
- `.claude/features/contract/scripts/enforcement/check-tests-non-interactive.py`
- `.claude/features/contract/scripts/enforcement/check-numbered-lists.py`

## Invariants

1. Every file in `templates/` carries a `template_version` field.
2. `dispatch-feature-edit.py` output begins with the sentinel `RABBIT-POLICY-BLOCK-v1`.
3. All scripts in `scripts/` and `scripts/enforcement/` are executable.
4. Every schema file in `schemas/` is valid JSON.
5. The `[rabbit]` print system is split into three artifacts (CONTRACT-BACKLOG-20):
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
6. `workspace-map.py` exists, is executable, and produces valid JSON (conforming to `workspace-map.json.schema.json`) when called without flags (show mode); with `--human` it produces human-readable terminal output; with `--audit` it produces a findings-only JSON object (with a `findings` array) listing deviations from the declared workspace structure — missing required nodes emit `error` severity, unknown nodes emit `warn`, missing optional nodes emit no finding; user projects without a `workspace-structure.json` emit a `warn`-severity `missing_declaration` finding. Both show mode and audit mode also accept `--human` for human-readable output.
7. `workspace-map.json.schema.json` is at schema version 2.0.0 and uses a `oneOf` discriminated union: show mode (with `roots` array of annotated node trees, with a `repoRoot` string field alongside the `roots` array) and audit mode (with `findings` array of severity/type/path/root objects). The v1 flat-array properties (`features`, `scripts`, `schemas`, `commands`, `skills`, `hooks`, `userProjectDirs`) are removed. `workspace-structure.json` exists at `.claude/features/contract/schemas/workspace-structure.json`, is valid JSON, and defines a node-tree schema: documents conforming to it must have `schema_version`, `owner`, `root`, `nodes` at top level; each node must have `name`, `required`, `description`, `children`.
8. `rabbit-workspace-map/SKILL.md` exists under `.claude/features/contract/skills/` (source of truth, deployed to `.claude/skills/` by generate-skills-dir.sh) and instructs Claude to directly execute `workspace-map.py` on invocation — using `--human` for readable terminal output and the default JSON mode for programmatic use — rather than merely describing how to invoke it.
9. `build-contract.json` exists at `.claude/features/contract/build-contract.json`, is valid JSON, and validates against `.claude/features/contract/schemas/build-contract.schema.json`.
10. All `copy-file` targets declared in `build-contract.json` have a `source` field whose path exists on disk (relative to the repo root).
11. `relink.sh` does NOT exist at `.claude/features/contract/scripts/relink.sh`. No `.sh` files exist anywhere in `scripts/` or `scripts/enforcement/`; Python is the sole scripting tech stack.
12. `.claude/workspace-structure.json` exists, is valid JSON, conforms to the `workspace-structure.json` schema (requires `schema_version`, `owner`, `root`, `nodes` at top level), has `root` equal to `"rabbit"`, and declares nodes for `features`, `skills`, `hooks`, and `commands`.
13. `check-naming.py` documents that the `rbt-` prefix is fully deprecated with no remaining valid use cases; comments and flag messages in that script must not reference `rbt-` as a valid or recommended prefix. The current naming policy is: user-facing artifacts use `rabbit-`; the `rbt-` prefix is banned.
14. `rabbit-triage.py` is called as `rabbit-triage.py <feature-dir> <bug-name>` and locates bug.json at `<repo-root>/.claude/bugs/<feature-name>/<bug-name>/bug.json` (centralized bug storage, where `<feature-name>` is the basename of `<feature-dir>`). It does NOT look in `<feature-dir>/docs/bugs/`.
15. Boolean CLI flag values and subcommand values across the rabbit workflow use the literal strings `true` and `false` exclusively. The values `enabled`, `disabled`, `on`, `off`, `yes`, `no` are prohibited as boolean values (action verbs like `lock`, `unlock`, `add`, `remove` remain allowed when the subcommand itself denotes an action, not a boolean state).
16. CLI flag names, subcommand names, and configuration variable names in the rabbit workflow MUST be positive-streamlined: they describe what is present/active, never what is absent/disabled. Names beginning with `no-`, `disable-`, `skip-`, `without-`, or any negating prefix are prohibited. If such a name exists, it must be renamed to describe what IS active when the flag/variable is true. Boolean state is encoded in the value (`true`/`false`), never in the name.
17. `check-tests-non-interactive.py` MUST scan Python test files (`.py`) under `<feature-dir>/test/`, not shell scripts (`.sh`). The repo is Python-only (rabbit-cage Inv 39, rabbit-file Tech Stack); a `.sh`-only scanner is silently vacuous on every invocation. The script MUST detect Python interactive constructs that would block an end-to-end run: bare `input(` calls, `getpass.getpass(`, `click.prompt(`, `click.confirm(`, and any `sys.stdin.read*()` call that is not preceded by an `isatty()` guard or a piped-input fixture. A violation MUST exit 1 with stderr naming the file and the offending construct.
18. `validate-feature.py` MUST check for `test/run.py` (the Python test runner), not `test/run.sh`. The Python-only stack means `test/run.sh` does not exist; checking for it is silently vacuous and rejects valid features. References to `.sh` test runners are banned across all contract enforcement scripts.
19. `check-naming.py` MUST enforce that the deprecated prefix `rbt-` is banned (matches rabbit-cage Inv 13). The legacy literal `rwf-` is incorrect — `rwf-` was never a banned prefix in this repo; `rbt-` is. The script's banned-prefix list MUST be exactly `["rbt-"]`.
20. `.claude/features/contract/scripts/policy-block.py` (and every other Python script under `.claude/features/contract/scripts/` or `.claude/features/contract/scripts/enforcement/`) MUST have a module-level docstring describing its purpose, usage, and exit codes. `print_usage()` functions that print `__doc__` MUST therefore print non-empty text. A `None` usage output is a silent failure mode.
21. `.claude/features/contract/test/run.py` MUST invoke every active `test-*.py` file in the test directory. Tests intentionally excluded (e.g., archived, superseded) MUST be moved out of the test directory or renamed with a leading underscore (`_test-...py`). Dead test files referencing deleted scripts (e.g., `test-relink-no-skills.py` referencing the removed `relink.sh`) MUST be deleted, not skipped.
22. `feature.json.schema.json` MUST NOT require `bugs_root` (item storage was consolidated into rabbit-file's `bug-backlog-files` branch; per-feature `bugs_root` paths no longer apply) and MUST permit the optional top-level `updated` field used by rabbit-cage and other features for the last-modified date. The schema MUST be permissive enough to validate every actual feature.json in the repo without modification.
23. `check-template-schema-producer-consistency.py` MUST reference only producers that exist. Any reference to `file-bug.sh`, `relink.sh`, or other deleted producers is dead code and MUST be removed. The producer list MUST be derived from the current `build-contract.json` or another live source, not from hardcoded names.
24. `check-sentinel.py` MUST scan `.py` files (Python-only stack per Inv 11), not `.sh` files. The script's behavior on a `.sh`-only walk in a Python-only repo is silently vacuous.
25. `bug-template.json` MUST use the field name `template_version` (matching every other template). The legacy `_template_version` underscore-prefix form is prohibited; templates MUST have consistent metadata field names.
26. `feature-json-template.json` MUST validate against `feature.json.schema.json` (i.e., the template MUST be a legal `feature.json`). Templates carrying top-level fields the schema rejects (e.g., when `additionalProperties: false`) are broken by construction.
27. `dispatch-feature-edit.py` project-feature path detection MUST handle paths that contain literal `.claude/features/` correctly: a feature reference like `.claude/features/<X>/scripts/foo.py` MUST resolve to feature `<X>`, not be misclassified as a project-relative path. The detection MUST use the `.claude/features/` prefix as a discriminator rather than substring heuristics that misfire.
28. `find-feature.py` MUST close all opened file handles (use `with open()` context managers) and MUST scan ONLY `.claude/features/` for feature directories — not any directory whose basename happens to be `features` (project-side, dependency vendor dirs, etc.). Scope is `.claude/features/` exclusively.
29. `audit-orphan-storage.py` MUST audit both bugs AND backlogs for orphaned storage (unmatched item.json without counter slot, or counter slot without item.json). Reporting only bugs creates a blind spot for backlog items, which are now equally first-class per the rabbit-file consolidation.
30. `check-symlinks-resolve.py` MUST follow symlinks at any depth (use `find -L` or equivalent with no maxdepth limit), or document why a finite depth is sufficient. Hard-coding `maxdepth=3` silently misses symlinks nested deeper, producing false-OK results.
31. `check-no-main-edits.py` MUST enforce the protected-branch set `{main, master}` exactly. It MUST NOT forbid additional branches (`trunk`, `develop`, etc.) that are not in any documented invariant. The protected-branch list is the single source of truth for the contract's "never commit on main" guard (the legacy rabbit-cage R1 auto-branch-creation hook was removed; this script is now the sole programmatic enforcement of branch-per-feature).
32. `check-imports-resolve.py` import-target regex MUST cover all paths where imports can appear: `.claude/features/`, `.claude/hooks/`, `.claude/skills/`, `.claude/commands/`, `.claude/agents/`. The current `.claude/features/`-only pattern misses imports from deployed surface files, producing false-OK on real drift.
33. `workspace-structure.json` schema field naming MUST be internally consistent: either all snake_case or all camelCase, not mixed. The current mixed-case form (camelCase metadata keys with snake_case enforcement targets) confuses readers and triggers spurious schema-vs-data mismatches.
34. `rabbit-print-messages.json` exists at `.claude/features/contract/schemas/rabbit-print-messages.json`, is valid JSON, and conforms to `rabbit-print.schema.json`. Top-level keys (required): `schema_version`, `owner`, `deprecation_criterion`, `brand` (the prefix string, exactly `"[🐇 rabbit 🐇]"`), `bar` (the decoration string, exactly `"━━━"`), `colors` (object mapping color name to `{ansi: <code>, reset: <code>}`; required keys `green` = `[32m`/`[0m` and `red` = `[31m`/`[0m`), and `messages` (object mapping message-id to `{icon, color, text}` where `icon` is a single emoji string, `color` is a key into `colors`, and `text` is the body string with `{name}` placeholders for runtime substitution). The required message-ids are: `welcome` (✅ green), `policy-drift` (⚠️ red), `surface-drift` (🔄 red), `scope-guard-off` (🔓 red), `scope-guard-bypassed` (🔓 red), `human-approval-bypass` (🔑 red), `skills-updated` (✨ green), `policy-refreshed` (🔄 green), `tdd-transition` (🔧 green), `tdd-forced` (🔧 red). The previously-required `r1-branch` id was removed alongside the rabbit-cage R1 enforcement hook (rabbit-cage Inv 61). Adding new message-ids is permitted; removing or renaming an id is a breaking change requiring a coexistence window per the Designed Deprecation principle.
35. `rabbit_print.py` exists at `.claude/features/contract/scripts/rabbit_print.py` and is an importable Python 3 module (underscore form is required by Python's import system; the rest of contract's scripts use hyphens because they are CLI tools, not importable modules). The module exposes:
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
        `skills_updated(names: str) -> str`
        `policy_refreshed() -> str`
        `tdd_transition(from_state: str, to_state: str) -> str`
        `tdd_forced(from_state: str, to_state: str) -> str`
      Each wrapper signature exposes exactly the kwargs its message-id requires — no `**kwargs`, no extra parameters. State-name placeholders (`from_state`, `to_state`) for `tdd_transition` and `tdd_forced` are upcased by the wrapper (`s.upper()`) so callers pass internal lowercase names without ceremony.
    All functions load the registry from disk on first use and cache it. The module MUST NOT print to stdout or stderr; it returns strings only. The module's `__all__` declares exactly these names: `rabbit_print`, `rabbit_subline`, `rabbit_block`, and every named wrapper above.
36. Every producer that emits a `[rabbit]` message — currently the four declared in `rabbit-print.schema.json` `producers` array — MUST go through `rabbit_print.py`. The mandatory call shape is `rabbit_block(<named_wrapper>(), ...)` or `rabbit_block(<named_wrapper>(), rabbit_subline(...), ...)` for messages with sub-lines. Direct calls to `rabbit_print("message-id", ...)` at producer call sites (i.e. inside `sync-check.py`, `session-init.py`, `refresh.py`, `tdd-step.py`) are forbidden — the named wrappers are the public API for producers. Direct in-line ANSI escape codes (`\x1b[3...`), direct brand-prefix strings (`[🐇 rabbit 🐇]` or the legacy `[rabbit]`), bar strings (`━━━`), or leading `"\n"` characters in systemMessage values outside `rabbit_block` are likewise forbidden. The single function `rabbit_block` is the only place the leading newline appears.
37. The `build-contract.json` copy-file entry whose `name` is `skills/rabbit-feature-touch/SKILL.md` MUST have its `source` field pointing at `.claude/features/rabbit-feature/skills/rabbit-feature-touch/SKILL.md` (the rabbit-feature feature owns the skill source post-Cycle B). The destination remains `.claude/skills/rabbit-feature-touch/SKILL.md`. The verification test is owned by rabbit-feature (`test/test-build-source-points-to-rabbit-feature.py`, rabbit-feature spec Inv 4), not by contract — this invariant exists in contract because contract owns `build-contract.json`, but the cross-feature drift detection lives where the affected consumer is. The legacy `tdd-subagent` source path for this entry is retired as of Cycle B.
38. `.claude/workspace-structure.json` MUST declare nodes for every feature that exists on disk under `.claude/features/`. Missing declarations cause `workspace-map.py --audit` to emit a `warn`-severity finding. Newly created features MUST be added to the declaration in the same TDD cycle that scaffolds them. (Audit gap as of Cycle B: rabbit-spec, rabbit-file, and rabbit-feature were added to the declaration during Cycle B to close pre-existing audit findings.)
39. `validate-feature.py` MUST NOT require a per-feature `docs/bugs/` directory. Per Inv 14, bug storage is centralized to `<repo-root>/.claude/bugs/<feature-name>/`; the legacy per-feature `docs/bugs/` directory no longer applies. The script is feature-level structure validation only (feature.json, docs/spec/spec.md, docs/spec/contract.md, test/run.py) — not bug-storage validation. A feature directory that is otherwise valid (correct feature.json, spec.md, contract.md, executable test/run.py) but lacks `docs/bugs/` MUST validate successfully.
40. `check-numbered-lists.py` MUST exist at `.claude/features/contract/scripts/enforcement/check-numbered-lists.py`, be executable, and reject Markdown files whose ordered-list items or headings use decimal sub-numbers (e.g. `1.1`, `1.2.3`, `## 2.6 Foo`) or letter-suffixed numbering (e.g. `1a`, `3a)`, `## 3a Foo`). The script accepts file paths and/or directories as positional arguments and recursively scans `.md` files. The required in-scope paths for the contract test runner are: `.claude/features/**/docs/spec/*.md`, `.claude/features/**/skills/**/SKILL.md`, `.claude/features/**/agents/**/*.md`, `.claude/features/policy/*.md`, `.claude/features/contract/docs/**/*.md`, and top-level `CLAUDE.md` / `README.md` at the repo root. Out-of-scope (skipped): `archive/**`, `docs/superpowers/**`, and the rabbit-file `bug-backlog-files` branch tree. Exit 0 on no violations; exit 1 on any violation, with each violation printed to stderr as `<path>:<line>: <pattern> <line-content>`. The contract `test/run.py` MUST invoke this script against the live in-scope set and fail if any violation is reported.

## Template marker convention

Every template file in `templates/` MUST carry exactly one `template_version` marker. The marker placement depends on the template's body language:

- **JSON templates** — top-level `"template_version"` field (e.g. `bug-template.json`, `feature-json-template.json`).
- **Markdown templates with YAML frontmatter** — `template_version:` key inside the frontmatter (e.g. `skill-template.md`, `command-template.md`).
- **Markdown templates without frontmatter** — HTML comment `<!-- template_version: X.Y.Z -->` on the first non-empty line (e.g. `handoff-template.md`, `triage-template.md`, `spec-update-template.txt`).
- **Markdown templates with Jinja-style placeholders** — `{# template_version: X.Y.Z #}` on the first line (e.g. `spec-template.md`, `contract-template.md`).
- **Plain-text templates** — `# template_version: X.Y.Z` comment on a leading line (e.g. `subagent-launch-template.txt`).

The legacy `_template_version` underscore-prefix form is prohibited (Inv 25); `test-templates-have-version.py` uses a word-boundary regex that rejects it. `handoff-template.md` is the reference marker for HTML-comment style.

## Invariant enforcement limitations

Some invariants are **test-only** — the test suite verifies them at CI time, but no edit-time hook prevents drift between runs.

- **Inv 9** (build-contract validation): only `test-build-contract.py` verifies that `build-contract.json` validates against `build-contract.schema.json`. There is no edit-time enforcement; an unvalidated `build-contract.json` will only be flagged when tests run. This is acceptable because the contract is small and changes infrequently; promoting it to a hook would add startup latency disproportionate to the protection delivered.

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
