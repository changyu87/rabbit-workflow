# Philosophy Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the existing `philosophy.md` into a three-principle abstract `philosophy.md` (for all AI subagents) and a comprehensive `work-guide.md` (for code/spec-touching agents only).

**Architecture:** Two standalone, self-contained markdown files in repo root. No cross-references between them. Source spec at `docs/superpowers/specs/2026-05-08-philosophy-split-design.md`.

**Tech Stack:** Markdown only. No code, no tests beyond byte-level content verification via `diff` and `git status`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `philosophy.md` | Modify (full rewrite) | Three abstract principles for ALL AI subagents |
| `work-guide.md` | Create | Construction rules + Karpathy's editing discipline for code/spec-touching agents |
| `philosophy-CN.md` | Untouched | (Future task: translate new files) |
| `philosophy-brainstorm.md` | Untouched | Audit trail |
| `philosophy-debate.md` | Untouched | Audit trail |
| `philosophy-holes.md` | Untouched | Audit trail |

---

### Task 1: Rewrite `philosophy.md`

**Files:**
- Modify: `/home/cyxu/ai-workflow-philosophy/philosophy.md` (full rewrite)

- [ ] **Step 1: Capture current content for diff verification**

Run: `cp /home/cyxu/ai-workflow-philosophy/philosophy.md /tmp/philosophy.md.bak`

Expected: silent success, file copied.

- [ ] **Step 2: Overwrite `philosophy.md` with the new three-principle content**

Use the Write tool to write the following exact content to `/home/cyxu/ai-workflow-philosophy/philosophy.md` (note: file begins with one blank line, then `---`, matching the original file's leading-blank-line convention):

````markdown

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
````

- [ ] **Step 3: Verify the file was written correctly**

Run: `diff /tmp/philosophy.md.bak /home/cyxu/ai-workflow-philosophy/philosophy.md | head -80`

Expected: a non-empty diff. Confirm visually that the diff shows: (a) old "four principles" intro replaced with new "three principles" intro, (b) old §1 "Script Over Token" removed, (c) old §2 renamed to "Machine First", (d) old §3 renamed to "Bounded Scope" and merged with new escalation language, (e) old §4 renamed to "Designed Deprecation" with abstracted body.

- [ ] **Step 4: Sanity-check that no other files were touched**

Run: `git status --short`

Expected output should show ONLY `philosophy.md` modified plus the two pre-existing untracked `.swp` files. If any other file appears, stop and investigate.

---

### Task 2: Create `work-guide.md`

**Files:**
- Create: `/home/cyxu/ai-workflow-philosophy/work-guide.md`

- [ ] **Step 1: Confirm file does not already exist**

Run: `ls /home/cyxu/ai-workflow-philosophy/work-guide.md 2>&1`

Expected: `ls: cannot access ...: No such file or directory` (exit 2). If the file exists, stop and check with the user before overwriting.

- [ ] **Step 2: Write `work-guide.md`**

Use the Write tool to write the following exact content to `/home/cyxu/ai-workflow-philosophy/work-guide.md`:

````markdown
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
````

- [ ] **Step 3: Verify the file exists and has the expected size**

Run: `wc -l /home/cyxu/ai-workflow-philosophy/work-guide.md`

Expected: roughly 130–150 lines. If wildly different, inspect for truncation.

- [ ] **Step 4: Sanity-check git status**

Run: `git status --short`

Expected: shows `M philosophy.md` and `?? work-guide.md` (plus pre-existing `.swp` files). No other modifications.

---

### Task 3: Verify untouched files are unchanged

**Files:**
- Verify (no modification): `philosophy-CN.md`, `philosophy-brainstorm.md`, `philosophy-debate.md`, `philosophy-holes.md`

- [ ] **Step 1: Confirm none of the untouched files appear in `git status`**

Run: `git status --short | grep -E '(philosophy-CN|philosophy-brainstorm|philosophy-debate|philosophy-holes)\.md'`

Expected: empty output (no matches). If anything matches, an untouched file was accidentally modified — stop and investigate.

- [ ] **Step 2: Confirm the only `.md` files staged or modified are the two intended ones**

Run: `git status --short | awk '{print $2}' | grep '\.md$'`

Expected output (order may vary):
```
philosophy.md
work-guide.md
```

If any other `.md` files appear, stop.

---

### Task 4: Commit the split

**Files:**
- Stage: `philosophy.md`, `work-guide.md`
- Do NOT stage: `.swp` files, `.philosophy.md.swp`

- [ ] **Step 1: Stage only the two intended files**

Run: `git add philosophy.md work-guide.md`

- [ ] **Step 2: Verify staging is correct**

Run: `git status --short`

Expected: `M  philosophy.md` and `A  work-guide.md` in the staged area; `.swp` files remain untracked. Confirm visually before committing.

- [ ] **Step 3: Create the commit**

Run:

```bash
git commit -m "$(cat <<'EOF'
Split philosophy.md into philosophy + work-guide

philosophy.md is now three abstract, instructive principles
(Machine First / Bounded Scope / Designed Deprecation) — orthogonal
along form, space, and time — for ALL AI subagents.

work-guide.md is new and applies only to agents that author or
modify code or specs. It collects the concrete tool-tier hierarchy,
schema/contract mechanics (with an explicit out-of-scope escalation
procedure), lifecycle/ownership mechanics, and Andrej Karpathy's
four code-editing guidelines (verbatim, with attribution).

Both files are standalone and self-contained — neither references
the other. Existing files (philosophy-CN.md, philosophy-brainstorm.md,
philosophy-debate.md, philosophy-holes.md) are untouched.

Design spec: docs/superpowers/specs/2026-05-08-philosophy-split-design.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Verify commit landed cleanly**

Run: `git status && git log -1 --stat`

Expected: working tree clean except for the two pre-existing `.swp` files; the latest commit shows two files changed (philosophy.md modified, work-guide.md created).

---

## Self-Review Checklist (run mentally before declaring done)

1. **Spec coverage:** Every acceptance criterion in §5 of the spec has a corresponding step in this plan. ✓
2. **No placeholders:** No "TBD" / "TODO" / "fill in" / "similar to Task N" — every step contains the actual content needed. ✓
3. **Type consistency:** N/A (markdown content only). The principle names ("Machine First", "Bounded Scope", "Designed Deprecation") are consistent across both files. ✓
4. **Frequency of commits:** One logical commit. The split is one logical change — splitting it into two commits would leave an intermediate state where philosophy.md is rewritten but the work guide doesn't yet exist, which is incoherent. Single commit is the right granularity here.
