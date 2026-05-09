# Policy Feature — Spec

**owner:** rabbit-workflow team
**version:** 1.0.0
**deprecation_criterion:** when Claude Code exposes a native subagent-policy injection point

---

## Purpose

The `policy` feature owns the canonical rule files that are injected into every subagent dispatch. It replaces two flat files — `.claude/philosophy.md` and `.claude/work-guide.md` — with four purpose-scoped files that can be selectively included per dispatch type.

This split reduces per-dispatch token cost (only the relevant rules need inclusion) and gives the rule set a first-class feature lifecycle: owner, version, and explicit deprecation criterion.

---

## Rule Files

### `philosophy.md`
The three foundational principles: Machine First, Bounded Scope, Designed Deprecation. Injected into every subagent dispatch. Content is verbatim from `.claude/philosophy.md`.

### `spec-rules.md`
Construction rules for agents that author or modify code and specifications (Part I of the former work-guide): Tool-Choice Tier, Schemas and Contracts, Lifecycle and Ownership. Injected into spec-authoring and planning subagents.

### `coding-rules.md`
Code-editing discipline (Part II of the former work-guide, Karpathy sections): Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution, Main Session Is a Dispatcher. Injected into implementation subagents (`rabbit-breeder` and equivalents).

### `workflow-rules.md`
Operational workflow rules: subagent-driven construction, full TDD discipline, token/compliance tradeoff policy, and the hard-rules index (R1–R9). Injected into dispatchers and any subagent that may need to invoke further dispatches.

---

## Invariants

- Rule files are **read-only for consumers**. No subagent or downstream feature may write to these files.
- Only the `policy` feature (i.e., a dispatch scoped to `.claude/features/policy/`) may modify any rule file.
- Human-readable views of the policy are derived from these files by tooling — never authored separately.
- Every rule file update must go through the full TDD step sequence (R8).

---

## Deprecation Criterion

This feature is superseded when Claude Code exposes a native subagent-policy injection point that makes file-level policy injection redundant. At that point the four rule files become input to the native mechanism; the policy feature itself and its injection glue are retired.
