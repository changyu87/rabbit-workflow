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

- **v5.83.0 (fix #1046: canonical single-`.rabbit` runtime-root resolver):** in vendored mode the session cwd IS the `.rabbit` install dir and `RABBIT_ROOT` points at it, so runtime-artifact writers that anchored a cwd-relative `.rabbit/` literal doubled the segment to `<host>/.rabbit/.rabbit/...` — splitting the mode marker and the doubled artifacts (`last-update-check`, assembled prompts, `impl-suggestion-*.json`) across two trees so readers and writers disagreed. New Inv 52 promotes the basename-`.rabbit` decision (previously inlined in the SessionStart mode-marker reconciliation, Inv 44) into a single owned library function `lib/runtime_root.rabbit_runtime_root(repo_root)`: it returns `repo_root` unchanged when it is already a `.rabbit` dir and `<repo_root>/.rabbit` otherwise, is pure/idempotent, and is now imported by `hooks/session-start-dispatcher.py`'s `_reconcile_mode_marker`. The cross-feature cwd-relative writers (contract's `check-release-update.py`, tdd-subagent's `dispatch-tdd-subagent.py`, rabbit-spec's `dispatch-spec-creator.py`) remain out of rabbit-cage scope and are filed as follow-ups to adopt the resolver. New e2e test `test-runtime-root-resolver.py`. Feature/spec/contract versions bumped 5.82.0 -> 5.83.0 in lockstep (Inv 11).

- **v5.82.0 (fix #1035: broaden Inv 24 script-closure to cover COMMAND-referenced scripts):** `install.py`'s `FEATURE_INCLUDES` omitted `scripts/rabbit-tdd-autonomous-config.py` for `rabbit-feature`, so the shipped `/rabbit-tdd-autonomous` command (deployed via `commands/rabbit-tdd-autonomous.md`) hit `FileNotFoundError` in a vendored install. The existing closure tests scanned only SKILL.md bodies, so the command-backed omission was silent. Inv 24 is broadened from "skill-referenced" to "deployed-surface-referenced": the source set is now the union of shipped SKILL.md and shipped command `.md` bodies (the `COMMANDS` list plus any `commands/*.md` entry in `FEATURE_INCLUDES`). Both `test-feature-includes-scripts-closure.py` (static) and `test-install-ships-skill-referenced-scripts.py` (e2e) now scan command bodies. The broadened tests caught FOUR genuine omissions of the same class — `rabbit-tdd-autonomous-config.py` (rabbit-feature) and the three `/rabbit-project` backing scripts (`rabbit-project.py`, `rabbit-project-set-path.py`, `rabbit-project-map.py`, rabbit-cage) — all four added to the closure. Feature/spec/contract versions bumped 5.81.0 -> 5.82.0 in lockstep (Inv 11).

- **v5.80.0 (feat #1001: dual-accept the remaining strict `"plugin"`
  assertions in rabbit-cage's own tests; unblocks #990):** the earlier
  dual-accept prep relaxed every rabbit-cage CODE site that branches on the
  vendored-mode value, but three rabbit-cage TEST assertions still pinned the
  OBSERVED value strictly to `"plugin"` — each of which drives the real
  `write_mode_marker` (which writes `detect_mode`'s value verbatim) or the real
  `detect_mode`/`show-mode.py` output against a vendored-signature layout, so
  each would go RED on the pending `detect_mode -> "vendored"` flip even though
  the code under test already dual-accepts. This change relaxes those three
  observe-side assertions to the same dual-accept membership test: (1)
  `test-show-mode-command.py` t1 (the `mode` field) and t3 (the human-summary
  line); (2) `test-write-mode-marker-wired.py` (marker content after a real
  SessionStart dispatch); (3) `test-mode-marker-root-consistency.py` (the
  canonical-path marker content in a faithful vendored install layout).
  Test fixtures that WRITE a chosen `"plugin"` marker as an INPUT to exercise a
  consumer (the `test-plugin-*` scope-guard/alert tests) are unchanged — they
  pin their own valid legacy input, not an observed output. The existing Inv 50
  is extended to require the dual-accept of rabbit-cage's own observe-side test
  assertions, and `test-mode-value-dual-accept.py` gains a guard that drives
  `write_mode_marker` with a `detect_mode` stub returning `"vendored"` and
  confirms the observed marker content satisfies the dual-accept. Simulated
  `detect_mode -> "vendored"` flip verified: rabbit-cage's full `test/run.py`
  stays green. rabbit-cage does NOT change `detect_mode` or `write_mode_marker`
  (#990/rabbit-meta scope). Coexistence deprecation criterion: drop the
  `"plugin"` arm from every dual-accept site once #980 completes.

- **v5.79.0 (feat #989: dual-accept vendored-mode value + rename surface
  terminology; gate-safe prep for the #980 `"plugin"` -> `"vendored"`
  rename):** prepares rabbit-cage for rabbit-meta's pending rename of the
  vendored-mode value WITHOUT flipping it here (the value flip is #990, blocked
  on this). Two rabbit-cage-only changes: (1) every rabbit-cage site that
  branches on the vendored-mode value now DUAL-ACCEPTS both spellings via
  `mode in ("vendored", "plugin")` — `scripts/show-mode.py` (the `detect_mode`
  return value driving the project-root derivation), `hooks/scope-guard.py`
  (the two `.rabbit/.runtime/mode` content reads: the vendored-branch dispatch
  and the per-mode override-marker path), and `scripts/scope-guard-on.py` (its
  override-marker-path mirror) — so the gate stays green both before and after
  the canonical value flips; (2) user-facing TERMINOLOGY `plugin mode` ->
  `vendored mode` renamed in the README modes table/section + Uninstall note,
  the `install.py` module docstring, and the spec Inv 45 prose, with the #981
  disambiguation note kept consistent. New Inv 49 documents the dual-accept
  coexistence shim and its deprecation criterion. rabbit-cage does NOT change
  `detect_mode` or `write_mode_marker` (those are rabbit-meta/contract scope).
  Enforced by test-mode-value-dual-accept.py and the updated
  test-show-mode-command.py / test-vendored-mode-disambiguation-note.py.

- **v5.78.0 (docs #981: clarify rabbit's vendored mode is distinct from Claude
  Code `/plugin` plugins):** added a one-line disambiguation callout to the
  README "Plugin mode" section noting that rabbit's vendored `.rabbit/` install
  (historically called "plugin mode") is unrelated to Claude Code's native
  `/plugin` marketplace plugins — they are independent mechanisms that merely
  share the word "plugin." Reduces the terminology collision identified in the
  #956 research without renaming anything (the rename is tracked separately in
  #980). Docs-only; no code or behavior change. Enforced by
  test-vendored-mode-disambiguation-note.py.

- **v5.77.0 (fix #968: `install.py --update` tolerates a closure that shrinks
  across a surface retirement):** the `--update` path is driven by the
  LOCALLY-installed (older) `install.py`, whose hardcoded closure still names
  surfaces the NEW upstream source has intentionally RETIRED (deleted/renamed
  files). The Inv 21 fresh-install integrity self-check treated EVERY closure
  source absent from `--src` as a hard "dangling required-file" abort, so a
  release crossing a retirement was permanently un-installable from an older
  install — the stale local closure could never be reconciled before the Inv
  22h re-exec into the new `install.py`. A FRESH install from the same new
  source succeeded (new installer + new closure are self-consistent), confirming
  the failure was specific to the `--update` path crossing a retirement. New Inv
  49 makes the integrity gate ASYMMETRIC by mode: a fresh install (no
  `--update`) still HARD-ABORTS on any absent closure source (unchanged); under
  `--update`, a closure source absent from the NEW `--src` is a TOLERATED
  closure SHRINK (a retired surface) — dropped, not aborted — so the per-file
  copy loops skip it and the in-place refresh proceeds to the re-exec, after
  which the NEW `install.py` validates its OWN corrected closure against the NEW
  source. Tolerance is scoped EXACTLY to the shrink: a path the NEW closure
  REQUIRES but the NEW source omits (a real packaging defect, not a retirement)
  still HARD-FAILS under the new code and at CI via the fresh-install integrity
  tests and the cross-feature contract gate. `check_install_sources_exist` is
  unchanged; the asymmetry lives in how `main()` consumes it. Added Inv 49.
  Enforced by the new `test/test-install-update-tolerates-closure-shrink.py`
  (e2e via the real `install.main()`). Wired into `test/run.py`.

- **v5.76.0 (feat #963: main-centric install/release channel with dev opt-in
  coexistence — Part 2 of #957):** moved the named development channel to a
  main-centric model. `install.py`'s `--channel` flag now accepts a third value
  `main` (resolves the `--update` self-fetch ref to the literal `main`, the
  default development tip) alongside the existing `stable` (dynamic
  latest-release default) and `dev` channels. `dev` is retained as an explicit
  opt-in channel during the coexistence window — the loop is still dev-based
  until the #957 admin cutover (dev->main merge + branch protection, tracked
  separately in the blocked #964), so naming `--channel dev` (or
  `RABBIT_REF=dev`) keeps working unchanged. The dynamic latest-release default
  (no flag) and the downgrade guard are untouched; the user still MUST name a
  branch tip to land on it. `install.sh`'s channel documentation now describes
  the main-centric model and adds a `RABBIT_REF=main` example beside the legacy
  `RABBIT_REF=dev` one; the live bootstrap one-liner URLs stay on `dev` until
  the #964 cutover lands install.sh on `main`. Amended Inv 26/27 (no new
  invariant). Enforced by the new
  `test/test-install-py-channel-main-default.py` (e2e: `--channel main`
  resolves to ref `main` via a mocked `fetch_upstream`; `main` is an accepted
  argparse choice and `dev` still is too) plus the reconciled existing channel
  tests (`test-install-py-channel-dev-opt-in.py`,
  `test-install-py-default-ref-not-dev.py`,
  `test-install-sh-default-ref-not-dev.py`,
  `test-install-py-default-ref-matches-install-sh.py`), all unchanged in intent
  and still green. Deployed repo-root `install.py` re-synced in-branch.

- **v5.75.2 (fix #961: include rabbit-issue Issue-Form/workflow surfaces in
  install FEATURE_INCLUDES):** added the two governed deployed surfaces
  declared by rabbit-issue's manifest — `github/ISSUE_TEMPLATE/file-item.yml`
  and `github/workflows/issue-form-autolabel.yml` — to
  `FEATURE_INCLUDES["rabbit-issue"]` in `install.py`. Without them the install
  set did not cover rabbit-issue's full manifest, so the manifest-closure
  invariant failed on a clean checkout and `check_manifest_drift` would rebuild
  rabbit-issue's surface on first Stop. No new invariant; the existing
  closure tests are the gate.

- **v5.75.1 (fix #958: meaningful version/channel fallback for local `--src`
  installs — no more `vunknown`):** added Inv 48. `install.write_version_pin`
  now derives a meaningful `.version` pin when `RABBIT_INSTALLED_REF` is unset
  or empty (the local `python3 install.py --src <checkout> --target ...` case)
  instead of writing the literal `unknown`. It derives `local-<short-sha>` via
  a read-only `git -C <src_root> rev-parse --short HEAD` against the source
  tree, falling back to the literal `local` when no SHA is resolvable (git
  absent, source not a checkout). Previously the `unknown` sentinel flowed
  verbatim into the SessionStart version box (`rabbit vunknown`) and the
  update-check headline (`current: unknown ... on channel unknown`), comparing
  a real upstream release against a non-version. An explicit
  `RABBIT_INSTALLED_REF` still wins verbatim (the published-install /
  `--update` self-fetch path is unchanged). New helper signature
  `write_version_pin(dst_root, src_root=None)` plus private
  `_local_src_marker(src_root)`; both best-effort, never raise. Enforced by
  `test/test-install-version-pin-local-src-not-unknown.py` (e2e: the produced
  `.version` fed through the deployed SessionStart dispatcher yields a banner
  with neither `vunknown` nor `channel unknown`).

- **v5.75.0 (fix #931: source the post-update changelog summary from the live
  `vX.Y.Z` release track):** repointed the Inv 46 post-update changelog summary
  added by #924 off the dead-track root `CHANGELOG.md` (frozen at
  `release/1.12.0`, not maintained by the release path — see rabbit-auto-evolve
  Inv 57, a READ reference) and onto the LIVE release channel: the annotated
  `vX.Y.Z` git tags carried in the source tree. `emit_changelog_summary` now
  enumerates the source tree's tags via `git -C <src_root> tag` and delegates
  to `render_changelog_summary(old_ref, new_ref, tags)` — whose signature
  changed from a CHANGELOG-body string to an iterable of `(tag, subject)`
  pairs. The renderer selects tags whose name parses to a semver in
  `old < tag <= new` (reusing `_parse_version`), orders them newest-first,
  names the `old -> new` range, lists each tag with its annotation subject
  verbatim, and points at the release history. The now-dead
  `_parse_changelog_sections` helper (which only fed the root-CHANGELOG path)
  was removed. Best-effort and deterministic: when git is unavailable or no
  tags fall in the range it degrades cleanly (prints nothing, never fabricates)
  and is never a failure mode; a normal `vX.Y.Z` update no longer silently
  degrades to a bare version-range pointer. `test/test-install-update-changelog-summary.py`
  rewritten to build a tagged source git repo and assert the summary renders
  the intervening tags (excluding the already-installed one), surfaces the tag
  annotation verbatim, does not read root `CHANGELOG.md`, and the renderer is
  pure over an in-memory `(tag, subject)` list. `install.py` is a deployed
  `publish_file` surface — its repo-root deployed copy must be republished.

- **v5.74.0 (feat #923: decompose-context scope-guard pass-through):** added a
  principled, explicit, auto-cleared pass-through to `hooks/scope-guard.py` for
  batch work that spans several feature directories — the documented
  replacement for the undiscoverable manual `.rabbit/.rabbit-scope-override =
  'session'` workaround. A new decompose-context marker
  `.rabbit/.runtime/decompose-active` carries a JSON object
  `{operation, features, expires?}`; while it is present, un-expired, and
  well-formed, scope-guard ALLOWs writes inside any feature directory named in
  `features` (resolved via the same `find-feature.py` lookup the per-feature
  markers use), in BOTH standalone and plugin mode. The marker is honored ONLY
  while present (orchestration sets it before batch work and clears it after);
  an optional ISO-8601 `expires` bounds an orphaned marker as defense in depth;
  a malformed, empty-`features`, or already-expired marker is treated as
  absent. The per-feature `.rabbit-scope-active-<feature>` markers, the global
  `.rabbit-scope-active` marker, and the legacy manual `.rabbit-scope-override`
  paths are unchanged (additive coexistence). New invariant Inv 47 specifies the
  marker path, content schema, set/clear semantics, and scope-guard
  interpretation; enforced end-to-end by
  `test/test-scope-guard-decompose-context.py` (wired into `test/run.py`).
  scope-guard.py is a deployed hook — its `.claude/hooks/` copy must be
  republished.

- **v5.73.0 (feat #922 piece 3/5: retire rabbit-spec-create from the install
  manifest):** updated `install.py` so the bootstrap closure no longer deploys
  the retired `rabbit-spec-create` skill and tracks the renamed dispatch
  script. Removed the `rabbit-spec-create/SKILL.md` entry from `SKILLS`;
  renamed the `FEATURE_INCLUDES["rabbit-spec"]` script entry
  `scripts/dispatch-spec-create.py` -> `scripts/dispatch-spec-creator.py` and
  removed its `skills/rabbit-spec-create/SKILL.md` entry. The
  `agents/rabbit-spec-creator.md` deploy mapping (AGENTS + FEATURE_INCLUDES)
  and the `templates/prompts/spec-create.txt` contract template are KEPT — the
  agent is upgraded, not retired, and the template is out of #922 scope. Inv 64
  install-closure (listed -> exists) is GREEN again. Spec Inv 21 prose and the
  Inv 17 (a2) carve-out comment updated to name the renamed script and the
  write-capable `rabbit-spec-creator` subagent as the spec-body writer.

- **v5.72.0 (feat #924: post-update changelog summary after `install.py
  --update`):** after a successful in-place refresh, `install.py main()` now
  emits a brief, DETERMINISTIC summary of what changed between the OLD and
  NEWLY-installed version, sourced from the just-installed repo `CHANGELOG.md`
  (Inv 28) — NOT AI-inferred. Two new stdlib-only helpers exported by
  `install.py` back this: `render_changelog_summary(old_ref, new_ref,
  changelog_body) -> str` (pure string→string; parses the keep-a-changelog
  body via `_parse_changelog_sections`, selects the sections whose label
  parses to a semver in `old < section <= new` reusing `_parse_version`, names
  the `old -> new` range, lists the intervening entries verbatim, and points
  at the full `CHANGELOG.md`) and `emit_changelog_summary(old_ref, new_ref,
  src_root)` (the IO wrapper `main()` calls, reading
  `<src_root>/CHANGELOG.md`). Emitted ONLY under `--update` and ONLY for a
  real upgrade: a no-op refresh (same version) emits no summary, and the
  pre-existing Inv 22e `updating A -> B` pin line is unaffected. Best-effort:
  a missing/unreadable `CHANGELOG.md` or an empty selection prints nothing and
  is never a failure mode. New spec Inv 46; new e2e
  `test/test-install-update-changelog-summary.py` (range + intervening entries;
  verbatim-from-file sentinel; no-op suppression; pure-renderer export);
  `CHANGELOG.md` added to this feature's `contract.md` `reads.files`.
  `rabbit-cage` bumped 5.71.0 -> 5.72.0. Closes #924.

- **v5.71.0 (fix #914: show the permission-bypass message on-demand, not on
  every startup):** the permission-bypass info message used to print on EVERY
  SessionStart as a `welcome_with_policy` welcome subline (added by #889 for
  discoverability), so a fresh `.rabbit` install surfaced it on every session
  start. That information is useful but non-urgent and should appear only when
  explicitly queried. The FOURTH SessionStart welcome subline was removed from
  `feature.json runtime.SessionStart` (the three policy-summary sublines remain),
  and the same message content/branding is now surfaced ON-DEMAND through the
  `/rabbit-cage-config` query path: `scripts/rabbit-cage-config.py`'s help path
  (`-h`/`--help`/`help`) prints the guidance (the ephemeral `Shift+Tab` live
  toggle AND the persisted `/rabbit-cage-config bypass-permissions true|false`
  path that writes `defaultMode` and takes effect after a Claude relaunch). The
  change targets ONLY the permission-bypass info message; the scope-override
  SAFETY notice (#917, Inv 16/25) STILL fires on startup when a `session`
  override is active. Inv 16 rewritten (FOURTH subline removed), Inv 40 gains
  clause (e) documenting the on-demand surface; obsolete #889 test
  `test-bypass-permissions-discoverable-at-sessionstart.py` removed and replaced
  by `test-bypass-permissions-on-demand-not-startup.py` (e2e: no startup advert,
  on-demand help emits the message, #917 safety notice intact). rabbit-cage
  5.70.0 -> 5.71.0.

- **v5.70.0 (fix #917: notify the user when a session scope override is active
  in plugin mode):** in plugin mode the session scope-override marker's
  canonical location is `<repo_root>/.rabbit/.rabbit-scope-override` (Inv 25),
  but `runtime.Stop` and `runtime.SessionStart` only declared a
  `check_marker_alert` for the standalone relative path `.rabbit-scope-override`
  — which `contract.lib.runtime` resolves against `repo_root` to the STANDALONE
  location. So a plugin-mode session running with an ACTIVE override got NO
  `[rabbit]` SCOPE GUARD OFF notice at session-start or tick-end: the user was
  never told the scope guard had been bypassed, asymmetric with the
  always-present bypass-permissions notice (a safety gap). Fix: added a SECOND
  `check_marker_alert` entry to BOTH `runtime.Stop` and `runtime.SessionStart`
  with the plugin-mode relative path `.rabbit/.rabbit-scope-override`, so the
  banner fires in either mode. The two entries never double-fire — the marker
  lives at exactly ONE canonical location per mode and `check_marker_alert`
  no-ops on an absent marker. A per-feature `.rabbit-scope-active-<feature>`
  marker (the normal bounded-scope mechanism) does NOT trip the notice. Inv 16
  (now SIX SessionStart entries) and Inv 25 (consumer (5) now declares both
  paths) updated. New e2e test
  `test-plugin-sessionstart-alert-at-canonical-override-path.py`; existing
  `test-plugin-scope-override-path-consistent.py` extended (t6 → 6 entries, new
  t7 pins the plugin-path entry in both events).

- **v5.69.0 (feat #889: make the bypass-permissions path discoverable):**
  rabbit-cage owns a first-class `bypass-permissions` configurable
  (`/rabbit-cage-config bypass-permissions true|false`, which writes
  `permissions.defaultMode`), but nothing in loaded context advertised it, so
  when a user expressed permission-mode intent the dispatcher defaulted to
  upstream Claude Code mechanisms (Shift+Tab, `--dangerously-skip-permissions`)
  and never surfaced the rabbit-native path. The active-override alert (Inv 40c)
  only fires once bypass is ALREADY active, so it cannot help discovery while
  bypass is OFF. Fix: added a FOURTH `welcome_with_policy` subline to
  rabbit-cage's `runtime.SessionStart` (its own feature.json) that advertises
  BOTH mechanisms and their difference in always-loaded SessionStart context —
  the ephemeral live toggle (`Shift+Tab`, this session only) and the persisted
  path (`/rabbit-cage-config bypass-permissions true|false`, writes
  `defaultMode`, takes effect after a Claude relaunch). Spec Inv 16 updated;
  enforced end-to-end by
  `test/test-bypass-permissions-discoverable-at-sessionstart.py` (drives the
  real deployed session-start-dispatcher subprocess and asserts the rendered
  systemMessage carries `/rabbit-cage-config bypass-permissions` AND names the
  Shift+Tab live toggle, with the three policy sublines unchanged). Wired into
  `test/run.py`. The signal is intentionally in-scope: the issue suggested a
  CLAUDE.md / policy edit, but those are outside rabbit-cage scope, so the fix
  uses rabbit-cage's OWN SessionStart welcome surface.
- **v5.68.1 (fix #897: fresh install omitted a SKILL-referenced script):**
  `#890` added `.claude/features/rabbit-decompose/scripts/handoff-scaffold.py`
  and referenced it from rabbit-decompose's `SKILL.md` Step 4, but
  `install.py`'s `FEATURE_INCLUDES['rabbit-decompose']` was not updated, so a
  fresh `curl … | bash` install did NOT ship the script and Step 4 failed at
  runtime with `No such file or directory`. Fix: added
  `"scripts/handoff-scaffold.py"` to `FEATURE_INCLUDES['rabbit-decompose']`
  (Inv 24 closure). The existing `test-feature-includes-scripts-closure.py`
  (t14) already caught the gap statically; this change additionally adds an
  end-to-end guard `test/test-install-ships-skill-referenced-scripts.py` that
  runs the REAL `install.main()` and asserts every SKILL-referenced backing
  script actually lands on disk AND is executable in the fresh install
  (derived from the deployed SKILL bodies, not from `FEATURE_INCLUDES`).
- **v5.68.0 (feat #888: deterministic `/show-mode` reporter):** Adds
  `scripts/show-mode.py`, a single-invocation, zero-AI reporter that prints
  whether rabbit is running in `plugin` or `standalone` mode plus the key
  evidence, so the model no longer has to infer mode from env/dir/settings
  across multiple tool calls. Output is Machine First: a single-line JSON
  object (`{mode, rabbit_root, project_root, feature_dir, evidence}`) followed
  by one derivative human `Mode: …` summary line; exit 0 in both modes (and in
  the degenerate rabbit-meta-unavailable case, where `mode` is `"unknown"`).
  Detection is delegated to the canonical resolver
  `rabbit-meta.lib.mode_detection.detect_mode` (a cross-feature INVOKE, now
  declared in `docs/contract.md`), lazy-imported relative to the script's own
  location so the reporter always agrees with the rest of the system. The
  script runs from SOURCE (no `publish_file` manifest entry, so no deployed
  copy drifts). New invariant 45; enforced by
  `test/test-show-mode-command.py` (e2e, plugin + standalone layouts), wired
  into `test/run.py`. Surfacing the reporter from the SessionStart banner or a
  `/rabbit-project status` subcommand is left as a follow-up to keep this touch
  to the script + its test.

- **v5.67.0 (fix #891: plugin-mode mode-marker written one `.rabbit` too
  deep):** In a plugin install (`RABBIT_ROOT = <project>/.rabbit`), the
  SessionStart mode marker was written to `<project>/.rabbit/.rabbit/.runtime/mode`
  (doubled `.rabbit`) because the dispatcher forwarded `RABBIT_ROOT` verbatim
  to `contract.lib.runtime.write_mode_marker`, which APPENDS `.rabbit` to its
  `repo_root` arg. `scope-guard.py` reads the SINGLE-`.rabbit`
  `<git-toplevel>/.rabbit/.runtime/mode`, so the absent marker mis-detected
  mode. `hooks/session-start-dispatcher.py` now reconciles the marker
  (`_reconcile_mode_marker`) after dispatch: when the resolved root is itself
  a `.rabbit` install dir, it relocates the doubled marker to the canonical
  single-`.rabbit` path (where scope-guard reads) and prunes the stray doubled
  tree; no-op in standalone mode. The detection logic stays owned by
  rabbit-meta/contract — only the file the contract API produced is relocated.
  A cleaner upstream fix (separating `write_mode_marker`'s rabbit-meta IMPORT
  root from its WRITE root) lives in the contract feature and is flagged for
  follow-up. New invariant 44; enforced by
  `test/test-mode-marker-root-consistency.py`. The deployed
  `.claude/hooks/session-start-dispatcher.py` copy is republished.
- **v5.66.0 (CRITICAL fix #880: fresh install aborts on a retired closure
  source):** `install.py`'s hardcoded file closure still referenced the
  `rabbit-feature-audit` skill that #853 deleted — the
  `SKILLS` entry and the `FEATURE_INCLUDES['rabbit-feature']`
  `skills/rabbit-feature-audit/SKILL.md` entry. Because `install.main()`
  requires every closure source to exist, the missing source aborted
  `curl … install.sh | bash` on every fresh install with
  "missing required source file: …/rabbit-feature-audit/SKILL.md". Both stale
  entries are removed. To prevent the class systemically, install.py gains the
  importable `check_install_sources_exist(repo_root)` (built on a new
  `closure_source_rels()` enumeration) — run as a fail-loud self-check inside
  `_main_with_args` (before any copy, naming the offending path) and exercised
  against the REAL repo by the new `test/test-install-closure-sources-exist.py`.
  The cross-feature contract gate (separate change) wires the SAME function so a
  surface retirement in ANY feature is screened against the install closure, not
  only when rabbit-cage is touched. Separately, the #849 e2e readiness test
  `test/test-install-e2e-ready-to-run.py` was CIRCULAR — its `_build_src_tree`
  copied exactly `install.SAME_PATH_FILES` et al. from the repo then ran install
  against that sandbox, validating install.py against its OWN list and never the
  repo's actual surface set. It now validates the closure against the REAL repo
  surface first (`test_closure_sources_exist_in_repo` via
  `check_install_sources_exist`, plus `test_every_feature_deployed_surface_covered`
  asserting no published surface is omitted) before building any sandbox.
- **v5.65.0 (fix #851: fresh install reports no surface drift on first run):**
  `install.py` now RUNS THE PUBLISH FLOW against the freshly installed tree
  after the closure copy and settings rewrite
  (`canonicalize_installed_surfaces`, calling the existing `run_publish_loop`
  which invokes the contract-owned `contract.lib.publish` APIs — the SAME path
  `check_manifest_drift` uses at runtime). Previously the installer laid down
  the COMMITTED deployed surfaces verbatim; a committed copy left un-republished
  after a source change shipped stale, and the user's first Stop hook
  re-published from source, found a diff, rebuilt, and emitted
  "Surface drift detected - rebuilt: ..." for edits the user never made
  (RABBIT-CAGE-16 class). Canonicalizing at install time makes the installed
  surfaces byte-identical to the runtime republish, so the first Stop is a clean
  no-op. Degrades gracefully: a publish failure is reported to stderr but does
  not fail the install (the closure copy is retained). New e2e regression test
  `test/test-install-no-drift-on-first-run.py` installs via the real
  `install.main()` then runs the real `check_manifest_drift` against the
  install and asserts no drift, including a deliberately-stale committed-surface
  case that the install must canonicalize.

- **v5.64.0 (feat #849: end-to-end plugin-install readiness test):** Added Inv
  42 and a new e2e test `test/test-install-e2e-ready-to-run.py` that runs the
  REAL user-facing installer `install.main()` (its real `--src/--target` CLI —
  not mocks, not the `run_publish_loop` dev-test path) into a throwaway
  `tempfile.TemporaryDirectory` sandbox sourced from the clean repo tree, then
  asserts the install is structurally complete AND wired ("ready to run short of
  launching Claude") without launching Claude: top-level closure present;
  `.claude/settings.json` present with every hook command across all four wired
  events (PreToolUse / Stop / SessionStart / UserPromptSubmit) resolving (via
  the install-rewritten `$RABBIT_ROOT`, Inv 19) to an EXISTING, EXECUTABLE file;
  every shipped feature dir carrying a valid `feature.json`; deployed
  agent/skill/command/hook copies byte-matching their source (deployed-copies-
  match), excepting installer-rewritten settings files; the `rabbit-project`
  command scaffold + `.claude/agents/` deployed; and no dangling references
  across the settings hook commands and every installer manifest destination.
  Test-only addition wired into `test/run.py`; no deployed surface changed.

- **v5.63.0 (fix #855: rabbit-cage's scope marker authorizes its owned repo-root bootstrap files):**
  rabbit-cage owns three repo-root bootstrap files — `install.sh`, `install.py`,
  and the root `README.md` (`install.py` + `README.md` are `publish_file`
  destinations in the manifest; `install.sh` is the committed bootstrap) — that
  live OUTSIDE its feature directory. The standalone per-feature scope-marker
  gate (Inv 5) authorized writes only INSIDE the named feature's directory, so a
  rabbit-cage TDD cycle editing those owned root files (e.g. #848/#850) had to
  fall back to an ad-hoc scope-guard override, which the override rule reserves
  for plan / temporary-document writing — never feature code. Added Inv 41 and
  extended `hooks/scope-guard.py`'s standalone per-feature marker branch: when
  the active marker is `.rabbit-scope-active-rabbit-cage`, a write whose absolute
  target equals `<REPO_ROOT>/install.sh`, `<REPO_ROOT>/install.py`, or
  `<REPO_ROOT>/README.md` is ALLOWED with no override. The owned-root set is an
  EXPLICIT, MINIMAL module-level constant `RABBIT_CAGE_OWNED_ROOT` (exactly those
  three basenames); the carve-out does NOT broaden rabbit-cage to arbitrary root
  paths (an unrelated root file or another feature's dir still DENIES), and ONLY
  rabbit-cage's marker authorizes the set (another feature's marker does not).
  New e2e `test/test-scope-guard-cage-owned-root.py`, wired into `test/run.py`.
  `hooks/scope-guard.py` is a deployed hook (`publish_hook`) — its
  `.claude/hooks/` copy drifts until republished.

- **v5.62.0 (fix #850: `install.py --update` downgrade guard; action tracks the check):**
  `install.py --update` could DOWNGRADE — a v1.14.14 install slid back to the
  dead `release/1.12.0` branch while the update-CHECK banner advertised v9.0.26;
  the action and the check disagreed and the action went BACKWARDS. Extended Inv
  27 with a downgrade guard on the dynamic-default channel: after resolving the
  latest ref, `--update` reads `<target>/.version` and refuses to fetch when the
  resolved ref is not strictly newer (semver-tuple comparison; `release/1.12.0`
  → `(1,12,0)`, `v9.0.26` → `(9,0,26)`). An older-or-equal latest is a no-op —
  it prints "already up to date", makes no change, and leaves `.version`
  byte-untouched. The guard governs ONLY the dynamic default; an explicit
  `--version`/`--ref`, `--channel dev`, or `RABBIT_REF` bypasses it and installs
  the named ref verbatim (intentional downgrade still possible). README
  reconciled: the dead `release/*` example replaced with a live tag and the
  no-downgrade behavior documented. New test
  `test-install-py-update-no-downgrade.py` (newer → fetch on advertised tag;
  older → refused, untouched; equal → no-op; explicit older `--version` →
  bypasses guard, fetches verbatim).

- **v5.61.0 (fix #848: install.sh + install.py default ref resolves latest release dynamically):**
  Fresh `curl … install.sh | bash` installs were frozen at the hardcoded
  `RABBIT_REF=v1.14.14` default while GitHub's latest release had advanced to
  v9.0.26 — the release process never bumped the install.sh/install.py default.
  Reworked Inv 26 and Inv 27 so the DEFAULT path (no explicit `RABBIT_REF`/CLI
  ref) resolves GitHub's latest published release dynamically — install.sh via a
  `curl` query to `releases/latest`, install.py by reusing the contract-owned
  `fetch_upstream_version` (the same logic the update-check and `/rabbit-update`
  use). An explicit `RABBIT_REF` (or `--version`/`--ref`/`--channel dev`) still
  short-circuits the lookup verbatim; only the default became dynamic. When the
  latest-release lookup fails (offline / API outage), both installers degrade
  gracefully to a hardcoded last-known-good tag (`RABBIT_FALLBACK_REF` /
  `HARDCODED_STABLE_DEFAULT`, now `v9.0.26`, kept in lock-step and never `dev`)
  with a clear stderr line. README reconciled to describe the dynamic mechanism.
  New tests `test-install-sh-resolves-latest-release.py` and
  `test-install-py-resolves-latest-release.py`; the former default-ref pins
  repurposed to guard the offline fallback.

- **v5.60.0 (measured reduction: cut dead `/rabbit-config` coexistence prose):**
  The rabbit-config feature is retired, so every spec/contract/README claim that
  the central `/rabbit-config` surface is "still live" or "coexisting" is now
  dead-but-plausible prose. Removed it deterministically: Inv 7 (the "central
  `/rabbit-config scope-guard on` surface still dispatches" sentence), Inv 31
  (the dead `rabbit-config`'s `iterate_configurables_alerts` footer example,
  generalized to "features sorting alphabetically after rabbit-cage"), Inv 40
  intro + Inv 40c (the "both surfaces are live" / "central `iterate_configurables_*`
  alert path remains live" coexistence sentences), Inv 40(d) ("identical to the
  central path"), Inv 40 test-clause (vii) (now "the retired central rabbit-config
  interpreter is absent"), the contract `never`-clause, the Out-of-Scope
  `/rabbit-config` skill bullet, and the README command-table `/rabbit-config
  permissions lock|unlock` row + coexistence note. Repointed two tests
  (`test-scope-guard-revoke-uses-rabbit-config.py`,
  `test-rabbit-cage-config-command.py`) from the dead coexistence E2E to a
  retirement-absence assertion (this also re-greens the suite, which the
  rabbit-config retirement had left red). spec.md 519 -> 515 lines.
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
