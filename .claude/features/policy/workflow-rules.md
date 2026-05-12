# Workflow Rules

---

## 1. Subagent-driven by construction

Every implementation touch goes through a dispatched subagent via `dispatch-feature-edit.sh`. The main session reads, decides, dispatches, and verifies. It does not write files.

---

## 2. Main Session Is a Dispatcher, Not an Implementer

**Dispatch subagents for all implementation work. Never edit code directly.**

For any task that involves writing or modifying implementation artifacts
(code, specs, tests, config), the main session MUST dispatch a subagent:

- Bug triage → run `rabbit-triage.sh <feature-dir> <bug-name>` (via `.claude/features/contract/scripts/`), invoke Agent with the resulting prompt, capture the TRIAGE: block, and write `vet-triage.json`.
- Code fix or feature → dispatch via `dispatch-feature-edit.sh` (via `.claude/features/contract/scripts/`) with the appropriate
  `SCOPE` path (per R6). Touch the scope marker before dispatch; remove after.
- The main session reads, decides, dispatches, verifies. It does not edit.

---

## 3. Full TDD on every feature touch

Any add, edit, or delete of a feature — including a one-character typo fix or a comment deletion — MUST go through the full TDD step sequence managed by `tdd-step.sh`. There is no partial-TDD shortcut. The discipline is uniform because partial flows are where drift enters undetected.

Tests must exercise the full chain from the user-facing entry point through to the final state change. Testing individual script behavior in isolation is not sufficient — E2E coverage across all feature layers is required.

---

## 4. Token/compliance tradeoff is the user's call

Full TDD costs tokens. The cost is intentional: accumulated drift costs more than any individual dispatch. The user always retains the judgment of whether to initiate a dispatch at all. The rule is: if you touch a feature, run the full discipline. Choosing not to touch is always available and always free.

---

## 5. Hard rules index (R1–R9)

- **R1** — Branch per feature; never commit directly to main.
- **R2** — Use Opus for brainstorm, spec, plan, design, and architect subagents.
- **R3** — Tests are end-to-end and non-interactive — no `read` or `select`.
- **R4** — TDD state transitions go through `tdd-step.sh` only.
- **R5** — Features live anywhere; the same discipline applies everywhere.
- **R6** — Every Agent dispatch prepends the canonical policy block.
- **R7** — Vet every bug before closing — triage first, then close.
- **R8** — Every feature touch runs full TDD.
- **R9** — Project-level contract wins over rabbit contract at conflict.

---

## 6. Cross-component handoffs use schemas, not prose

Every handoff between components uses a declared, versioned schema. Free-form text at a boundary is a bug. Schema fields are typed, named, and validated at the boundary by the receiving component.

---
