---
feature: rabbit-spec
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When spec authoring is natively handled by the rabbit CLI.
status: active
---

# rabbit-spec — Spec

## Purpose

Standalone skill for spec authoring. Peeled off from the TDD cycle so it can be
invoked independently during backlog grooming, design, or any feature touch.
Invoked as Step 3 in rabbit-feature-touch before TDD subagent dispatch.

## Scripting Tech Stack

Skill-only feature — no runtime Python scripts. All logic lives in SKILL.md.
The sole test runner is test/run.py which validates structural invariants.

## Surface

- `.claude/features/rabbit-spec/skills/rabbit-spec/SKILL.md`

## Invariants

1. SKILL.md MUST declare `model: opus` in its YAML frontmatter.
2. rabbit-spec MUST judge whether a request is open-ended or specific before
   deciding which superpowers to invoke (open → brainstorming + writing-plans;
   specific → writing-plans only).
3. rabbit-spec MUST write `.rabbit/impl-suggestion-<feature>.json` conforming
   to schema_version 1.0.0 on every invocation.
4. rabbit-spec MAY read any file in the target feature directory freely.
5. rabbit-spec MUST update `docs/spec/spec.md` in the target feature directory
   before writing the impl-suggestion file.
6. `surface.skills` in `feature.json` MUST be `[]`. Skills are managed via
   explicit copy-file entries in `build-contract.json`.

## impl-suggestion Schema (v1.0.0)

```json
{
  "schema_version": "1.0.0",
  "feature": "<name>",
  "generated_at": "<iso timestamp>",
  "request_summary": "<what was asked>",
  "spec_changes": "<summary of what changed in spec>",
  "implementation_approach": "<narrative suggestion>",
  "affected_files": ["<file1>", "<file2>"],
  "key_invariants": ["<invariant1>"]
}
```

## Out of Scope

- Running tests or implementing code (that is the TDD subagent's job).
- Filing bugs or backlog items (that is rabbit-file's job).
- Scaffolding new features from scratch (that is rabbit-project's job).
