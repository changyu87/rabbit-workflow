---
feature: rabbit-cage
owner: rabbit-workflow team
deprecation_criterion: when rabbit-cage's spec version history is folded into a structured schema-tracked log
---

# rabbit-cage — Changelog

Version-keyed change log for the rabbit-cage feature. The version here tracks
the spec version declared in `docs/spec.md` frontmatter and the `version`
field in `feature.json` (lockstep).

## Version notes

- **v5.47.0 (command frontmatter compliance, #492):** Added Inv 38 — every
  command deployed via `publish_command` MUST carry full frontmatter
  (`name`, `description`, `version`, `owner`, `deprecation_criterion`,
  `template_version`; owner exactly `rabbit-workflow team`) per spec-rules.md
  "Skills and commands" + `contract/templates/command-template.md`. Fixed the
  three violators: `commands/rabbit-project.md` had NO frontmatter (rendered
  blank in the slash-command menu); `commands/rabbit-refresh.md` was missing
  `name`/`version`/`owner`/`deprecation_criterion`/`template_version`;
  `commands/rabbit-update.md` was missing `name`/`template_version`. Gated by
  the new e2e test `test-command-frontmatter-compliance.py`, which enumerates
  every `publish_command` source from the manifest (closure) and asserts the
  full key set + owner on each. All three command files are deployed
  artifacts (`publish_command`); their deployed `.claude/commands/` copies
  drift until republished.
- **v5.46.0 (FEATURE_INCLUDES closure — ship contract/check-release-update.py, #605):**
  Added `scripts/check-release-update.py` to `FEATURE_INCLUDES["contract"]` in
  install.py. The probe is subprocessed at runtime by contract's
  `check_release_update` SessionStart API and the `/rabbit-update check`
  command, but was absent from the packaging closure, so a plugin install
  omitted it and the release check failed. Same class as #570
  (rabbit-feature/audit-owner.py). Pinned by a targeted assertion in
  `test-install-py-exports.py` plus a new e2e test
  `test-install-deploys-check-release-update.py` that runs the real installer
  and asserts the probe lands in the deployed target. install.py is a deployed
  artifact (publish_file), so this republishes on next install.
- **v5.45.0 (FEATURE_INCLUDES closure — ship rabbit-feature/audit-owner.py, #570):**
  Added `scripts/audit-owner.py` to `FEATURE_INCLUDES["rabbit-feature"]` in
  install.py. The script is referenced by `rabbit-feature-audit/SKILL.md` but
  was absent from the packaging closure, so a plugin install omitted it and
  `test-feature-includes-scripts-closure.py` (t10) failed. The targeted
  assertion in `test-install-py-exports.py` now pins the entry. install.py is a
  deployed artifact (publish_file), so this republishes on next install.
- **v5.44.0 (/rabbit-update command — check + install, #493):** Added the
  user-invocable `/rabbit-update` slash command, deployed via `publish_command`
  from `commands/rabbit-update.md` (mirroring rabbit-refresh / rabbit-project).
  Per `script > CLI > spec > prompt`, the command is a thin router to the new
  deterministic companion script `scripts/rabbit-update.py` with two
  subcommands: `check` (non-mutating, non-throttled current-vs-latest probe
  that REUSES contract's `check-release-update.py` fetch/compare helpers and
  emits structured `{current, latest, newer, self_update_available}` JSON) and
  `install` (invokes the existing `install.py --update` self-update path). No
  release-check logic is duplicated; no AI skill is introduced. Registered in
  `feature.json manifest`, added to `install.py`'s `COMMANDS` +
  `FEATURE_INCLUDES["rabbit-cage"]` (the command + the backing script) per
  Inv 21 / Inv 25. Spec Inv 37 added; no invariants retired or renumbered. The
  new command is a deployed artifact (`publish_command`) — its deployed copy
  under `.claude/commands/rabbit-update.md` drifts until republished. Covered
  by the new e2e `test/test-rabbit-update-command.py`, wired into
  `test/run.py`.

- **v5.43.0 (install.py maps renamed rabbit-spec-creator agent, #477):**
  `install.py` deployed the rabbit-spec drafting agent from the OLD path
  `spec-creator.md`, but issues #471/#473 renamed the source to
  `rabbit-spec-creator.md`. Both references are corrected to the new
  filename: the `AGENTS` deploy tuple now maps
  `.claude/features/rabbit-spec/agents/rabbit-spec-creator.md` ->
  `.claude/agents/rabbit-spec-creator.md`, and the
  `FEATURE_INCLUDES["rabbit-spec"]` entry is now
  `agents/rabbit-spec-creator.md`. On a fresh install or `--update` the
  installer no longer redeploys the non-existent old file or skips the new
  one. The feature-dir key (`rabbit-spec`) and the dispatch script entry
  (`scripts/dispatch-spec-create.py`) are unchanged. Pinned by the new e2e
  test `test/test-install-agent-path-rabbit-spec-creator.py`. install.py is
  a deployed artifact (publish_file) — republish needed. Same pattern as
  the #470 tdd-subagent fix.

- **v5.42.0 (3-row rabbit-box SessionStart banner, #449):** Redesigned the
  SessionStart welcome banner emitted by `hooks/session-start-dispatcher.py`.
  The single compact `[rabbit] 🐇 rabbit v<version>` line is replaced by a
  three-row rabbit box around the centered version: a top border of 32 🐇, a
  middle row `🐇 rabbit v<version> 🐇` with the version centered in the
  32-wide box, and a bottom border of 32 🐇 — each row carrying the brand
  prefix via the dispatcher's subline renderer. The box is built by the new
  `_version_box(root)` helper (module constants `_BOX_WIDTH = 32`,
  `_BOX_RABBIT`) and inserted ahead of all other SessionStart payloads.
  Separately, the welcome line `Welcome — governing policies loaded` is now
  rendered PLAIN (brand prefix only — no ✅ icon, no ━━━ bars): the new
  `_strip_welcome_decoration(payloads)` helper converts contract's
  `welcome_with_policy` `banner` payload to a `subline` in place, leaving the
  three policy summary sublines (philosophy/spec-rules/coding-rules)
  untouched. Version sourcing (`.version` plugin, `feature.json` standalone)
  is unchanged. Spec Inv 36 added; no invariants retired or renumbered.
  `hooks/session-start-dispatcher.py` is a `publish_hook` deployed hook — its
  deployed copy under `.claude/hooks/` drifts until republished. Covered by
  the new e2e `test/test-runtime-banner-shape.py` (box shape, centered
  version, plain welcome line, policy sublines intact, box-before-welcome
  ordering), wired into `test/run.py`; the prior `#326` ordering test
  (`test/test-session-start-version-line.py`) stays green.
- **v5.41.0 (flat docs/ layout, #399 Phase 2b):** Migrated the feature's spec
  artifacts from `specs/` to the flat `docs/` layout
  (`git mv specs/spec.md docs/spec.md`, `git mv specs/contract.md
  docs/contract.md`, removed the now-empty `specs/`). rabbit-cage carries no
  `docs/bugs/` subtree, so none is created. This rides on the contract
  feature's dual-read (`resolve_spec_path` / `resolve_changelog_path`), which
  prefers the flat `docs/` layout and falls back to `specs/`, so the move
  keeps the feature green. Spec/contract content is unchanged (location only,
  plus the lockstep version bump). The deployed hooks under `hooks/` are
  untouched — a doc move relocates only the doc artifacts the resolver already
  prefers, so no manifest republish is needed. New `docs/CHANGELOG.md` (this
  file) records the migration. The E2E regression test
  `test/test-specs-layout.py` pins the flat layout and asserts the contract
  resolver targets `docs/` for both the spec/contract pair and the changelog.
  Deprecation of the upstream `specs/` fallback is owned by issue #399 Phase 3.

- **v5.40.0 and earlier:** Pre-migration history tracked the `specs/` layout
  spec/contract frontmatter and `feature.json` version (lockstep).
