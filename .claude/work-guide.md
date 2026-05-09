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
- Remove imports/variables/functions that YOUR changes made unused in the
  current (uncommitted) edit. This is "cleaning up your own mess."
- The exception does NOT extend to previously committed artifacts. Once
  code is committed it is pre-existing — mention it, don't delete it.

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

### 8. Main Session Is a Dispatcher, Not an Implementer

**Dispatch subagents for all implementation work. Never edit code directly.**

For any task that involves writing or modifying implementation artifacts
(code, specs, tests, config), the main session MUST dispatch a subagent:

- Bug triage → dispatch `rabbit-vet`; write `vet-triage.json` from its output.
- Code fix or feature → dispatch `rabbit-breeder` with the appropriate
  `SCOPE` path (per R6). Touch the scope marker before dispatch; remove after.
- The main session reads, decides, dispatches, verifies. It does not edit.

**Exceptions (direct calls allowed without subagent):**
- Read-only queries (`list-bugs.sh`, `bug-status.sh get`, grep)
- Status transitions performed by a scoped agent within its own active scope
  (e.g. breeder calling `bug-status.sh set ... closed --skip-vet-reason ...`)
- Simple answers to questions that don't touch any file

---

## Part III — Hard Rules

The rules in this section are operational add-ons enforced by deterministic
checks shipped with the workflow. The full text and the check scripts live
in `.claude/features/hard-rules/`. This section is a one-line index.

- **R1 — Branch per feature; never work on main.** Every feature mutation
  goes on a new branch and through a PR. Direct commits to `main`/`master`/
  `trunk`/`develop` are forbidden. Check:
  `.claude/features/hard-rules/scripts/check-no-main-edits.sh`.

- **R2 — Opus for brainstorming / spec / planning subagents.** Any subagent
  whose description matches `brainstorm|spec|plan|design|architect` MUST
  declare `model: opus` in its frontmatter. Check:
  `.claude/features/hard-rules/scripts/check-opus-for-planning-agents.sh`.

- **R3 — Tests are end-to-end, no human intervention.** No `read`,
  `select`, or other interactive constructs in any feature's `test/`. Check:
  `.claude/features/hard-rules/scripts/check-tests-non-interactive.sh
  <feature-dir>`.

- **R4 — TDD step transitions go through `tdd-step.sh`.** Manual edits to
  `feature.json:tdd_state` bypass the forward-only gate and the drift
  check. Documented policy enforced by the `breeder` subagent and PR review.

- **R5 — Unified work model: features live anywhere, same discipline
  applies.** A feature directory is a feature directory regardless of
  parent path; `.claude/features/<x>/` and `projA/features/<y>/` are
  treated identically by every script and subagent. The scope-guard hook
  detects feature dirs by `feature.json` presence, not path prefix. No
  rabbit-dev-mode vs user-mode dichotomy in the runtime.

- **R6 — Every Agent dispatch prepends the canonical policy block.**
  Universal: rabbit's own subagents AND Claude's built-in subagents.
  The block is produced by
  `.claude/features/subagent-policy-injection/scripts/policy-block.sh`
  (with optional `--include <path>` flags for dispatch-relevant rule
  files) and prepended to the `prompt` field of every Agent call. This
  closes the subagent drift gap at invocation start. Dispatcher
  discipline + PR review (no Agent-tool hook in Claude Code).

- **R7 — Vet before close; main session never skips.** Before closing any
  bug, main session dispatches `rabbit-vet`, receives a `TRIAGE:` block,
  and writes `vet-triage.json`. Only scoped agents may use `--skip-vet-reason`.
  Enforcement: `bug-status.sh` gate + PR review.

The full statement, rationale, and tests for each rule live in
[`hard-rules/spec.md`](./features/hard-rules/spec.md).

---
