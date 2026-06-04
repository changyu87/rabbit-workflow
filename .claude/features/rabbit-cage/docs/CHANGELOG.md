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

- **v5.59.0 (re-home bypass-permissions per-feature alert + drop rabbit-config from install.py (retire-rabbit-config step 1)):**
  Re-homed the bypass-permissions active-override alert as a PER-FEATURE
  `runtime[]` entry: rabbit-cage now declares
  `{"api": "emit_configurable_alert", "args": {"feature_name": "rabbit-cage",
  "configurable_id": "bypass-permissions"}}` in both `runtime.Stop` and
  `runtime.SessionStart`. The entry fires the inlined-revoke alert
  (`/rabbit-cage-config bypass-permissions false`) when
  `permissions.defaultMode == "bypassPermissions"` is active, re-homing what
  the central `iterate_configurables_*` alert path provided (step 1 of #769 /
  retire-rabbit-config; enum admitted by #773, polarity fixed by #775). Removed
  rabbit-config from `install.py`: the `FEATURE_INCLUDES["rabbit-config"]` entry
  and the `SAME_PATH_FILES` rabbit-config skill-copy tuple. During coexistence
  the central alert may briefly co-exist; the per-feature entry is authoritative
  (#781 removes the central path). The deployed root `install.py` is republished
  so the Inv 22h self-update byte comparison stays in sync. Closes #780.

- **v5.58.1 (include rabbit-feature rabbit-tdd-autonomous command in install closure (fix #767 manifest gap)):**
  Added `commands/rabbit-tdd-autonomous.md` to `install.py`'s
  `FEATURE_INCLUDES["rabbit-feature"]` so the command declared by
  rabbit-feature's `feature.json` manifest (added in #767) is shipped by the
  installer. Closes the rabbit-cage-suite `test-feature-includes-manifest-closure.py`
  gap (#777). The deployed root `install.py` is republished from this source so
  the Inv 22h self-update byte comparison stays in sync (the source/deployed
  drift was the sole cause of the self-update e2e breakage; no COMMANDS-map or
  re-exec-fixture change was needed).

- **v5.58.0 (migrate rabbit-cage config refs to /rabbit-cage-config; phase 4 of #733):**
  Migrated rabbit-cage's user-facing config reference sites from the central
  `/rabbit-config <sub>` command to its own per-feature `/rabbit-cage-config <sub>`
  command (#767/#768): the `scope-guard.py` default-deny SESSION OVERRIDE revoke
  hint, the three `feature.json` runtime alert texts (the two `.rabbit-scope-override`
  `check_marker_alert` entries and the `bypass-permissions` `alert-message`), the
  `README.md` command catalog rows for the five owned configurables, and the
  `docs/spec.md` Inv 7 revoke-hint prose. Coexistence is preserved: the central
  `/rabbit-config <sub>` surface still mutates the same configurables (retired
  separately by #769). The `test-scope-guard-revoke-uses-rabbit-config.py`
  deny-message + banner expectations and the `bypass-permissions` alert-text
  expectation were updated in lockstep; the coexistence E2E assertions (the
  rabbit-config interpreter still dispatches the command) are left intact.
  Deployed byte-copies (`.claude/hooks/scope-guard.py`, root `README.md`)
  republished from source via the contract publish API.

- **v5.57.0 (relocate tdd-autonomous out of rabbit-cage; phase 3 of #733):**
  Removed the `tdd-autonomous` configurable from rabbit-cage's
  `feature.json configuration[]`. It gates the TDD feature-touch Step-4 cycle
  (consumers: `tdd-subagent/dispatch-tdd-subagent.py` + the
  `rabbit-feature-touch` SKILL), NOT any rabbit-cage behavior — it is mis-homed
  here (added under the `human-approval` name by an earlier feature, renamed by
  #336) and is being re-declared in its owning TDD feature (rabbit-feature) in
  the SAME PR. A configurable declared in two features' `configuration[]` would
  be ambiguous, so it MUST NOT remain in rabbit-cage once relocated. Dropped
  the now-stale `.rabbit-human-approval-bypass` entry from contract.md
  `reads.files` (rabbit-cage no longer reads that marker for an alert — only a
  scope-guard sibling-path comment references the name). The on-disk marker
  `.rabbit-human-approval-bypass` itself is UNAFFECTED: the auto-evolve loop
  mutates it via `set-evolve-mode.py` / `contract.lib.mutation` directly, not
  via this `configuration[]` entry, so loop activation is undisturbed (and the
  marker stays in `.gitignore` per Inv 9). The five genuinely-owned
  configurables (`scope-guard`, `bypass-permissions`, `allowed-tools`,
  `bash-allow`, `prompt-threshold`) and `/rabbit-cage-config` are untouched.
  Removed the #336 test `test-tdd-autonomous-configurable.py`; added
  `test-tdd-autonomous-relocated-out.py` pinning the removal + the five owned
  configurables staying. Doc references to `/rabbit-config tdd-autonomous` are
  migrated to the new owning-feature command in #768.

- **v5.56.0 (per-feature config command + alerts via shared helper; phase 3 of #733):**
  rabbit-cage manifests its five genuinely-owned configurables (`scope-guard`,
  `bypass-permissions`, `allowed-tools`, `bash-allow`, `prompt-threshold`) as a
  single grouped per-feature config command `/rabbit-cage-config`, additively
  alongside the still-live `/rabbit-config <sub>` central surface (coexistence —
  both work; rabbit-config retired separately in phase 4 / #769). New artifacts:
  `commands/rabbit-cage-config.md` (deployed via `publish_command`) and its
  backing `scripts/rabbit-cage-config.py`, a THIN wrapper that reads rabbit-cage's
  own `configuration[]` entry and delegates validation + mutation +
  restart-prompt rendering to `contract.lib.config_dispatch.dispatch_config`
  (no re-implemented interpreter; script > prompt). The five owned configurables
  gain the optional `command` field (`configuration.schema.json` 1.1.0); the
  `tdd-autonomous` configurable is left untouched (it is the TDD feature's
  surface). Per-feature override alerts: rabbit-cage's `scope-guard` override
  already surfaces via its OWN dedicated `check_marker_alert` entries (Inv 7 /
  Inv 16) — per-feature alert ownership in place. Re-homing the json-key-storage
  `bypass-permissions` alert needs `contract.lib.runtime.emit_configurable_alert`
  admitted into the `runtime.schema.json` API enum (the function + its contract
  test already exist; only the enum entry is missing — outside rabbit-cage's
  bounded scope), so it is DEFERRED as a phase-3 cross-feature follow-up for
  `contract` (#768); bypass-permissions' alert continues to surface via
  rabbit-config's central `iterate_configurables_*` meanwhile (coexistence).
  install.py's `COMMANDS` / `FEATURE_INCLUDES["rabbit-cage"]`
  gain the command + script, and `FEATURE_INCLUDES["contract"]` gains
  `lib/config_dispatch.py` (the cross-feature dependency the command shells
  into). New invariant Inv 40.

- **v5.55.0 (rename CONFIGURATION `human-approval` -> `tdd-autonomous` + polarity flip; #336 / phase 2 of #733):**
  BREAKING rename of rabbit-cage's TDD-gating configurable. The `subcommand`
  `human-approval` becomes `tdd-autonomous`, and the boolean polarity is
  FLIPPED to match the CLI positive-streamlined naming rule (contract Inv 12):

  | old | new | meaning |
  | --- | --- | --- |
  | `human-approval true` (default, gate active) | `tdd-autonomous false` (default, gate active) | Step 4 prompts for approval each cycle. |
  | `human-approval false` (bypass active) | `tdd-autonomous true` (bypass active) | Step 4 is skipped; cycle runs autonomously. |

  The default (`tdd-autonomous false`) keeps the TDD Step-4 human-approval
  gate ACTIVE, identical to the prior default (`human-approval true`). The
  `alert-on` value flips from `false` to `true` (bypass is now the positive
  state), and `alert-message.text` is amended to
  "TDD-AUTONOMOUS MODE ACTIVE — TDD cycle Step 4 (human approval) skipped".
  The on-disk marker path (`.rabbit-human-approval-bypass`) is UNCHANGED —
  marker dual-read coexistence already landed in #766, so the running
  auto-evolve loop's preconditions are not disturbed. Cross-feature doc
  references to `/rabbit-config human-approval` (rabbit-feature-touch SKILL,
  tdd-subagent, scope-guard deny prose) are intentionally left for phase 3
  (#768); this touch is bounded to rabbit-cage. rabbit-config (the mutation
  surface) is retired separately in phase 4 (#769).

- **v5.54.0 (reflow invariants to contiguous 1..N + opt into contiguous_invariants; #737):**
  rabbit-cage's `## Invariants` numbering had two holes (24 and 26) left by
  retired invariants. Ran the deterministic `contract/scripts/reflow-invariants.py`
  on this feature to renumber to contiguous 1..39 and atomically rewrite every
  live `Inv N` cross-reference WITHIN rabbit-cage (spec.md, contract.md, hooks/,
  scripts/, install.py, test/). Invariants 1..23 are unchanged; 24 and 26 were
  the gaps. Then set `"contiguous_invariants": true` in `feature.json` to opt
  into contract's strict CONTIGUOUS tier (contract Inv 30), so future holes are
  caught by `contract/test/run.py`. No cross-feature `Inv N` references to
  rabbit-cage's renumbered invariants exist (verified by repo-wide grep), so no
  cross-feature edit was needed. `docs/CHANGELOG.md` tombstones are point-in-time
  history and were not renumbered (the reflow tool never touches CHANGELOG).
  Old -> new invariant mapping (invariants not listed are unchanged):

  | old | new |
  | --- | --- |
  | 25  | 24  |
  | 27  | 25  |
  | 28  | 26  |
  | 29  | 27  |
  | 30  | 28  |
  | 31  | 29  |
  | 32  | 30  |
  | 33  | 31  |
  | 34  | 32  |
  | 35  | 33  |
  | 36  | 34  |
  | 37  | 35  |
  | 38  | 36  |
  | 39  | 37  |
  | 40  | 38  |
  | 41  | 39  |

- **v5.53.0 (scope-override revoke uses /rabbit-config command, not raw script path; #709):**
  The scope-guard override REVOKE instruction now surfaces the clean
  `/rabbit-config scope-guard on` command form that sibling configurables
  use, instead of the raw `.claude/features/rabbit-cage/scripts/scope-guard-on.py`
  path. Changes: (1) `feature.json configuration` gains a `scope-guard`
  configurable (subcommand `scope-guard`, value `on` → `delete_marker` on
  `.rabbit-scope-override`), so the existing data-driven rabbit-config
  interpreter dispatches `/rabbit-config scope-guard on` with no rabbit-config
  edit; (2) the scope-guard.py default-deny SESSION OVERRIDE option now reads
  "Revoke any time via `/rabbit-config scope-guard on`"; (3) the
  active-override banner (`.rabbit-scope-override` `check_marker_alert` Stop +
  SessionStart entries) inlines the same revoke hint. `scope-guard-on.py`
  remains the implementation the command wraps (script-tier preserved); only
  the user-facing instruction changed. Spec Inv 7 amended to document the
  `scope-guard` configurable and the command-form revoke instruction.
  Regression: `test/test-scope-guard-revoke-uses-rabbit-config.py` (deny
  message + banner text + configurable declaration + E2E command deletes the
  override marker).

- **v5.52.1 (housekeeping round 2 — measured dead-prose removal in spec; #682):**
  Measured line-removal pass under the #639 prove-it-dead-or-flag methodology
  (parent #677, round 2 re-run; round 1 only reworded). `docs/spec.md`:
  518 -> 497 lines (-21). Removed/collapsed, each verified by a deterministic
  check before deletion:
  (1) Inv 27 historical narration "Before this invariant was added, scope-guard
  wrote at <git_toplevel>..." — past-defect storytelling; the CURRENT
  single-canonical-location invariant is stated immediately above (CHANGELOG
  material).
  (2) Inv 40 "the prior `_BOX_WIDTH - 2 = 30` char-column math under-counted"
  plus the "Two defects in the earlier version-box form / Defect 1 / Defect 2"
  framing — past-fix narration; the CURRENT math (inner field 2*_BOX_WIDTH-4=60)
  is fully specified.
  (3) Inv 22h "a confusing and load-bearing two-run requirement that produces
  spurious 'missing feature' failures" — rationale narration of a defect the
  MUST already prevents.
  (4) Inv 29d "Rationale — REJECTED alternative: dynamic ... Same rejection as
  Inv 28" — verbatim duplicate of the GitHub-API rejection already in Inv 28;
  collapsed to a one-line back-reference (rule #3 collapse-redundancy).
  (5) Inv 29a csh/tcsh rationale paragraph — the shell-agnostic behavior is
  stated; the justification was redundant.
  (6) Three-layout dual-read carve-out (scope-guard Semantics prose section +
  Inv 17(a2)) — restated in full in three places; the carve-out is the
  AUTHORITATIVE subject of Inv 35, so the prose section and Inv 17(a2) now
  point at Inv 35 (rule #3).
  (7) Inv 30 "Initial seed: CHANGELOG.md carries ... release/1.0 through
  release/1.10 reconstructed from the git log" — one-time historical seeding
  narration; not load-bearing (test-changelog-shape.py validates shape, not
  the seed content).
  Verbose per-test "(i)/(ii)/(iii)" enumerations in several "Enforced by"
  blocks collapsed to one-line summaries (the test docstrings own the detail).
  No deployed artifact changed; rabbit-cage owns no SKILL.md. New e2e
  regression `test/test-spec-housekeeping-682-dead-prose-removed.py` pins the
  banned phrases absent, the dual-read collapse, and a 500-line spec ceiling;
  wired into `test/run.py`. Doc-only; contract suite GREEN.

- **v5.52.0 (retire dead `permissions` lock/unlock configurable; #366):**
  Removed the `permissions` configurable (`subcommand: "permissions"`,
  actions `lock`/`unlock`) from `feature.json` `configuration[]` and deleted
  its backing `scripts/repo-permissions.py` — a post-clone chmod drift guard
  over `archive/` + `test/` that was never invoked in practice (no hook,
  script, or workflow ever called it). Designed Deprecation: the dead artifact
  is removed rather than carried forward. Deleted the unit suite
  `test/test-repo-permissions.py` and unwired it from `test/run.py`; added
  `test/test-repo-permissions-retired.py` (e2e) asserting the script is absent,
  the suite is unwired, and no `configuration[]` entry references
  `scripts/repo-permissions.py`. Dropped the `repo-permissions.py` row from
  `docs/contract.md` `provides.scripts`. NOTE: this is the dead repo-permissions
  `permissions` configurable ONLY — the ACTIVE `bypass-permissions` configurable
  (backed by `permissions.defaultMode`) is untouched and load-bearing. Part A
  of the #366 two-feature barrier; the rabbit-config SKILL CLI-table row is
  retired separately in Part B.

- **v5.51.0 (file-scoped scope-guard override; #649):** Added a least-privilege
  variant to the `.rabbit-scope-override` marker. `_consume_override()` in
  `hooks/scope-guard.py` now recognizes a third content form
  `one-time:<repo-relative-path>` alongside `session` and bare `one-time`: it
  authorizes a SINGLE write to exactly the declared path (resolved against
  `REPO_ROOT`) and then consumes the marker with the same delete-marker +
  create-`.rabbit-scope-override-used` semantics as bare `one-time`; a write to
  any OTHER path does not match, leaving the override un-consumed so it never
  widens beyond its declared path. `_consume_override()` now takes the candidate
  absolute target path; the two call sites in `decide()` pass `abs_path`. Bare
  `session` and bare `one-time` are unchanged (backward compatible); the
  file-scoped form is documented as PREFERRED when the target path is known.
  New invariant Inv 41 in rabbit-cage's own namespace; enforced by new e2e
  `test/test-scope-guard-file-scoped-override.py` (allow-to-declared-path +
  consume; deny-other-path + retain; deny-after-consume; session/one-time
  regression), wired into `test/run.py`. `hooks/scope-guard.py` is a deployed
  hook (`publish_hook`) — its `.claude/hooks/` copy drifts until republished.

- **v5.50.0 (housekeeping Phase 2 — history-free doc surfaces; strict-tier opt-in, #549):**
  Opted rabbit-cage into the strict housekeeping tier by setting top-level
  `"housekeeping_clean": true` in `feature.json`, then scrubbed all
  historical-burden tags from `docs/spec.md` and `docs/contract.md` so the
  surfaces describe the CURRENT design only (Inv 49 strict tier). No invariant
  was retired, removed, or renumbered — only historical framing was stripped;
  the substantive behaviour of every invariant is preserved verbatim. The
  stripped references, recorded here for provenance:
  - Load-bearing `feature.json status == "retired"` enum references (Dispatcher
    Behavior step 1, `run_publish_loop`, Inv 2, and the install-closure
    exclusion of tdd-state-machine) were rephrased to cite the contract status
    enum / retirement semantics (contract Inv 36) instead of restating the
    tombstone word — mirroring the rabbit-feature (#555) / rabbit-config (#634)
    precedent, keeping the change single-feature.
  - Inv 14's "stale `@`-import to a retired source" → "to a removed source"
    (here "retired" meant a deleted file, not the status enum).
  - Bare issue/PR refs stripped from prose and invariant titles:
    Inv 22 ("the flag was retired per #273"), Inv 22h (#297), Inv 28 (#307),
    Inv 29a (bug #287), Inv 29 (#499/#508), Inv 30 (example `#318` → `#N`;
    "this PR" + `#281`–`#318` seed narrative reworded present-tense),
    Inv 33 (#413), Inv 34 (#503 title + "pre-#503"), Inv 36 (#449 title +
    "#326 form"), Inv 37 (#493), Inv 38 (#492), Inv 39 (#545 title + "#503"
    cross-refs + "pre-#545"), Inv 40 (#629 title + "#326/#449 form").
  CHANGELOG.md is exempt from the strict scan (history lives here), so the
  issue numbers above are retained for traceability. Doc surfaces only:
  no behaviour, hook, command, or script changed; no republish needed.

- **v5.49.0 (version-box release source + emoji alignment fix, #629):** Added
  Inv 40 — the SessionStart version box (Inv 36) now shows the rabbit RELEASE
  version (the git tag cut by release-bump.py, e.g. `v1.11.0`) rather than
  rabbit-cage's per-feature `feature.json` `version` (the spec version, e.g.
  `5.49.0`). `_read_installed_version` reads `<install_root>/.version` in
  plugin mode (unchanged), derives the latest tag via `git describe --tags
  --abbrev=0` in standalone/dev mode, and falls back to `"unknown"` when
  neither is resolvable (graceful: missing git / non-repo / tag-free repo
  never raises) — replacing the old feature.json fallback (Defect 1). SEPARATELY,
  `_version_box` now centers the version row across `2*_BOX_WIDTH - 4` DISPLAY
  columns (was `_BOX_WIDTH - 2` character columns) so the closing 🐇 lands on
  the 32-emoji border instead of drifting off it, on the emoji=2-columns common
  case (Defect 2). Documented assumption: perfect emoji alignment is
  terminal-dependent; the fix targets the common 2-column rendering, the same
  width model the borders already assume. `hooks/session-start-dispatcher.py`
  is a deployed hook (`publish_hook`); its deployed `.claude/hooks/` copy drifts
  until republished. Enforced by `test/test-session-start-version-line.py`
  (version source: plugin / standalone-no-tag → unknown / standalone-with-tag →
  tag) and `test/test-runtime-banner-shape.py` (version row display width equals
  border display width). No invariants retired or renumbered.

- **v5.48.0 (advisory-restart surfacing in Stop + SessionStart, #545 part B):**
  Added Inv 39 — the Stop and SessionStart dispatchers surface
  rabbit-auto-evolve's ADVISORY-restart signal (a restart that WOULD unlock a
  capability but NEVER pauses or auto-resumes the loop) by INVOKING
  rabbit-auto-evolve's `scripts/advise-restart.py` (a cross-scope INVOKE
  declared in `contract.md` `invokes.scripts`, like the existing #503
  check-auto-resume invoke). Stop emits one concise advisory line per tick-end
  (`🔄 restart ADVISED (not required): <reason> — loop continues meanwhile`)
  while the advisory marker is present and does NOT clear it; SessionStart
  surfaces the same line in its banner AND clears the marker (invokes
  `advise-restart.py clear`) since the advised restart has occurred. The
  advisory icon/wording is deliberately distinct from the hard #503
  auto-resume banner (`Auto-resuming rabbit-auto-evolve loop`) so it reads as
  OPTIONAL. Graceful degradation mirrors #503: an absent/non-zero/timed-out/
  unparseable `advise-restart.py` surfaces no line, never crashes, never
  clears, and the dispatchers continue normally. Gated by the new e2e test
  `test-advisory-restart-surfaced.py`. Both `hooks/stop-dispatcher.py` and
  `hooks/session-start-dispatcher.py` are deployed (`publish_hook`); their
  `.claude/hooks/` copies drift until republished.
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
