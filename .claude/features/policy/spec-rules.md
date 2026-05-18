# Spec Rules

This guide applies to AI agents that author or modify code or specifications.

---

## 1. Tool-Choice Tier: `script > CLI > spec > prompt`

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

## 2. Schemas and Contracts

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

## 3. Lifecycle and Ownership

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

**Where the metadata lives.** Each artifact type has a fixed metadata location:

- **Features** — top-level `name`, `version`, `owner`, `deprecation_criterion`
  fields in the feature's `feature.json`.
- **Specs / contracts** — YAML frontmatter at the top of `docs/spec/spec.md`
  and `docs/spec/contract.md` (`feature:`, `version:`, `owner:`,
  `deprecation_criterion:`).
- **Skills and commands** — YAML frontmatter at the top of the `SKILL.md`
  or command `.md` file (`version:`, `owner:`, `deprecation_criterion:`).
- **Scripts** — module-level docstring, with `Version:`, `Owner:`, and
  `Deprecation criterion:` lines.
- **Schemas and JSON contracts** — top-level `schema_version`, `owner`,
  and `deprecation_criterion` keys.
- **Templates** — `template_version` marker (placement convention defined
  by the contract feature's spec).

An artifact missing any of these fields in its declared location is
considered unowned. Promote it to compliance before extending it.

---
