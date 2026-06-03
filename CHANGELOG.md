# Changelog

All notable changes to the rabbit workflow are documented here. Format adapted from [keep-a-changelog.com](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Changed
- Phase 2 of #399 (rabbit-cage) — migrated `rabbit-cage`'s `docs/spec/` -> `specs/` (spec.md + contract.md moved via `git mv`; empty `docs/` removed). `scope-guard.py`'s spec.md path-pattern carve-out (standalone Inv 5 + plugin Inv 17(a2)) now dual-reads BOTH `specs/spec.md` (new) and `docs/spec/spec.md` (legacy) for every feature, mirroring contract's `resolve_spec_path` (#451), so mid-migration features still match during the coexistence window. `workspace-tree.py` recognizes `specs/` (annotation + key-file detection + structural dir). `rabbit-cage` bumped 5.35.0 -> 5.36.0. New e2e `test/test-scope-guard-specs-dir-dual-read.py` pins both layouts ALLOW in both modes and the narrow non-`spec.md` DENY. Do not close #399 (Phase 3 drops the legacy fallback after all features migrate).

### Removed
- Closes #391 — Skill-path PreToolUse prompt injection retired. `contract` bumped to v2.0.0; `hooks/prompt-injector.py` source + deployed copy removed; the `publish_hook` manifest entry and the two `runtime.Stop` entries (`check_prompt_injection_failures`, `cleanup_old_prompts`) removed from contract's `feature.json`; the `.claude/settings.json` PreToolUse entry registering `prompt-injector.py` removed (`scope-guard.py` unaffected). Nine `prompts[]` entries with `kind: "skill"` removed across rabbit-feature, rabbit-spec, rabbit-config, rabbit-issue, rabbit-auto-evolve, rabbit-decompose; nine corresponding skill-passthrough templates deleted from `.claude/features/contract/templates/prompts/`. The mechanical RABBIT-POLICY-BLOCK-v1 sentinel-validation contract owned by `scope-guard.py` (Inv 66, PR #390/#394) supersedes the Skill-path injection mechanism. Inv 55 and Inv 56 tombstoned in `.claude/features/contract/CHANGELOG.md`; Inv 57 shrunk from ten templates to two (`tdd-subagent.txt`, `spec-create.txt`).

## [release/1.12.0] - 2026-06-02
### Added
- Closes #221 — `dispatch-tdd-subagent.py` accepts new `--affected-invariants N[,N,...]` flag for scoped spec embedding (~38% prompt-size reduction on rabbit-cage)
### Changed
- install.sh + install.py defaults: release/1.11.0 -> release/1.12.0 (minor bump for the new flag)

## [release/1.11.0] - 2026-06-02
### Added
- Closes #307 — 3-field semantic versioning adopted for release branches; legacy 2-field branches retained for backwards compat; bump-tier guidance documented in Inv 28
### Changed
- install.sh + install.py defaults: release/1.10 -> release/1.11.0 (first 3-field release)

## [release/1.10] - 2026-06-02
### Fixed
- Fixes #318 — bypass-permissions config now emits one-shot 'restart Claude' prompt after mutation
### Added
- CHANGELOG.md at repo root (this file; #292) with maintenance protocol per rabbit-cage Inv 30

## [release/1.9] - 2026-06-02
### Fixed
- Fixes #313 — dispatch-tdd-subagent.py no longer emits doubled .rabbit/.rabbit/ paths; new {{tdd_report_path}} slot computed per mode at assembly time

## [release/1.8] - 2026-06-02
### Fixed
- Fixes #311 — find-feature.py rogue-inner-.rabbit/ precedence + validation (canonical RABBIT_ROOT-as-repo first; require <rabbit_root>/.claude/ to validate)
- Contract test placeholder sets updated for scope_marker_path slot

## [release/1.7] - 2026-06-02
### Fixed
- Fixes #304 — dispatch-tdd-subagent.py LOCK/UNLOCK scope-marker path is now mode-aware (standalone vs plugin) via new {{scope_marker_path}} slot
- Fixes #303 — corrected three stale '7-step TDD cycle' docs strings to '8-step' (cycle has been 8-step since SYNC-DEPLOYED per #274)

## [release/1.6] - 2026-06-02
### Fixed
- Fixes #297 — install.py --update self re-execs into freshly-copied install.py before the FEATURE_INCLUDES loop, so new closure entries land in a single --update run (no more confusing two-run requirement)

## [release/1.5] - 2026-06-02
### Fixed
- Fixes #300 — find-feature.py dual-detect plugin mode (host_root or rabbit_root --repo arg both work)
- Fixes #301 — dispatch-tdd-subagent.py prefers RABBIT_ROOT env var for repo resolution
- Fixes #302 — root-cause fix (dual-root ambiguity removed)
- Inv 28/29 source-order fix (monotonic)

## [release/1.4] - 2026-06-01
### Fixed
- Fixes #286 — install.py --update hardcoded default is now a stable release ref (not 'dev')
- Fixes #287 — install.py --update accepts --version/--ref/--channel CLI flags (csh/tcsh compatible)

## [release/1.3] - 2026-06-01
### Fixed
- Fixes #284 — rabbit-feature-touch Step 3 spec-commit is now mode-aware (plugin: git add -f for .rabbit/ paths)

## [release/1.2] - 2026-06-01
### Fixed
- Fixes #285 — tdd-subagent feature now ships in plugin-mode install (install.py FEATURE_INCLUDES + AGENTS + contract prompt-template closure)
- Fixes #281 — plugin-mode session-override marker path-equality across five consumers; SCOPE GUARD OFF banner now fires at SessionStart
- Fixes #282 — resolve-scope.py and format-feature-context.py ship in install closure; find-feature.py scans .rabbit/rabbit-project/features/ in plugin
- Fixes #283 — rabbit-spec-update dual-mode feature_root resolution

## [release/1.1] - 2026-06-01
### Added
- rabbit-config skill mutation surface
- install.py --update self-fetch + plugin-install settings.json rewrite

## [release/1.0] - 2026-06-01
### Added
- Initial rabbit workflow: rabbit-cage dispatcher hooks, rabbit-feature touch orchestration, rabbit-spec lifecycle skills, tdd-subagent state machine, rabbit-issue GitHub Issues wrapper
