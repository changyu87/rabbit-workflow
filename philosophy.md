
---

## Philosophy

*These four principles guard against silent drift — the slow, unattributable decay of a system into a state where no one can answer "why did it do that?" Each principle guards one dimension: who executes, what is produced, how components meet, and how long things live.*

*When principles seem to conflict, decompose the act: each principle binds a different dimension, and conflicts are category collisions, not contradictions. Engineering judgment is the chooser of how to act — it is not itself ranked.*

---

### 1. Script Over Token: `script > CLI > spec > prompt`

When choosing how a task gets done, reach for determinism first, AI last.

- **Script** — code you own, version, and control. Fully deterministic.
- **CLI** — a deterministic tool invocation. No AI inside.
- **Spec** — structured directives that tightly constrain what AI does. Minimal interpretive freedom.
- **Prompt** — a free-form request to AI. Maximum freedom. Minimum predictability.

Determinism means the failure is locatable to a source artifact your team can read or escalate against — not merely that the function is byte-reproducible. A script fails reproducibly: the error is locatable and fixable. An LLM fails silently — it drifts, hallucinates, or returns different output from identical input.

---

### 2. AI Over Human

Every state file, metadata, and data structure is designed for machine consumption first. Use fixed-format schemas for every handoff — never free-form text.

When a human needs to read state, run a script that extracts and formats it. The machine is the primary consumer. The human is secondary.

---

### 3. Isolated Contract Interface

Each component operates within its own bounded scope. No boundary crossing.

All inter-component communication is contract-bound. Read nothing outside the contract. Generate nothing outside the contract.

This principle governs the **runtime layer**. The design layer — where contracts are authored, evolved, and deprecated — is upstream. When design and runtime are co-located in a single process, decompose the process into its design acts and runtime acts; this principle binds the runtime acts.

---

### 4. Designed Deprecation

Every actor, artifact, and contract is created with an explicit end-of-life criterion.

Contracts carry versions. Changes are additive by default; breaking changes require a coexistence window and a migration path. Scripts and components have named owners — an unowned artifact is not a reliable artifact. Every dependency, schema, and encoding will be superseded: name the deprecation criterion at creation time, or inherit the failure.

Predictability without lifecycle is borrowed time.

---
