---
feature: rabbit-spec
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
status: active
---

# rabbit-spec — Spec

## Purpose

rabbit-spec is the owner of the rabbit workflow's spec-lifecycle skills — the
skills that read, draft, and revise a feature's `docs/spec/spec.md`. The
feature is **currently empty**: it carries no surface artifacts. Its concrete
skills land in subsequent waves:

- `rabbit-spec-create` (Stage 2) — drafts the initial spec body from feature
  name + optional code globs + optional description. Absorbs the existing
  spec-seeder agent and dispatch script.
- `rabbit-spec-update` (Stage 3) — revises an existing spec body based on a
  request. Absorbs the existing `rabbit-feature-spec` skill and promotes it
  to a subagent-driven dispatch for parallelism and context isolation.

This empty-revival stage exists to flip the directory from a tombstone to an
active feature so the surface absorbs from spec-seeder and rabbit-feature
have a home to land in. The cross-feature ripples — the rabbit-spec node in
`workspace-structure.json`, the rabbit-spec assertion in
`test-retirement-semantics.py`, and the rabbit-spec entries in rabbit-cage's
install.py / spec.md retired-tombstone lists — are part of this same
revival cycle.

## Surface

No surface artifacts yet. Stage 2 adds `rabbit-spec-create` (skill + agent +
dispatch script); Stage 3 adds `rabbit-spec-update` (skill + agent + dispatch
script). Until then, the feature is structurally complete (feature.json,
spec.md, contract.md, test/run.py) but functionally inert.

## Invariants

1. `feature.json` MUST declare `status: "active"` (not `"retired"`),
   `version: "1.0.0"`, `owner: "rabbit-workflow team"`,
   `tdd_state: "test-green"`, a non-empty `summary`, a non-empty
   `deprecation_criterion`, and an empty `surface` block
   (`{"skills": [], "hooks": [], "commands": [], "agents": []}`). The
   `successor` and `deprecation` fields from the retirement record MUST
   be absent. The `manifest`, `runtime`, and `configuration` blocks MUST
   either be absent or be empty containers.

2. `docs/spec/spec.md` MUST exist with frontmatter declaring `status: active`
   and `version: 1.0.0`. The body MUST describe the future-population intent
   (rabbit-spec-create and rabbit-spec-update arriving in later stages) and
   MUST NOT contain RETIRED markers, successor pointers, or retirement
   lifecycle prose.

3. `docs/spec/contract.md` MUST exist with proper YAML frontmatter
   (`feature: rabbit-spec`, `version: 1.0.0`, `template_version: 2.0.0`)
   and a JSON block declaring empty `provides`/`reads`/`invokes` and a
   `never` array that includes `"introduces any surface artifact without first updating spec.md"`.

4. `test/run.py` MUST exist as a Python 3 stdlib runner that scans `test/`
   for `test-*.py` files and exits 0 — on an empty test set (no matching
   files), the runner MUST still exit 0 (not error). The previous
   `test/test-retired.py` MUST be removed because rabbit-spec is no longer
   retired.

## Tech Stack

Python 3 stdlib only.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Currently the
directory contains only the runner itself — no per-invariant tests yet — and
the runner exits 0 on the empty case. Per-invariant coverage arrives with
the surface artifacts in Stage 2 / Stage 3.

## Out of Scope

- The actual rabbit-spec-create and rabbit-spec-update skills — landing in
  Stage 2 and Stage 3 respectively, not in this revival cycle.
- Cross-feature artifact updates outside rabbit-spec's own directory — the
  `workspace-structure.json` node flip, the contract retirement-semantics
  test assertion, and the rabbit-cage retired-tombstone-list edits are
  owned by those features' TDD subagents in the same revival PR.
