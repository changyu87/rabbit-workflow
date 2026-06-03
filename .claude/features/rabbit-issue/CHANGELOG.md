---
feature: rabbit-issue
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-issue feature is retired or its change history is folded into a structured schema-tracked log
---

# rabbit-issue — Changelog

## 1.2.3 — persist not-planned reason-text as the close comment (issue #476)

Fixed a bug where `item-status.py close --reason not-planned --reason-text
<text>` validated the reason-text (>= 50 chars, no banned boilerplate) and
then discarded it: the closed issue carried no justification, defeating the
audit-trail intent of #423 Part D. `cmd_close` now persists the validated
reason-text as the close comment on the same `gh issue close` call. When
`--comment` is also supplied the reason-text leads, separated from the
comment by a blank line; with only `--reason-text` the reason-text is the
comment on its own. The `completed` close path is unchanged.

Added three regression tests in `test/test-item-status.py` (using the gh
shim) asserting the reason-text reaches gh as the close comment, that
`--reason-text` precedes `--comment` when both are given, and that the
`completed` path does not inject reason-text. Documented the persistence
behaviour in `specs/spec.md`. Lockstep bump of `feature.json` / `spec.md` /
`SKILL.md` (1.2.2 → 1.2.3) and the `item-status.py` module docstring
(1.1.0 → 1.1.1).

## 1.2.2 — specs/ migration (issue #399 Phase 2)

Migrated the feature's spec surface from `docs/spec/` to the new canonical
`specs/` layout via `git mv` (`spec.md` and `contract.md`). The sibling
`docs/bugs/` directory is retained. Fixed the now-relative
`feature.json` backlink in `spec.md` (`../../feature.json` → `../feature.json`).

Made rabbit-issue's own spec-aware tooling resolve dual-read (specs/
preferred, docs/spec/ fallback): `test/test-spec-presence.py` now resolves
both spec.md and contract.md via the dual-read resolver and pins a cutover
invariant that `specs/spec.md` exists and `docs/spec/` is gone. The
`rabbit-issue` SKILL Work Protocol prose and the
`test-gh-helper-resolves-rabbit-repo.py` docstring reference were updated to
the specs/ layout.

Cleared the historical-burden tag (formerly `RABBIT-FILE-BACKLOG-16`) from
the spec body's "What this feature does NOT define" section, rephrasing to
neutral prose so the contract feature's
`test-spec-bodies-no-historical-tags.py` no longer trips on rabbit-issue.

Lockstep patch bump of `feature.json` / `spec.md` / `SKILL.md`
(1.2.1 → 1.2.2) and `contract.md` (1.1.1 → 1.1.2).

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
