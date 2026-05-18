---
feature: rabbit-spec
version: 1.2.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: When spec authoring is natively handled by the rabbit CLI.
status: active
---

# rabbit-spec — Spec

## Purpose

General-purpose skill for spec authoring. Reads a feature's current spec,
judges the request type (open-ended vs specific), invokes the appropriate
superpowers, updates the spec surgically, and writes an implementation
suggestion file. The skill is process-agnostic — any caller (rabbit-feature-touch,
backlog grooming, standalone design review, direct user invocation) can use it,
and the skill makes no assumptions about who called it or what happens next.

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
7. SKILL.md MUST be process-agnostic. It MUST NOT identify any specific caller
   (e.g., "you are invoked as Step 3 in rabbit-feature-touch") as the primary
   or sole invocation context, and MUST NOT reference a specific downstream
   consumer (e.g., "the TDD subagent reads this file") as a guaranteed next
   step. The skill is invocable by any process; its output (the impl-suggestion
   file) is for whoever called it.
8. SKILL.md "What You Do NOT Do" section MUST NOT instruct the skill to avoid
   invoking specific named skills (e.g., rabbit-feature-touch). A generic rule
   like "do not invoke other skills" is acceptable; a process-specific one is not.
9. `feature.json` `version` MUST equal `docs/spec/spec.md` frontmatter `version`
   at every commit. Drift between the two means consumers reading one source see
   stale lifecycle/contract information. A test MUST enforce equality.
10. Every numbered spec invariant MUST have at least one corresponding test in
    `.claude/features/rabbit-spec/test/`. Specifically, Inv 3 (impl-suggestion
    schema conformance) is covered by a structural test asserting the SKILL.md
    body documents every required field of the impl-suggestion schema. Inv 5
    (spec.md updated before impl-suggestion written) is covered by parsing
    SKILL.md and asserting the "Update the Spec" step heading appears textually
    before the "Write impl-suggestion File" step heading. Missing tests for
    Inv 3 and Inv 5 were filed as RABBIT-SPEC-BUG-6 and BUG-7 (Wave 3).

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
