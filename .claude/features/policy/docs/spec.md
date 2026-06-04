---
feature: policy
version: 1.13.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native subagent-policy injection point
status: active
---

# policy — Spec

## Purpose

Owns the three canonical rule files loaded by every subagent dispatch and
by the repo-root `CLAUDE.md` via `@`-imports.

## Surface

- `.claude/features/policy/philosophy.md`
- `.claude/features/policy/spec-rules.md`
- `.claude/features/policy/coding-rules.md`

## Tech Stack

Python 3 stdlib only. No `.sh` files appear anywhere within the feature
directory.

## Invariants

1. **Rule files present.** Each of `philosophy.md`, `spec-rules.md`, and
   `coding-rules.md` exists at the feature root and is non-empty.

2. **Legacy rule file absent.** `workflow-rules.md` does NOT exist anywhere
   within the feature directory.

3. **No shell scripts.** No file ending in `.sh` exists anywhere within
   the feature directory.

4. **Surgical-Changes semantics.** `coding-rules.md` Section 3
   ("Surgical Changes") MUST state that "uncommitted" includes BOTH
   staged and unstaged work from the current agent session, and that
   once a change is committed (even within the same session) it counts
   as pre-existing and MUST be mentioned rather than deleted.

5. **Test deprecation criteria.** Every Python file under `test/`
   (excluding the harness `run.py`) MUST declare a
   `Deprecation criterion:` line in its module docstring per the
   metadata-location contract in `spec-rules.md` ("Where the metadata
   lives", Scripts row).

6. **Read-before-Edit principle.** `coding-rules.md` MUST contain a
   principle expressing all three of: (a) read an existing file before
   editing it, (b) read the surrounding module before writing alongside
   existing code, (c) edits made without reading are speculative. The
   principle propagates the lesson of rabbit-feature's spec-edit
   Read-before-Edit obligation — named, not numbered, so the citation
   remains stable across rabbit-feature renumbers.

7. **Canonical invariants test name.**
   `test/test-policy-invariants.py` is the canonical name for the
   spec-conformance suite. Files matching
   `test/test-policy-invariants-v*.py` MUST NOT exist.
   `test/test-files-exist.py` MUST NOT exist; its coverage is subsumed
   by `test/test-policy-invariants.py`.

8. **Historical-fixes regression guard.**
   `test/test-policy-bug-fixes.py` is a documentary regression guard
   for closed historical tickets. It MUST declare a module-level
   `TICKETS_COVERED` list whose elements are ticket-id string literals
   (one per element). Its module docstring MUST name the retirement
   pointer: the file is removed once `test/test-policy-invariants.py`
   carries a `# Subsumes: <ticket-id>` marker comment for every ticket
   in `TICKETS_COVERED`. A companion watch test
   `test/test-historical-fixes-retirement.py` MUST exist; it MUST FAIL
   once every ticket in `TICKETS_COVERED` is subsumed, and that failure
   is the signal to delete both files together.

9. **Behavior-first test filenames.** Every file matching `test/*.py`
   MUST use a behavior-first name. Files matching any of
   `test/test-POLICY-\d+-*.py`, `test/test-backlog\d+.py`, or
   `test/test-backlog-\d+-\d+.py` MUST NOT exist. Ticket IDs appear
   only inside docstring headers as `Traces:` lines, never embedded in
   filenames. `test/run.py` is the harness, not a test, and is
   excluded from this restriction.

### Meta-contract sections

10. **Meta-contract sections declared empty.** `policy/feature.json`
    declares the meta-contract sections `manifest`, `runtime`, and
    `configuration` explicitly, with the exact shapes `manifest: []`,
    `runtime: {}`, and `configuration: []`. All three are empty because
    policy is a content-only feature with no deployment surface: its
    three rule files are consumed in-place at
    `.claude/features/policy/` by rabbit-cage's `generate-claude-md`
    producer, never deployed to `.claude/`.

### SKILL.md authoring standard

11. **SKILL.md Authoring Standard present.** `spec-rules.md` MUST carry a
    "SKILL.md Authoring Standard" section with three terse, citable rules,
    each deriving from an existing policy principle: (a) **Script-Backed
    Orchestration** — orchestration steps with computed values or
    mode-aware branching belong in a companion `scripts/` script, not in
    SKILL.md prompt-tier bash blocks with runtime placeholders (derives
    from §1 Tool-Choice Tier); (b) **Verbatim Policy Embedding** — a
    SKILL.md surfacing policy MUST quote the canonical policy file
    verbatim (via `@path` injection or a reader script), never paraphrase
    (derives from §2 Schemas and Contracts); (c) **skill-creator
    Validation** — SKILL.md changes MUST pass through the `skill-creator`
    tool before deployment (derives from §1 determinism). The
    `test/test-rule-files-content.py` content guard asserts the section
    heading and the three rule names.

## Out of Scope

- Generating policy output on demand — consumers read the rule files
  directly.
- Modifying files in any other feature.
- Pinning detailed content (section counts, exact phrasings) of the
  three rule files beyond the structural invariants above.
