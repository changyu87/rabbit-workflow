# Coding Rules

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

- Bug triage → run `rabbit-triage.sh <feature-dir> <bug-name>`, invoke Agent with the resulting prompt, capture the TRIAGE: block, and write `vet-triage.json`.
- Code fix or feature → dispatch `rabbit-breeder` with the appropriate
  `SCOPE` path (per R6). Touch the scope marker before dispatch; remove after.
- The main session reads, decides, dispatches, verifies. It does not edit.

**Exceptions (direct calls allowed without subagent):**
- Read-only queries (`list-bugs.sh`, `bug-status.sh get`, grep)
- Status transitions performed by a scoped agent within its own active scope
  (e.g. breeder calling `bug-status.sh set ... closed --skip-vet-reason ...`)
- Simple answers to questions that don't touch any file

---
