---
feature: rabbit-meta
version: 0.3.1
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when rabbit's per-project plugin model is superseded by a native Claude Code workflow contract mechanism
status: active
---

# rabbit-meta — Spec

## Purpose

Owns plugin-mode machinery for rabbit's per-project install: mode detection
at session start, CLAUDE.md and README.md generators for the vendored
`.rabbit/` install, and the bootstrap helper. Tier-1 drift protection
deliverables live here; Tier-2 surfaces (rabbit-feature-new path-glob
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

**scripts/**
- `.claude/features/rabbit-meta/scripts/bootstrap.sh` (optional — may be inline-documented in `docs/install.md` instead)

## Invariants

1. `lib/mode_detection.py` MUST export `detect_mode(cwd: str) -> str` returning the literal string `"plugin"` or `"standalone"`.
    (a) **Plugin signature.** Returns `"plugin"` iff ALL of: `os.path.basename(cwd) == ".rabbit"` AND the parent directory `os.path.dirname(cwd)` exists AND that parent contains at least one entry whose name is not `".rabbit"`. Otherwise returns `"standalone"`.
    (b) **Behavioral cases enforced by `test/test-mode-detection.py`** (each is its own test):
        - t1: cwd ends in `.rabbit` and the parent has sibling content (e.g. `/tmp/proj/.rabbit` with `/tmp/proj` containing `src/` and `.rabbit/`) → returns `"plugin"`.
        - t2: cwd is a non-`.rabbit` directory with no `.rabbit` ancestor (e.g. a rabbit-self clone) → returns `"standalone"`.
        - t3: cwd ends in `.rabbit` but its parent contains only `.rabbit` (degenerate solo install at filesystem root) → returns `"standalone"`.
        - t4: cwd is a sub-directory of `.rabbit` whose basename is not `.rabbit` (e.g. `/proj/.rabbit/sub`) → returns `"standalone"`.
        - t5: cwd is a path that does not exist on disk → returns `"standalone"` (safe default; the function MUST NOT raise).
    (c) Module-level docstring with `Version`, `Owner`, and `Deprecation criterion` lines per spec-rules.md.
    (d) Pure stdlib (`os.path`, `os.listdir`); no side effects, no env reads, no logging, no module-level prints. Imports limited to `os` (or `os.path` + `os.listdir` via direct attribute access).

2. `templates/CLAUDE.md.template` MUST exist as the verbatim plugin-mode CLAUDE.md content. The template carries the killer-story prose (mentioning `rabbit-feature-new`), the user-project boundary note (`"You are operating on the user project at the parent directory. Edit files at ../, not inside .rabbit/."`), and `@`-imports of the three policy files: `@.claude/features/policy/philosophy.md`, `@.claude/features/policy/spec-rules.md`, `@.claude/features/policy/coding-rules.md`. `lib/generate_claude_md.py` exports `generate_claude_md(template_path: str, output_path: str) -> str`:
    (a) Reads the template file verbatim and writes it to `output_path`.
    (b) Idempotent via byte-equality: if `output_path` already exists with content identical to the template, no write occurs and the function returns the literal string `"no-op"`.
    (c) Otherwise writes the content and returns the literal string `"wrote"`.
    (d) Raises `FileNotFoundError` if `template_path` does not exist.
    (e) Module-level docstring with `Version`, `Owner`, and `Deprecation criterion` lines. Pure stdlib.
    Coverage by `test/test-generate-claude-md.py` (t1: template exists; t2: contains `rabbit-feature-new`; t3: contains all three `@`-imports; t4: each `@`-imported policy file resolves on disk; t5: verbatim write; t6: idempotent re-run returns `"no-op"`; t7: `FileNotFoundError` on missing template).

3. `templates/README.md.template` MUST exist with the killer-story prose (mentioning `rabbit-feature-new`), a "What to do next" section with three numbered items, and a link to `upstream rabbit-workflow`. `lib/generate_readme.py` exports `generate_readme(template_path: str, output_path: str) -> str` with the same five-clause contract as Inv 2 (verbatim copy; idempotent byte-equality returning `"no-op"`; otherwise `"wrote"`; `FileNotFoundError` on missing template; module-level docstring; pure stdlib). Coverage by `test/test-generate-readme.py` (t1: template exists; t2: contains `rabbit-feature-new`; t3: `What to do next` section with items 1./2./3.; t4: contains `upstream rabbit-workflow`; t5-t7: same generator semantics as Inv 2).

4. `scripts/bootstrap.sh` MAY exist as an optional one-line install helper. The canonical install ritual is documented in `docs/install.md` at the repo root; this script is a convenience shim and absence is a valid state. If shipped: the script is executable, idempotent (refuses with exit 1 if `.rabbit/` already exists in cwd), respects the `RABBIT_UPSTREAM` env var (default points at the canonical rabbit upstream), and exits 1 on any error. Coverage (conditional on existence) by `test/test-bootstrap.py` exercising the happy path and the abort-on-existing-dir path.

## Tech Stack

Python 3 stdlib only. No external dependencies (matches the Python-only invariants in `contract` and `rabbit-cage`).

## What this feature does NOT define

- TDD discipline on user-project code. Users keep their existing test suite; rabbit does not run tests against user code.
- Bug/backlog tracking on user-project code. Users keep GitHub Issues or their existing tracker; rabbit's internal B/B system is reserved for rabbit-self development.
- The `rabbit-feature-new` path-glob enhancement for plugin-mode feature mapping — owned by `rabbit-feature`.
- Scope-guard plugin-mode block-and-bypass logic — owned by `rabbit-cage` (the hook owner).
- The `project-map.json` schema — owned by `contract` (schema registry).
- The spec-seeding subagent invoked by `rabbit-feature-new` — owned by the `spec-seeder` feature.
- The user-facing `.rabbit/README.md` carries the killer story, not this spec.

## Tests

`test/run.py` runs the end-to-end suite. Test coverage grows with each implementation milestone; the per-test file mapping is enumerated alongside each invariant above.

`test/run.py` invokes `test-mode-detection.py` (Inv 1), `test-generate-claude-md.py` (Inv 2), and `test-generate-readme.py` (Inv 3). The bootstrap tests land alongside Inv 4 if/when `scripts/bootstrap.sh` is shipped.
