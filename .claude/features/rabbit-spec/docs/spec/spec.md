---
feature: rabbit-spec
version: 1.3.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
status: active
---

# rabbit-spec — Spec

## Purpose

rabbit-spec owns the rabbit workflow's spec-lifecycle skills — the skills that
draft and revise a feature's `docs/spec/spec.md`. After Stage 2 it hosts
`rabbit-spec-create`, the initial-spec-drafting skill that absorbs the
behavior of the former `spec-seeder` feature; Stage 3 will add
`rabbit-spec-update`, the spec-revision skill that absorbs and subagent-ifies
the former `rabbit-feature-spec`.

The reading-and-drafting work is performed by a read-only subagent
(`spec-creator`) that is tool-restricted to Read/Grep/Glob. The skill itself
is a thin orchestration wrapper that assembles the prompt, dispatches the
agent, and writes the returned body to disk.

## Surface

- `skills/rabbit-spec-create/SKILL.md` — the user-invocable skill
- `agents/spec-creator.md` — the read-only drafting subagent
  (frontmatter declares `tools: Read, Grep, Glob` — the restriction is
  load-bearing)
- `scripts/dispatch-spec-create.py` — Python prompt assembler invoked by
  the skill; resolves globs, caps at 50 files, calls
  `contract/scripts/build-prompt.py`
- `docs/spec/spec.md`, `docs/spec/contract.md`, `feature.json`,
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
   agent at `agents/spec-creator.md`, and the dispatch script at
   `scripts/dispatch-spec-create.py`. The `manifest` MUST contain a
   `publish_skill` entry sourcing the skill and a `publish_agent` entry
   sourcing the agent. The `prompts` array MUST contain exactly one entry
   with `id: "spec-create"`, `kind: "subagent"`, `inject` listing
   philosophy + coding-rules, and `slots: ["feature_name", "paths_globs", "paths_resolved"]`.

2. `agents/spec-creator.md` MUST exist with YAML frontmatter declaring
   `name: spec-creator`, `tools: Read, Grep, Glob` (exact comma-separated
   list — no `Write`/`Edit`/`Bash`), `model: sonnet`, and `version: 1.0.0`.
   The body describes the read-only drafting task. The tool restriction is
   load-bearing — it makes side-effects impossible regardless of what the
   agent attempts.

3. `scripts/dispatch-spec-create.py` MUST be executable, carry a
   module-level docstring (Version/Owner/Deprecation criterion), and:
    (a) Accept `--feature-name <name>` (required) and `--paths <globs>`
        (optional; comma-separated, may be empty for standalone mode).
    (b) Resolve each glob via `glob.glob(<g>, recursive=True)`, dedupe,
        sort lexicographically, take first 50.
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
   and plugin modes, `version: 1.0.0`, `owner: rabbit-workflow team`, and
   a `deprecation_criterion`. The body documents the 4-step orchestration
   protocol (assemble prompt → dispatch agent → write to spec.md → report).

## Tech Stack

Python 3 stdlib only.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Per-invariant
coverage arrives with the surface artifacts in this stage:
- `test-agent-restriction.py` — asserts the agent's `tools` field is exactly
  `Read, Grep, Glob` with no others
- `test-dispatch-script.py` — invokes the dispatch script in both modes
  (with paths and without) and asserts it produces a prompt-file path
- `test-prompts-section-shape.py` — loads feature.json and asserts the
  `prompts` entry shape matches Inv 1

## Out of Scope

- `rabbit-spec-update` (Stage 3) — revising existing specs, subagent-ified
  from rabbit-feature-spec. Arrives in the next stage.
- The user-code globs themselves and their semantics — owned by
  `rabbit-feature` (or its successor `rabbit-feature-scaffold` in Stage 4).
- The prompt template body at
  `.claude/features/contract/templates/prompts/spec-create.txt` — owned by
  `contract` per Inv 57.
