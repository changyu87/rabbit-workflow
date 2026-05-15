# Workflow Rules

*These rules govern how work moves through the rabbit system — from intent to
artifact. They bind the temporal and procedural dimension: the order in which
things happen, who acts, and what state changes are permitted at each step.*

---

## 1. Spec First

Every feature begins with a specification, not code. The spec is the contract.
Implementation follows the spec; the spec does not follow the implementation.

If a spec is absent, stop. File the spec before touching code.

---

## 2. TDD Cycle

Every code change follows the red-green cycle: write a failing test, then make
it pass. No implementation without a test. No test that is skipped or xfail
without a documented reason tied to a tracked issue.

---

## 3. Scope Before Write

Every write to a `.claude/features/<feature>/` directory requires an active
scope marker for that feature. Writes without a scope marker are rejected.

Use `/rabbit-feature-touch` to open scope. Never bypass the gate.

---

## 4. Branch Per Feature

Each feature lives on its own branch. A branch is opened when scope opens and
closed (merged or abandoned) when scope closes. Long-lived branches that span
multiple unrelated features are a scope violation.

---

## 5. Structured Handoffs

When a task crosses a feature boundary or requires a different agent, stop and
emit a structured handoff: what was done, what is out-of-scope, and what
context the receiving party needs. Never silently assume cross-boundary work.
