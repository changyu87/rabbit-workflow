---
feature: rabbit-spec
version: 1.9.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
status: active
---

# rabbit-spec — Spec

## Purpose

rabbit-spec owns the rabbit workflow's spec-lifecycle skills — the skills that
draft and revise a feature's spec.md (canonical flat layout: `docs/spec.md`;
fallbacks: `specs/spec.md` and legacy `docs/spec/spec.md`).
After Stage 2 it hosts
`rabbit-spec-create`, the initial-spec-drafting skill that absorbs the
behavior of the former `spec-seeder` feature; Stage 3 will add
`rabbit-spec-update`, the spec-revision skill that absorbs and subagent-ifies
the former `rabbit-feature-spec`.

The reading-and-drafting work is performed by a read-only subagent
(`rabbit-spec-creator`) that is tool-restricted to Read/Grep/Glob. The skill itself
is a thin orchestration wrapper that assembles the prompt, dispatches the
agent, and writes the returned body to disk.

## Surface

- `skills/rabbit-spec-create/SKILL.md` — the user-invocable spec-drafting skill
- `skills/rabbit-spec-update/SKILL.md` — the user/dispatcher-invocable spec-revision skill (absorbs the former rabbit-feature-spec). Dual-mode: detects rabbit mode at invocation time and resolves the feature spec path accordingly.
- `agents/rabbit-spec-creator.md` — the read-only drafting subagent
  (frontmatter declares `tools: Read, Grep, Glob` — the restriction is
  load-bearing)
- `scripts/dispatch-spec-create.py` — Python prompt assembler invoked by
  the skill; resolves globs, caps at 50 files (reporting any dropped
  count loudly on stderr — never a silent truncation), calls
  `contract/scripts/build-prompt.py`
- `docs/spec.md`, `docs/contract.md`, `feature.json`,
  `test/run.py` — feature scaffolding

## Mode awareness

The skill works in both rabbit modes:

- **Standalone**: drafts the spec from feature name alone (skeleton output;
  globs are empty)
- **Plugin**: drafts the spec by reading the matched code files

Mode detection is the skill's responsibility (it reads
`.rabbit/.runtime/mode`); the agent and dispatch script accept globs of any
length including zero.

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "1.1.0"` or
   later, `owner: "rabbit-workflow team"`, `tdd_state: "test-green"`,
   non-empty `summary`, non-empty `deprecation_criterion`, and a `surface`
   block that lists the skill at `skills/rabbit-spec-create/SKILL.md`, the
   agent at `agents/rabbit-spec-creator.md`, and the dispatch script at
   `scripts/dispatch-spec-create.py`. The `manifest` MUST contain a
   `publish_skill` entry sourcing the skill and a `publish_agent` entry
   sourcing the agent. The `prompts` array MUST contain exactly one entry
   with `id: "spec-create"`, `kind: "subagent"`, `inject` listing
   philosophy + coding-rules, and `slots: ["feature_name", "paths_globs", "paths_resolved"]`.

2. `agents/rabbit-spec-creator.md` MUST exist with YAML frontmatter declaring
   `name: rabbit-spec-creator`, `tools: Read, Grep, Glob` (exact comma-separated
   list — no `Write`/`Edit`/`Bash`), `model: sonnet`, and `version: 1.1.0` or
   later. The body describes the read-only drafting task and names the flat
   `docs/spec.md` as the draft target. The tool restriction is
   load-bearing — it makes side-effects impossible regardless of what the
   agent attempts. The agent's base name MUST start with `rabbit-` so that the
   deployed `.claude/agents/rabbit-spec-creator.md` satisfies
   `contract.lib.checks.check_naming` (Inv 10/15).

3. `scripts/dispatch-spec-create.py` MUST be executable, carry a
   module-level docstring (Version/Owner/Deprecation criterion), and:
    (a) Accept `--feature-name <name>` (required) and `--paths <globs>`
        (optional; comma-separated, may be empty for standalone mode).
    (b) Resolve each glob via `glob.glob(<g>, recursive=True)`, dedupe,
        sort lexicographically, take first 50. When the deduped resolved
        count EXCEEDS the 50-file cap, the truncation MUST NOT be silent:
        the script MUST emit a structured note to STDERR (stdout stays a
        single prompt-file path so the skill can parse it) reporting BOTH
        the number inspected and the number dropped — the note text MUST
        contain the substring `dropped` and the integer dropped count
        (e.g. `NOTE: resolved <N> files; capped at 50, <M> dropped`).
        When the deduped resolved count is at or below the cap, NO such
        note is emitted (silent success). The dropped count is consumed by
        `rabbit-spec-create` Step 4 so the user is told "and M dropped"
        rather than silently receiving an incomplete `## Public surface` /
        `## Current behaviour` draft. Enforced by
        `test/test-dispatch-truncation-not-silent.py` (>cap reports the
        dropped count on stderr; <=cap emits no note).
    (c) Invoke `python3 <repo_root>/.claude/features/contract/scripts/build-prompt.py
        --callable-id spec-create --slot feature_name=<name> --slot
        paths_globs=<globs> --slot paths_resolved=<newline-joined>` as a
        subprocess; print the resulting prompt-file path to stdout on
        success; exit nonzero on subprocess failure.
    (d) Stdlib only (argparse, glob, os, subprocess, sys, pathlib).
    (e) `<repo_root>` MUST be resolved via `Path(__file__).resolve().parents[4]` —
        NOT via `subprocess git rev-parse --show-toplevel` and NOT via `os.getcwd()`.
        The script lives at `<repo_root>/.claude/features/rabbit-spec/scripts/dispatch-spec-create.py`,
        so parents[0]=scripts, [1]=rabbit-spec, [2]=features, [3]=.claude, [4]=repo_root —
        which resolves correctly whether `<repo_root>` is the dev workspace OR a plugin
        `.rabbit/` install root. The `git rev-parse` and `os.getcwd()` mechanisms are
        forbidden because in plugin mode (where rabbit lives under `.rabbit/.claude/`)
        they resolve to the user-project root, NOT the rabbit root — causing the
        build-prompt.py path to point to a non-existent location. Enforced by 3 tests
        under `.claude/features/rabbit-spec/test/`: plugin-layout resolution,
        standalone-layout resolution from external cwd, and nested-git-repo immunity.

