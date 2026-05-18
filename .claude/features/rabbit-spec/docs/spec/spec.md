---
feature: rabbit-spec
version: 1.3.0
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
  "generated_at": "<iso 8601 UTC timestamp, e.g. 2026-05-18T03:42:11Z>",
  "request_summary": "<what was asked>",
  "spec_changes": "<summary of what changed in spec>",
  "implementation_approach": "<narrative suggestion>",
  "affected_files": ["<repo-relative path 1>", "<repo-relative path 2>"],
  "key_invariants": ["<invariant1>"],
  "owner": "<optional: named individual or team accountable for the suggested change>",
  "deprecation": "<optional: end-of-life criterion for the suggested artifact, if applicable>"
}
```

### Field Semantics

- `schema_version` — MUST equal `"1.0.0"` for this schema revision.
- `generated_at` — ISO 8601 UTC timestamp. Format: `YYYY-MM-DDTHH:MM:SSZ`
  (RFC 3339 profile with `Z` suffix). Test must assert this shape.
- `affected_files` — list of repo-relative paths the implementer is expected
  to modify when carrying out the suggestion. Paths SHOULD point at files
  whose contents will change; new files MAY be included. Globs are not
  permitted — each entry is a concrete path. Reading-only files are NOT
  listed.
- `key_invariants` — invariants from the updated spec that directly
  constrain the implementation (i.e., that the implementer should re-read
  before coding).
- `owner` (optional) — the named individual or team accountable for the
  suggested change (Designed-Deprecation principle).
- `deprecation` (optional) — the end-of-life criterion for the suggested
  artifact, if the suggestion creates a new artifact.

## What the Skill Reads

The skill MAY read any file inside the target feature's directory. At
minimum, callers SHOULD expect it to read:

- `docs/spec/spec.md` — the current spec (required).
- `docs/spec/contract.md` — the current contract (if present).
- `scripts/`, `skills/`, and any other implementation directories — so the
  skill does not re-spec already-implemented behavior.

When the `feature-name` argument names a directory that does not exist
under `.claude/features/`, the skill MUST abort gracefully with an explicit
error message naming the missing feature and the directory it expected to
find. The skill MUST NOT silently fall back to creating a new feature.

## Out of Scope

- Running tests or implementing code (out of this skill's scope).
- Filing bugs or backlog items (out of this skill's scope).
- Scaffolding new features from scratch (out of this skill's scope).
