---
feature: rabbit-meta
version: 0.7.3
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when a native Claude Code workflow contract mechanism supersedes rabbit's per-project plugin model
status: active
---

# rabbit-meta — Spec

## Purpose

Owns plugin-mode machinery for rabbit's per-project install: mode detection
at session start, and CLAUDE.md and README.md generators for the vendored
`.rabbit/` install. Tier-1 drift protection deliverables live here;
Tier-2 surfaces (rabbit-feature-new path-glob
enhancement, scope-guard plugin-mode logic) live in their respective owning
features.

## Surface

**lib/** (Python — stdlib only)
- `.claude/features/rabbit-meta/lib/mode_detection.py`
- `.claude/features/rabbit-meta/lib/generate_claude_md.py`
- `.claude/features/rabbit-meta/lib/generate_readme.py`

**templates/**
- `.claude/features/rabbit-meta/templates/CLAUDE.md.template`
- `.claude/features/rabbit-meta/templates/README.md.template`

## Invariants

This feature opts into the strict contiguous-invariant-numbering tier by
declaring `"contiguous_invariants": true` in its `feature.json`. The
invariants below MUST be numbered contiguously 1..N with no gaps; the contract
suite's Inv 30 strict tier enforces this. Use
`scripts/reflow-invariants.py` (owned by `contract`) to renumber if a gap is
ever introduced.

1. `lib/mode_detection.py` MUST export `detect_mode(cwd: str) -> str` returning the literal string `"plugin"` or `"standalone"`.
    (a) **Plugin signature.** Returns `"plugin"` iff ALL of: `os.path.basename(cwd) == ".rabbit"` AND the parent directory `os.path.dirname(cwd)` exists AND that parent contains at least one entry whose name is not `".rabbit"`. Otherwise returns `"standalone"`.
    (b) Behavioral cases enforced by `test/test-mode-detection.py` (the authoritative source for each case).
    (c) Module-level docstring with `Version`, `Owner`, and `Deprecation criterion` lines per spec-rules.md.
    (d) Pure stdlib (`os.path`, `os.listdir`); no side effects, no env reads, no logging, no module-level prints. Imports limited to `os` (or `os.path` + `os.listdir` via direct attribute access).

2. `templates/CLAUDE.md.template` MUST exist as the verbatim plugin-mode CLAUDE.md content. The template carries the killer-story prose (mentioning `rabbit-feature-new`), the user-project boundary note (`"You are operating on the user project at the parent directory. Edit files at ../, not inside .rabbit/."`), and `@`-imports of the three policy files: `@.claude/features/policy/philosophy.md`, `@.claude/features/policy/spec-rules.md`, `@.claude/features/policy/coding-rules.md`. `lib/generate_claude_md.py` exports `generate_claude_md(template_path: str, output_path: str) -> str`:
    (a) Reads the template file verbatim and writes it to `output_path`.
    (b) Idempotent via byte-equality: if `output_path` already exists with content identical to the template, no write occurs and the function returns the literal string `"no-op"`.
    (c) Otherwise writes the content and returns the literal string `"wrote"`.
    (d) Raises `FileNotFoundError` if `template_path` does not exist.
    (e) Module-level docstring with `Version`, `Owner`, and `Deprecation criterion` lines. Pure stdlib.
    Coverage by `test/test-generate-claude-md.py`.

3. `templates/README.md.template` MUST exist with the killer-story prose (mentioning `rabbit-feature-new`), a "What to do next" section with three numbered items, and a link to `upstream rabbit-workflow`. `lib/generate_readme.py` exports `generate_readme(template_path: str, output_path: str) -> str` with the same five-clause contract as Inv 2 (verbatim copy; idempotent byte-equality returning `"no-op"`; otherwise `"wrote"`; `FileNotFoundError` on missing template; module-level docstring; pure stdlib). Coverage by `test/test-generate-readme.py`.

## Tech Stack

Python 3 stdlib only. No external dependencies (matches the Python-only invariants in `contract` and `rabbit-cage`).

## What this feature does NOT define

- TDD discipline on user-project code. Users keep their existing test suite; rabbit does not run tests against user code.
- Issue tracking on user-project code. Users keep GitHub Issues or their existing tracker; rabbit-issue (rabbit-managed GitHub Issues) is reserved for rabbit-self development.
- The `rabbit-feature-new` path-glob enhancement for plugin-mode feature mapping — owned by `rabbit-feature`.
- Scope-guard plugin-mode block-and-bypass logic — owned by `rabbit-cage` (the hook owner).
- The `project-map.json` schema — owned by `contract` (schema registry).
- The spec-drafting subagent invoked during feature scaffolding (`rabbit-feature-scaffold`) — owned by `rabbit-spec`.
- The user-facing `.rabbit/README.md` carries the killer story, not this spec.

## Tests

`test/run.py` runs the end-to-end suite; each test file maps to the invariant named in its header. `test-specs-layout.py` guards the flat `docs/` layout (`docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`, siblings of `docs/bugs/`).