4. `skills/rabbit-spec-create/SKILL.md` MUST exist with YAML frontmatter
   declaring `name: rabbit-spec-create`, a description naming both standalone
   and plugin modes, `version: 1.1.0` or later, `owner: rabbit-workflow team`,
   and a `deprecation_criterion`. The body documents the 4-step orchestration
   protocol (assemble prompt → dispatch agent → write to spec.md → report).

5. **`skills/rabbit-spec-update/SKILL.md` dual-mode feature_root resolution.**
   `skills/rabbit-spec-update/SKILL.md` MUST exist with YAML frontmatter
   declaring `name: rabbit-spec-update`, a description that names both
   standalone and plugin modes, `model: opus`, `version: 2.1.0` or later,
   `owner: rabbit-workflow team`, and a `deprecation_criterion`.
   The skill body MUST detect the rabbit mode from
   `<repo_root>/.rabbit/.runtime/mode` (written at SessionStart by
   rabbit-meta's `write_mode_marker`) BEFORE issuing any Read/Edit/Write
   against the target feature's spec.md, and resolve the feature_root prefix
   to:
   - `.claude/features/<feature-name>/` — standalone mode (mode marker
     absent or content equals `standalone`).
   - `.rabbit/rabbit-project/features/<feature-name>/` — plugin mode (mode
     marker content equals exactly `plugin`).
   Every subsequent path reference in the skill body (Step 1 Read of the
   target spec.md, Step 1 optional reads of contract.md / feature.json /
   implementation files, Step 4 Edit/Write of spec.md, and the
   "abort if directory does not exist" guard) MUST use the resolved
   feature_root prefix — NOT the literal `.claude/features/` hardcode.
   The impl-suggestion path `.rabbit/impl-suggestion-<feature-name>.json`
   is mode-agnostic (always lives under `<repo_root>/.rabbit/`) and is
   exempt from the prefix rewrite. Mirroring pattern: `rabbit-feature-scaffold`
   SKILL.md's `## Modes` section is the reference implementation.
   Enforced by `test/test-rabbit-spec-update-dual-mode-paths.py` which
   greps the SKILL.md body for: (a) at least one literal mention of
   `.rabbit/.runtime/mode`, (b) at least one literal mention of
   `.rabbit/rabbit-project/features/`, (c) every literal occurrence of
   `.claude/features/<feature-name>/` appears in a context that names
   the standalone-mode branch (no unconditional uses). Wired into
   `test/run.py`.

6. **Spec-path layout dual-read (issue #399 Phase 2a coexistence window).**
   Both spec-lifecycle skills and the drafting agent resolve the in-feature
   spec-file *layout* independently of the mode prefix (Inv 5). The canonical
   layout is the FLAT `<feature_root>/docs/spec.md` (and
   `<feature_root>/docs/contract.md`); the fallbacks are the current
   `<feature_root>/specs/spec.md` and the legacy nested
   `<feature_root>/docs/spec/spec.md`. During the `specs/ -> docs/` flatten
   migration coexistence window, features migrate one-by-one, so the skills
   MUST work against ALL THREE layouts in this preference order (first
   existing wins): flat `docs/` → `specs/` → legacy `docs/spec/`.
   - `skills/rabbit-spec-update/SKILL.md` MUST instruct the skill to PREFER
     `<feature_root>/docs/spec.md`, FALL BACK to `<feature_root>/specs/spec.md`,
     then FALL BACK to the legacy `<feature_root>/docs/spec/spec.md` when the
     preferred paths are absent, for every Step 1 Read (spec.md, contract.md,
     feature.json — feature.json stays at `<feature_root>/feature.json`
     regardless of layout) and the Step 4 Edit/Write of spec.md. The skill
     MUST edit whichever layout it resolved (never silently create a new
     flat `docs/` file alongside an existing `specs/` or `docs/spec/` one).
     The skill body MUST mention the flat `docs/spec.md`, the `specs/spec.md`,
     and the legacy `docs/spec/spec.md` spec-file paths and name the flat
     `docs/` as the preferred layout.
   - `skills/rabbit-spec-create/SKILL.md` MUST write the drafted body to
     `<dest_root>/docs/spec.md` when it already exists, ELSE to
     `<dest_root>/specs/spec.md` when only that layout exists, ELSE to
     `<dest_root>/docs/spec/spec.md` when only the legacy layout exists; when
     NONE exists (brand-new scaffold) it MUST write the canonical flat
     `<dest_root>/docs/spec.md`. The skill body MUST mention the flat
     `docs/spec.md`, the `specs/spec.md`, and the legacy `docs/spec/spec.md`
     destination paths and name the flat `docs/` as the canonical destination
     for new specs.
   - `agents/rabbit-spec-creator.md` MUST name the flat `docs/spec.md` as its
     draft target (not the legacy `docs/spec/spec.md`).
   The deprecation criterion for this dual-read behavior: when every rabbit
   feature has migrated onto the flat `docs/` layout and the `specs/` +
   `docs/spec/` fallbacks can be dropped (tracked by issue #399). rabbit-spec's
   own spec.md/contract.md/CHANGELOG.md live under the flat `docs/` layout
   (`docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`); no `specs/`
   directory remains. Enforced by `test/test-spec-path-layout-dual-read.py`
   (source-inspection of both SKILL.md bodies and the agent body; also asserts
   rabbit-spec's own flat-`docs/` layout) and the on-disk
   `test/test-docs-layout.py`. Both wired into `test/run.py`.

## Tech Stack

Python 3 stdlib only.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Per-invariant
coverage arrives with the surface artifacts in this stage:
- `test-agent-restriction.py` — asserts the agent's `tools` field is exactly
  `Read, Grep, Glob` with no others
- `test-dispatch-script.py` — invokes the dispatch script in both modes
  (with paths and without) and asserts it produces a prompt-file path
- `test-dispatch-truncation-not-silent.py` — Inv 3(b): builds a fixture
  with >50 resolvable files, asserts the dispatcher emits a stderr note
  naming the dropped count (truncation is NOT silent) while stdout stays a
  single prompt-file path; with <=50 files asserts NO note is emitted
- `test-prompts-section-shape.py` — loads feature.json and asserts the
  `prompts` entry shape matches Inv 1
- `test-spec-path-layout-dual-read.py` — source-inspects both SKILL.md
  bodies and asserts the flat-`docs/`-preferred, `specs/` + `docs/spec/`
  fallback layout resolution required by Inv 6; also asserts rabbit-spec's
  own doc artifacts live under the flat `docs/` layout
- `test-docs-layout.py` — on-disk E2E assertion of rabbit-spec's flat
  `docs/` layout (`docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`
  present; no `specs/` or root `CHANGELOG.md`; resolver + `validate_feature`
  resolve cleanly)

## Out of Scope

- The user-code globs themselves and their semantics — owned by
  `rabbit-feature` (or its successor `rabbit-feature-scaffold` in Stage 4).
- The prompt template body at
  `.claude/features/contract/templates/prompts/spec-create.txt` — owned by
  `contract` per Inv 57.
