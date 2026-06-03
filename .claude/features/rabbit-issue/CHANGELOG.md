---
feature: rabbit-issue
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-issue feature is retired or its change history is folded into a structured schema-tracked log
---

# rabbit-issue — Changelog

## 1.2.1 — Owner sweep (issue #416)

Changed the feature owner from the individual `cyxu` to the team identity
`rabbit-workflow team` in every owner-bearing location within the feature:
`feature.json` owner, `docs/spec/spec.md` and `docs/spec/contract.md`
frontmatter, `skills/rabbit-issue/SKILL.md` frontmatter, every runtime-script
module docstring (`scripts/_gh.py`, `scripts/file-item.py`,
`scripts/item-status.py`, `scripts/list-items.py`), and the test-helper /
test-module owner markers (`test/gh_shim.sh`, `test/test-manifest-shape.py`,
`test/test-skill-presence.py`, `test/test-spec-presence.py`). No owner field,
frontmatter, or docstring in the feature names an individual any longer.

Added `test/test-owner-sweep.py` to pin the invariant that the feature owner
is `rabbit-workflow team` and that no owner marker re-introduces an individual
login. Lockstep patch bump of `feature.json` / `spec.md` / `SKILL.md`
(1.2.0 → 1.2.1) and `contract.md` (1.1.0 → 1.1.1).
