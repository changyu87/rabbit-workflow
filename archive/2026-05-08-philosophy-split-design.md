# Philosophy Split — Design

**Date:** 2026-05-08
**Status:** Ready for implementation
**Goal:** Split the existing `philosophy.md` into two standalone, self-contained
files: a high-level abstract `philosophy.md` (for all AI subagents) and a
concrete `work-guide.md` (only for agents that touch code or specifications).

---

## 1. Motivation

The current `philosophy.md` mixes two genres in a single document:

1. **Abstract laws** about how a system should behave (e.g., "every component
   operates within its bounded scope").
2. **Concrete mechanics and tool-choice rules** (e.g., the
   `script > CLI > spec > prompt` tier list, contract-versioning
   conventions, named-owner conventions).

The mixed genres create three concrete problems:

- **Audience mismatch.** Philosophy should apply to *all* AI subagents
  (orchestrators, reviewers, planners, code-touchers). Tool-tier rules and
  schema mechanics only apply to code- and spec-touching agents. Forcing
  every agent to read both wastes attention.
- **Aesthetic incoherence.** The current Principle 1 (`script > CLI > spec
  > prompt`) names specific tools and reads like a tactical playbook entry
  rather than a philosophical law. The current Principle 4 (Designed
  Deprecation) reads as a patch to Principle 1 because both reference scripts
  by name; once Principle 1 is abstracted away, Principle 4 stands alone.
- **Missing guidance.** A new behavioral principle — *Scope Awareness* —
  needs a home. So do battle-tested code-editing rules from external sources
  (Andrej Karpathy's CLAUDE.md). Neither fits cleanly in the current file.

## 2. Decisions

The following decisions were settled through bounded brainstorming with the
user (see appendix for the question-by-question log):

1. **Scope Awareness merges with Isolated Contract Interface** into a single
   philosophy principle, **Bounded Scope**, with two facets: structural
   (cross via contracts only) and behavioral (out-of-scope work returns to
   the scope's owner). Written instructively, not behaviorally.
2. **Philosophy holds exactly three principles** (Three-Laws aesthetic).
   The fourth candidate — *Determinism First* (the abstracted form of the
   old `script > CLI > spec > prompt` rule) — is dropped from philosophy
   and lives only in the work guide. The three remaining principles map to
   three orthogonal dimensions: **form**, **space**, **time**.
3. **Karpathy's four guidelines are adopted verbatim** in the work guide
   with attribution.
4. **Work guide is comprehensive.** It contains: tool-choice tier (rescued
   from old #1), schema/contract mechanics (rescued from old #2 and old #3),
   lifecycle mechanics (rescued from old #4), and Karpathy's four guidelines.
   One file, structured in two parts.
5. **English only this round.** `philosophy-CN.md` is left untouched and a
   future task may translate the new files.
6. **Intro to philosophy** rewrites the first paragraph (to name the new
   form/space/time triad) and keeps the second paragraph (the "category
   collision" rule) verbatim.
7. **Files are standalone and self-contained.** Neither file references
   the other. Each agent loads only what it needs and does not need to
   know the other exists.
8. **Old #2 ("AI Over Human") is renamed "Machine First"** to disambiguate
   from "AI assistants over humans".
9. **The "design layer is upstream" footnote** in the old #3 is dropped —
   philosophy should not carry footnotes.
10. **Work guide structure is two-part:** Part I (Construction Rules,
    §1-3 — *what an artifact must be*) and Part II (Code-Editing Discipline,
    §4-7 — *how to behave while editing*). The escalation procedure
    (operational form of "report to scope owner") is a sub-bullet under §2,
    not its own section.

## 3. Files

### 3.1 `philosophy.md` (rewrite)

```markdown
---

## Philosophy

*These three principles guard against silent drift — the slow, unattributable
decay of a system into a state where no one can answer "why did it do that?"
Each principle binds one orthogonal dimension: the form artifacts take, the
space they occupy, and the time they live across.*

*When principles seem to conflict, decompose the act: each principle binds a
different dimension, and conflicts are category collisions, not contradictions.
Engineering judgment is the chooser of how to act — it is not itself ranked.*

---

### 1. Machine First

Every state, metadata, interface, and artifact is designed for machine
consumption first. Handoffs use fixed-format, structured representations —
never free-form text.

Human-readable views are derivative: produced by tools that operate on the
machine-first artifact, never authored alongside it.

---

### 2. Bounded Scope

Every component operates strictly within its declared scope. Work that falls
outside that scope returns to the scope's owner; it is never assumed by the
boundary-crosser.

Cross-scope communication is contract-bound. Read nothing outside the
contract. Generate nothing outside the contract.

---

### 3. Designed Deprecation

Every artifact is created with an explicit end-of-life criterion. Every
contract carries a version. Every component carries an owner. An unowned,
unversioned, or open-ended artifact is not a reliable artifact.

Predictability without lifecycle is borrowed time.

---
```

### 3.2 `work-guide.md` (new)

```markdown
# Work Guide

This guide applies to AI agents that author or modify code or specifications.

---

## Part I — Construction Rules

### 1. Tool-Choice Tier: `script > CLI > spec > prompt`

When choosing how a task gets done, reach for determinism first, AI last.

- **Script** — code you own, version, and control. Fully deterministic.
- **CLI** — a deterministic tool invocation. No AI inside.
- **Spec** — structured directives that tightly constrain what AI does.
  Minimal interpretive freedom.
- **Prompt** — a free-form request to AI. Maximum freedom. Minimum
  predictability.

Determinism means the failure is locatable to a source artifact your team can
read or escalate against — not merely that the function is byte-reproducible.
A script fails reproducibly: the error is locatable and fixable. An LLM fails
silently — it drifts, hallucinates, or returns different output from identical
input.

---

### 2. Schemas and Contracts

Every cross-component handoff uses a fixed-format, declared schema. Never
free-form text. Schema fields are typed, named, and validated at the boundary.

Every component declares its contract: what it reads, what it writes, what it
invokes. Read nothing outside the contract. Generate nothing outside the
contract.

Human-readable views are produced by tools that operate on the schema-formed
artifact — never authored alongside the machine-format one.

**When a task falls outside your declared scope:** stop, emit a structured
handoff (what you intended, what is out-of-scope, what context the scope's
owner needs), and wait. Do not edit across the boundary, even if the change
appears trivial.

---

### 3. Lifecycle and Ownership

At creation time, every artifact records:

- **Owner** — a named individual or team accountable for it. An unowned
  artifact is not a reliable artifact.
- **Version** — for contracts, schemas, and encodings. Version bumps follow
  semantic conventions appropriate to the artifact.
- **Deprecation criterion** — the condition under which this artifact will be
  superseded (e.g., "when downstream Y migrates to schema v3", "after the
  2026-Q4 platform cutover").

Contract changes are additive by default. Breaking changes require a
coexistence window during which both old and new are honored, and a
documented migration path for consumers.

Every dependency, schema, and encoding will eventually be superseded. Name
the deprecation criterion at creation time, or inherit its failure.

---

## Part II — Code-Editing Discipline

*The four sections below are reproduced verbatim from Andrej Karpathy's
[CLAUDE.md](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md).
They are battle-tested for reducing common LLM coding mistakes.*

*Tradeoff: these guidelines bias toward caution over speed. For trivial
tasks, use judgment.*

---

### 4. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

---

### 5. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes,
simplify.

---

### 6. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

---

### 7. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

    1. [Step] → verify: [check]
    2. [Step] → verify: [check]
    3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it
work") require constant clarification.

---
```

## 4. Out of Scope

The following are explicitly *not* in this round:

- **Translation.** `philosophy-CN.md` is not updated. Future task may produce
  `philosophy-CN.md` (rewrite) and `work-guide-CN.md` (new).
- **Brainstorm/audit files.** `philosophy-brainstorm.md`, `philosophy-debate.md`,
  and `philosophy-holes.md` are left untouched. They are audit trail for how
  the original philosophy was developed.
- **Cross-document references.** Neither file links to the other. Each is
  loaded by a different audience and stands alone.
- **Skill or hook integration.** This spec only writes the two `.md` files;
  no changes to any agent configuration, hook, or settings file.

## 5. Acceptance Criteria

- `philosophy.md` matches §3.1 byte-for-byte.
- `work-guide.md` matches §3.2 byte-for-byte.
- Both files are in repo root.
- `philosophy-CN.md`, `philosophy-brainstorm.md`, `philosophy-debate.md`,
  `philosophy-holes.md` are unchanged (verified by `git diff`).
- Spec doc (this file) is committed under
  `docs/superpowers/specs/2026-05-08-philosophy-split-design.md`.

## 6. Appendix — Brainstorm decision log

| # | Question | Resolution |
|---|---|---|
| 1 | Scope Awareness vs Isolated Contract Interface? | Merge into one principle (Bounded Scope) |
| 2 | Which fourth-candidate principle drops out? | Drop Determinism First; keep form/space/time triad |
| 3 | Karpathy adoption style? | Verbatim with attribution |
| 4 | Work guide content scope? | Comprehensive (tier list + mechanics + Karpathy) |
| 5 | i18n scope? | English only this round |
| 6 | Intro paragraph treatment in philosophy? | Rewrite paragraph 1; keep paragraph 2 verbatim |
| 7 | Files self-contained? | Yes — no cross-references |
| 8 | Rename "AI Over Human" → "Machine First"? | Yes |
| 9 | Drop "design layer is upstream" footnote? | Yes |
| 10 | Work guide structure: flat or two-part? | Two-part (Construction Rules / Code-Editing Discipline) |
| 11 | Escalation procedure as own section or sub-bullet? | Sub-bullet under §2 |
