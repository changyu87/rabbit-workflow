---
feature: policy
owner: rabbit-workflow team
deprecation_criterion: when the policy feature is retired (Claude Code exposes a native subagent-policy injection point) or its history is folded into a structured schema-tracked log
---

# policy — CHANGELOG

## Version notes

- **v1.11.0 (flat `docs/` layout migration, #399 Phase 2b):** Relocated the
  policy feature's documentation surfaces from the legacy spec directory to the
  flat `docs/` layout. `specs/spec.md` → `docs/spec.md` and
  `specs/contract.md` → `docs/contract.md` were moved via `git mv` (history
  preserved); the now-empty spec directory was removed. This fresh
  `docs/CHANGELOG.md` was created to hold the migration note. The spec and
  contract bodies are unchanged — only their on-disk location moved.
  Frontmatter `version` was bumped in lockstep across `feature.json`,
  `docs/spec.md`, and `docs/contract.md`. The contract resolver
  (`resolve_spec_path` / `resolve_changelog_path`) already prefers the flat
  `docs/` layout and falls back to the spec directory, so the migration is
  invisible to every cross-feature consumer. The two layout E2E tests
  (`test/test-spec-layout-migration.py`, `test/test-canonical-convention-text.py`)
  were updated to assert the flat `docs/` reality.
