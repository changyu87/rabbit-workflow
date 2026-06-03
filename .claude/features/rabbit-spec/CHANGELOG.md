---
feature: rabbit-spec
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-spec spec's invariant numbering is folded into a structured schema-tracked log
---

# rabbit-spec — Retired Invariants Log

This file holds the tombstones for invariants previously declared in the feature spec and since retired, plus version notes for notable non-retirement changes.

Each retirement entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the cascade or backlog ID that drove the retirement.

## Version notes

- **v1.7.0 (flat docs/ resolver, #399 Phase 2a):** Updated rabbit-spec's spec-path resolvers to PREFER the flat `docs/spec.md` (and `docs/contract.md`) layout, FALL BACK to `specs/`, then to legacy `docs/spec/`, mirroring the contract feature's `resolve_spec_path` precedence (#399 Phase 1a). No files move (rabbit-spec itself stays on `specs/` so the fallback hits and the repo stays green). Inv 6 rewritten for the three-layout precedence order and now also constrains the drafting agent. `rabbit-spec-update` (v2.2.0 -> v2.3.0) and `rabbit-spec-create` (v1.1.1 -> v1.2.0) rewrote their `Spec-file layout` subsections and every Step 1/3/4 path reference to the flat-docs-preferred order; `agents/rabbit-spec-creator.md` (v1.0.0 -> v1.1.0) now names the flat `docs/spec.md` draft target (was `docs/spec/spec.md`). Inv 2 relaxed the agent version pin to `1.1.0 or later`. `test/test-spec-path-layout-dual-read.py` (v1.0.0 -> v2.0.0) now asserts all three layouts are named, the flat `docs/` is preferred across both SKILL bodies, and the agent targets the flat path. Deprecation criterion for the fallbacks: issue #399 final phase (every feature on flat `docs/`). Deployed skills/agent require republish.

- **v1.6.0 (rename agent spec-creator -> rabbit-spec-creator, #471):** The drafting subagent's base name violated `contract.lib.checks.check_naming` (Inv 10/15), which requires every artifact under `.claude/agents/` to start with `rabbit-` (the deployed `.claude/agents/spec-creator.md` was flagged). `git mv`d the source `agents/spec-creator.md` -> `agents/rabbit-spec-creator.md` and rewrote its frontmatter `name:` and body self-reference. Inv 2 now pins `name: rabbit-spec-creator` at `agents/rabbit-spec-creator.md` and states the rabbit- prefix is required for check_naming. Updated every in-feature reference: `feature.json` surface/manifest entries, `specs/contract.md` `provides.agents`/`invokes.agents.subagent_type` and prose, `skills/rabbit-spec-create/SKILL.md` dispatch call `subagent_type` (v1.1.0 -> v1.1.1), and `scripts/dispatch-spec-create.py` docstring/argparse (v1.1.0 -> v1.1.1). Deployed via `publish_agent` to `.claude/agents/rabbit-spec-creator.md` and removed the stale `.claude/agents/spec-creator.md`. `test/test-agent-restriction.py` (v1.0.0 -> v1.1.0) now asserts the new source name, that the old source is gone, that the deployed copy exists under the rabbit- name with no stale deployment, and (end-to-end) that `check_naming` no longer flags spec-creator.

- **v1.5.0 (spec-path layout migration + dual-read, #399 Phase 2):** Migrated rabbit-spec's own spec/contract from `docs/spec/` to `specs/` (`git mv`; empty `docs/` removed). Added Inv 6: both spec-lifecycle skills now resolve any feature's spec-file layout INDEPENDENTLY of the mode prefix, preferring the canonical `specs/spec.md` and falling back to legacy `docs/spec/spec.md` so they keep working for features not yet migrated. `rabbit-spec-update` (v2.1.0 -> v2.2.0) gained a "Spec-file layout" subsection defining `<spec_path>`/`<contract_path>` resolution and rewired Step 1 / Step 4 to the resolved paths; `rabbit-spec-create` (v1.0.0 -> v1.1.0) gained the same layout subsection and rewired Step 3 to write to `specs/spec.md` when canonical (or the existing legacy layout, or — for a brand-new scaffold — the canonical `specs/spec.md`). Inv 4 relaxed the create-skill version pin to `1.1.0 or later`. New source-inspection test `test/test-spec-path-layout-dual-read.py` proves both SKILL.md bodies document the dual-read and asserts rabbit-spec's own `docs/` is gone. This rides the coexistence window opened by contract v2.3.0 (#399 Phase 1); Phase 3 drops the legacy fallback once every feature has migrated. Deprecation criterion for the fallback: issue #399 Phase 3 (every feature migrated to `specs/`).

## Retired invariants

(none yet)
