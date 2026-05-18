---
feature: contract
version: 1.10.0
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

## Invariants

1. Every file in `templates/` carries a `template_version` field.
2. `dispatch-feature-edit.py` output begins with the sentinel `RABBIT-POLICY-BLOCK-v1`.
3. All scripts in `scripts/` and `scripts/enforcement/` are executable.
4. Every schema file in `schemas/` is valid JSON.
5. `rabbit-print.schema.json` is the authoritative definition of the `[rabbit]` print format used by all rabbit-workflow hooks and CLI scripts.
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
31. `check-no-main-edits.py` MUST mirror the protected-branch set declared in rabbit-cage Inv 21 (currently `main`, `master`). It MUST NOT forbid additional branches (`trunk`, `develop`, etc.) that are not in any documented invariant. The protected-branch list MUST be a single source of truth, ideally derived from a shared constant or config rather than duplicated.
32. `check-imports-resolve.py` import-target regex MUST cover all paths where imports can appear: `.claude/features/`, `.claude/hooks/`, `.claude/skills/`, `.claude/commands/`, `.claude/agents/`. The current `.claude/features/`-only pattern misses imports from deployed surface files, producing false-OK on real drift.
33. `workspace-structure.json` schema field naming MUST be internally consistent: either all snake_case or all camelCase, not mixed. The current mixed-case form (camelCase metadata keys with snake_case enforcement targets) confuses readers and triggers spurious schema-vs-data mismatches.

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
