---
feature: spec-seeder
version: 0.1.0
owner: cyxu
template_version: 2.0.0
deprecation_criterion: when rabbit's per-project plugin model is superseded by a native Claude Code workflow contract mechanism
status: active
---

# spec-seeder — Spec

## Purpose

A read-only subagent that drafts the initial body of `docs/spec/spec.md` for a newly-declared user-project feature in plugin mode. Invoked by `rabbit-feature-new` when the user maps a slice of their codebase to a rabbit feature for the first time. Reduces "empty template rot": the user reviews a seeded draft instead of staring at a blank file.

## Surface

**agents/**
- `.claude/features/spec-seeder/agents/spec-seeder.md` — agent definition (model: sonnet; tools: Read, Grep, Glob only — read-only enforcement)

**scripts/**
- `.claude/features/spec-seeder/scripts/dispatch-spec-seeder.py` — Python dispatch script. Args: `--feature-name <name> --paths <comma-separated-globs>`. Resolves globs against the user-project root, caps the resolved file list (default 50), invokes `contract/scripts/build-prompt.py --callable-id spec-seeder --slot ...` to assemble the prompt, prints the prompt-file path to stdout.

## Invariants

1. `agents/spec-seeder.md` MUST exist with YAML frontmatter declaring `name: spec-seeder`, `description`, and `tools: Read, Grep, Glob` (exact comma-separated list — no `Write`/`Edit`/`Bash`). Body describes the read-only spec-seeding task. The tool restriction is the load-bearing constraint: it makes side-effects impossible regardless of what the agent attempts.

2. `scripts/dispatch-spec-seeder.py` MUST be executable, have a module-level docstring (Version/Owner/Deprecation criterion), and:
    (a) Accept `--feature-name <name>` (required) and `--paths <globs>` (required; comma-separated path globs relative to the user-project root).
    (b) Resolve each glob via `glob.glob(<glob>, recursive=True)`. Cap the resolved file list at 50 entries (deterministic — sorted lexicographically, take first 50).
    (c) Invoke `python3 .claude/features/contract/scripts/build-prompt.py --callable-id spec-seeder --slot feature_name=<name> --slot paths_globs=<globs> --slot paths_resolved=<newline-joined-resolved-list>` as a subprocess; print the resulting prompt-file path to stdout on success; exit nonzero on subprocess failure.
    (d) Stdlib only.

3. `feature.json` MUST declare a `prompts` entry with `id: spec-seeder`, `kind: subagent`, `inject: [".claude/features/policy/philosophy.md", ".claude/features/policy/coding-rules.md"]`, and `slots: ["feature_name", "paths_globs", "paths_resolved"]`. The matching template at `.claude/features/contract/templates/prompts/spec-seeder.txt` is owned by contract (Inv 57).

4. Tests (`test/`):
    (a) `test-agent-definition.py` — asserts agent file exists, has valid YAML frontmatter, `tools` field is exactly `"Read, Grep, Glob"` (no other tools), `name == "spec-seeder"`.
    (b) `test-dispatch-script.py` — invokes `dispatch-spec-seeder.py --feature-name foo --paths "tmp/**"` in a tmpdir with sample files; asserts (i) exit 0, (ii) prints a prompt-file path, (iii) the prompt file exists and contains the slot-substituted values.
    (c) `test-prompts-section-shape.py` — asserts `feature.json prompts[0]` shape: id, kind=subagent, inject contains philosophy + coding-rules, slots == ["feature_name", "paths_globs", "paths_resolved"].

## Tech Stack

Python 3 stdlib only.

## What this feature does NOT define

- The invocation site (`rabbit-feature-new` plugin-mode path) — owned by `rabbit-feature`.
- The prompt template — owned by `contract` (per Inv 57).
- The agent's runtime model selection — encoded in the agent frontmatter; Claude Code dispatches.
- Spec-seeding for rabbit-self features — out of scope; the existing scaffold + manual authoring covers self-development.

## Tests

`test/run.py` invokes every `test-*.py` in this directory. Currently covers the three behavioural tests above.
