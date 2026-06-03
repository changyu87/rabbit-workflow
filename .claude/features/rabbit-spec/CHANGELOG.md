---
feature: rabbit-spec
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-spec spec's invariant numbering is folded into a structured schema-tracked log
---

# rabbit-spec — Retired Invariants Log

This file holds the tombstones for invariants previously declared in the feature spec and since retired, plus version notes for notable non-retirement changes.

Each retirement entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the cascade or backlog ID that drove the retirement.

## Version notes

- **v1.5.0 (spec-path layout migration + dual-read, #399 Phase 2):** Migrated rabbit-spec's own spec/contract from `docs/spec/` to `specs/` (`git mv`; empty `docs/` removed). Added Inv 6: both spec-lifecycle skills now resolve any feature's spec-file layout INDEPENDENTLY of the mode prefix, preferring the canonical `specs/spec.md` and falling back to legacy `docs/spec/spec.md` so they keep working for features not yet migrated. `rabbit-spec-update` (v2.1.0 -> v2.2.0) gained a "Spec-file layout" subsection defining `<spec_path>`/`<contract_path>` resolution and rewired Step 1 / Step 4 to the resolved paths; `rabbit-spec-create` (v1.0.0 -> v1.1.0) gained the same layout subsection and rewired Step 3 to write to `specs/spec.md` when canonical (or the existing legacy layout, or — for a brand-new scaffold — the canonical `specs/spec.md`). Inv 4 relaxed the create-skill version pin to `1.1.0 or later`. New source-inspection test `test/test-spec-path-layout-dual-read.py` proves both SKILL.md bodies document the dual-read and asserts rabbit-spec's own `docs/` is gone. This rides the coexistence window opened by contract v2.3.0 (#399 Phase 1); Phase 3 drops the legacy fallback once every feature has migrated. Deprecation criterion for the fallback: issue #399 Phase 3 (every feature migrated to `specs/`).

## Retired invariants

(none yet)
