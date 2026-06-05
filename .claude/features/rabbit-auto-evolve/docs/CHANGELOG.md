---
feature: rabbit-auto-evolve
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-auto-evolve feature is retired or its change history is folded into a structured schema-tracked log
---

# rabbit-auto-evolve — Changelog

Version-keyed change log for the rabbit-auto-evolve feature. The version here
tracks a single four-way lockstep version that the contract repo-gate's
feature-shape check ENFORCES as equal across `feature.json`, `docs/spec.md`
frontmatter, `docs/contract.md` frontmatter, and `skills/rabbit-auto-evolve/
SKILL.md` frontmatter; `docs/contract.md` participates in that lockstep
equality rather than carrying an independent version (the gate is
authoritative).

## Version notes

- **v0.63.1 — 2026-06-04** — housekeeping measured-reduction wave (#809,
  child of #794). Consolidated the "Current behaviour" section, which
  restated every invariant's normative content as a parallel bullet list
  with "(design doc §N)" citations, into a one-paragraph pointer to the
  numbered Invariants (the normative source). Pure prose reduction: zero
  behavior/contract loss, no invariant retired, numbering still contiguous,
  every load-bearing token preserved. spec.md dropped from 3431 to 3367
  lines, clearing the advisory deep-slim ceiling of 3384 enforced (soft)
  by `test-spec-housekeeping-751-deep-slim-consolidated.py`. The
  decomposition-lifecycle cross-reference (Inv 53) that lived only in the
  removed bullet was re-homed into the Inv 26 shape-3 (`decomposition`)
  table row where it is normatively accurate. Four-way version lockstep
  bumped 0.63.0 → 0.63.1; deployed SKILL.md republished from source.

- **v0.63.0 — 2026-06-04** — fetch-before-close fix for the Inv 6
  close-after-merge step (#802, `merge-prs.py` 1.5.0 → 1.5.1). `gh pr merge
  --squash` creates the squash commit on the REMOTE `dev` only, so the local
  repo has not seen that SHA when the close step runs; `item-status.py close
  --commit-sha <sha>` (which requires the SHA to resolve to a real local
  commit, #423 Part C) then failed and the referenced issue leaked OPEN in
  headless ticks that have no dispatcher to recover. `merge-prs.py` now runs
  `git fetch origin <sha>` (falling back to `git fetch origin dev`) before the
  first close so the SHA resolves locally and the close succeeds; it never
  runs the permission-denied `git merge`, and the fetch is best-effort and
  never fails the merge. Regression test `test-merge-prs.py` adds the
  "SHA not yet local at close time" case (a `git`-fetch shim plus a
  SHA-gated `item-status.py` shim). Discovered follow-up (not built here):
  a persisted `close_failed` retry that re-drains on a later tick, so a
  transient close failure self-heals even when the fetch path cannot reach
  the SHA.
- **v0.62.0 — 2026-06-04** — housekeeping cycle bundling three small
  rabbit-auto-evolve-scoped corrections (#797, #798, #799), all strictly within
  this feature.
  - **#797 (triage cross_scope accuracy, `triage-issue.py` 1.9.0 → 1.10.0)** —
    fixed two observed Inv 51 detection bugs. FALSE NEGATIVE: an explicit
    cross-feature scope DECLARATION (`Cross-feature (A + B)`, `Cross-feature:
    A, B`, `spans <feature> and <feature>`) now sets `cross_scope: true` even
    when the body names no second `.claude/features/<name>/` edit-path and
    carries no repo-wide phrase (new `_CROSS_FEATURE_DECL` signal, checked
    outside parent-reference lines). FALSE POSITIVE: a `.claude/features/<name>/`
    path on a READ-ONLY line (a line carrying `verify against`, `confirm
    against`, `read-only`, `do not edit`, `refer to`, `see`) is now stripped
    before the edit-target feature set is computed, so a `verify against
    .claude/features/contract/lib/runtime.py` confirmation no longer inflates
    the cross-scope count. `test/test-cross-scope.py` extended with three
    regression cases (true `Cross-feature (A + B)` declaration, true `spans X
    and Y` declaration, false `verify against <path>` read-only mention); the
    Inv 51 spec text and `test/test-spec-cross-scope-invariant.py` updated to
    match.
  - **#798 (stale `banner-status.py` docstring, 1.1.0 → 1.2.0)** — removed the
    obsolete `Ownership migration (v0.7.5)` paragraph claiming
    `contract.lib.runtime.emit_auto_evolve_banner` still inlines the variants
    and does NOT yet call this script. That migration has landed:
    `emit_auto_evolve_banner` is now a pure subprocess dispatcher delegating
    line1/line2 to `banner-status.py`. The docstring now states that ownership
    reality. Pure docstring cleanup (read-only confirmation against the
    contract-scope file; no contract edit).
  - **#799 (CHANGELOG version-equality note)** — corrected the misleading note
    claiming `docs/contract.md` "carries its own version"; the contract
    repo-gate's feature-shape check ENFORCES four-way version equality
    (`feature.json` == `docs/spec.md` == `docs/contract.md` == `SKILL.md`), so
    `docs/contract.md` participates in that lockstep rather than versioning
    independently.
  - Four-way version lockstep 0.61.0 → 0.62.0 (feature.json + docs/spec.md +
    docs/contract.md + SKILL.md frontmatter); dispatcher republishes the
    deployed SKILL copy in-branch.

- **v0.61.0 — 2026-06-04** — SessionStart banner agreement for the
  post-`on`/pre-`start` restart-pending window (#793, piece 2 of 2; piece 1
  fixed the symmetric Stop line in `contract`). `banner-status.py` now splits
  its lowest-priority `none` branch (Inv 22) by the presence of
  `.rabbit/auto-evolve-state.json`: ABSENT (loop configured by `on` but never
  started — only `start-loop.py` creates that file) emits the restart-pending
  line2 `auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start`
  (icon ⏸, color yellow), VERBATIM the same as the Stop line so SessionStart
  and Stop agree; PRESENT retains the existing `paste: /rabbit-auto-evolve start`
  idle line. The four priority markers (aborted > restart-needed > running)
  still win regardless of the state file. Detection is a single
  `os.path.isfile` probe — no git, no `gh`. `test/test-banner-status.py`
  extended to cover both `none` sub-cases and priority-wins-when-state-absent.

- **v0.60.1 — 2026-06-03** — decouple from the dead central
  `iterate_configurables_*` runtime functions ahead of their removal (#786,
  subagent 1 of the 2-feature barrier; contract deletes the functions in
  subagent 2). After rabbit-config was retired (#769) the central
  `contract.lib.runtime.iterate_configurables_alerts` / `_banner` functions
  are dead — no `feature.json` `runtime[]` declares them, and per-feature
  `emit_configurable_alert` entries replaced them. rae's
  `test/test-banner-suppression.py` was the last live importer/caller of
  `iterate_configurables_alerts`, so it is decoupled FIRST (landing green
  while the function still exists). The test is rewritten to exercise ONLY
  the rae-OWNED half of the suppression contract — the auto-evolve composite
  banner (`emit_auto_evolve_banner`) and stop-line
  (`emit_auto_evolve_stop_line`), which emit IN PLACE OF the suppressed
  per-configurable alerts when `.rabbit-auto-evolve-active` is present and are
  a no-op when it is absent. The per-id alert SUPPRESSION HOOK itself lives in
  `contract.lib.runtime` (Inv 54) and is owned by the `contract` feature (per
  spec.md "What this feature does NOT define"); its coverage already lives in
  `contract/test/test-runtime-iterate-configurables-alerts.py` (t12+), so the
  rae test no longer duplicates it. S1–S4 scenarios are preserved as
  banner/stop-line assertions; the now-redundant synthetic rabbit-cage
  feature.json + alert-filter helper are dropped. `set-evolve-mode.py` (script
  Version 1.3.0 → 1.3.1): the two cosmetic docstring mentions of the retired
  `rabbit-config.py` (describing the shared sys.path import pattern) are
  reframed to describe the pattern directly — non-functional. No spec or SKILL
  prose change; four-way frontmatter version bump 0.60.0 → 0.60.1 to keep
  lockstep equality with the CHANGELOG entry (dispatcher republishes the
  deployed SKILL copy for the version bump). No contract
  `provides`/`reads`/`invokes`/`never` schema change.

- **v0.60.0 — 2026-06-04** — marker dual-read coexistence (phase 1 of
  #733/#336). The approval-bypass marker gains a new name
  `.rabbit-tdd-autonomous` alongside the legacy `.rabbit-human-approval-bypass`.
  `check-preconditions.py` already dual-reads either name (shipped in #481);
  this change makes `set-evolve-mode.py` the matching writer: `on` now writes
  BOTH names (additive — step 1b after step 1; rolled back together on
  failure), and `off` deletes BOTH (step 3b after step 3; idempotent).
  PRESENCE semantics are unchanged (present = bypass/tdd-autonomous active).
  This lands BEFORE the #336 read-path rename so the running loop — whose disk
  currently holds only the legacy name — keeps passing preconditions
  (`all_pass: true`). Removal of the legacy write is a later cleanup (#769).
  set-evolve-mode.py script Version 1.2.0 → 1.3.0. spec.md Inv 1 on/off steps
  and the source SKILL.md `on`/`off`/`start` surfaces note both marker names
  during the coexistence window. The user-facing CONFIGURATION subcommand is
  NOT renamed (that is #336). No invariant renumbering. Four-way version
  lockstep 0.59.0 → 0.60.0 (feature.json + spec.md + contract.md + SKILL.md
  frontmatter). Historical CHANGELOG entries are unchanged.

- **v0.59.0 — 2026-06-04** — remove `rabbit-managed` selection + the #731
  leak-detector (step 3 of #753). Now that selection is actionability-based
  (#758) and provenance is migrated (#759), nothing depends on the
  `rabbit-managed` label. `fetch-queue.py` drops the `--detect-leaks` flag and
  its `is_leak`/`detect_leaks` code path (moot — Inv 25 convergence is
  label-independent and actionability selection already surfaces every open
  feature+priority issue); script Version 1.2.0 → 1.3.0. spec.md and the source
  SKILL.md drop `rabbit-managed` as a selection/queue concept: Inv 2 selection
  is purely actionability; the Inv 25 de-queue Red-Flag is rephrased from "MUST
  NOT remove `rabbit-managed` from an OPEN issue" to "MUST NOT strip the
  actionability labels (`feature:`/`priority:`) from an OPEN issue"; the
  leak-detector mention and the `discovered_issues` `rabbit-managed`-on-file
  note are removed (file with `feature:`/`priority:` only). rae tests migrated
  to the actionability basis. Four-way version lockstep 0.58.0 → 0.59.0
  (feature.json + spec.md + contract.md + SKILL.md frontmatter). Historical
  CHANGELOG entries are unchanged.

- **v0.58.0 — 2026-06-03** — `update-state.py` now MIGRATES-IN-PLACE an older
  but additively-compatible on-disk state instead of hard-failing at the
  persist phase (#761). When #727 bumped the state schema 1.2.0 → 1.3.0 by
  ADDING the optional `decomposition_parents` field, no migration was provided,
  so an older `.rabbit/auto-evolve-state.json` wedged persist (Inv 11) every
  full post-dispatch tick with `schema_version: expected '1.3.0', got '1.2.0'`,
  aborting the tick (Inv 20). The fix adds an explicit, deterministic
  version-migration LADDER (`1.1.0 → 1.2.0` seeds `pending_post_merge=[]`;
  `1.2.0 → 1.3.0` seeds `decomposition_parents={}`): an older version on the
  ladder is walked rung-by-rung to current, each newly-added optional field is
  seeded with its documented default only when absent (pre-existing data is
  preserved), `schema_version` is set to current, and THEN the state is
  validated. A current-version state is a no-op (untouched/idempotent). A
  newer-than-current version, or an older version NOT on the ladder, STILL
  errors clearly and writes nothing. Future additive bumps append one rung.
  Script-and-test only (no spec/contract/SKILL prose change); `update-state.py`
  module Version bumped 1.3.0 → 1.4.0, and the feature four-way version bumped
  0.57.0 → 0.58.0 to keep the lockstep equality.

- **v0.57.0 — 2026-06-03** — Queue selection switched to ACTIONABILITY basis
  (#758, coexistence step 1 of #753 "retire rabbit-managed"). `fetch-queue.py`
  now selects OPEN issues that carry BOTH a valid `feature:` label AND a valid
  `priority:` label, instead of `--state open --label rabbit-managed`. Per
  #753's verified finding (0 open feature-labeled issues lack rabbit-managed)
  this returns the IDENTICAL set today, so the change is BEHAVIOR-PRESERVING.
  COEXISTENCE: `rabbit-managed` is still TOLERATED (selected issues may carry
  it) and the #731 de-queue leak detector (`--detect-leaks`) is unchanged —
  only the selection BASIS moved, so later #753 steps can retire the label
  without the loop ever losing its queue. This aligns the actual selection
  with the already-LABEL-INDEPENDENT convergence guarantee (Inv 25). Inv 2
  prose, the Purpose statement, the component table, and the Red Flag /
  convergence prose in spec.md + SKILL.md updated to the actionability basis;
  `test/test-fetch-queue.py` gains an actionability-selection scenario
  (label-independence + exclusion of non-actionable issues). No invariant
  renumbering.

- **v0.56.0 — 2026-06-04** — Deep slim housekeeping wave (#751, under #639):
  consolidated six redundant/overlapping invariants into their load-bearing
  parents and reflowed the numbering to contiguous 1..53. Merges (old → parent):
  Inv 51 (issue_type/created_at wiring) → Inv 46 (computed score); Inv 54
  (observability-log attribution) → Inv 37 (log-tick.py); Inv 44 (leaked
  branch-switch restore) → Inv 43 (clean-dispatch-leaks.py, now three leak
  classes); Inv 42 (guard-before-marker ordering) → Inv 35 (stale-marker
  running-guard); Inv 49 (refire dedup) → Inv 33 (immediate-refire); Inv 59 (no
  de-queue Red Flag) → Inv 25 (convergence). Plus targeted prose tightening of
  verbose enforcement enumerations. MEASURED reduction: invariant count
  59 → 53 (−6); docs/spec.md 3534 → 3382 lines (−152). Zero behavior/contract
  loss — every script name, schema field, marker, decision-table row, and
  MUST/MUST-NOT rule preserved; the contiguity guarantee and every within-rae
  `Inv N` cross-reference were rewritten in lockstep via
  `contract.lib.reflow`. Cross-feature citations of rae invariant numbers
  19/28/31 are UNCHANGED (they sort below the first merged number). Lockstep
  version bump across feature.json / spec.md / contract.md / SKILL.md.

- **v0.55.2 — 2026-06-03** — Spec-accuracy fix (#736): the "fresh context"
  claim in Inv 32 (DEVELOPMENT tick) and Inv 33 over-promised — it is true
  ONLY for the system-cron / headless path (each tick is a brand-new
  Claude-free OS process via `tick-headless.py`, zero accumulated history).
  On the `CronCreate` FALLBACK path (crontab-restricted hosts) there is NO
  fresh context: the one-shot enqueues the tick prompt into the SAME live
  Claude session, so it fires as a NEW TURN in the existing conversation —
  session history is REUSED and ACCUMULATES across ticks, bounded by Claude
  Code auto-compaction, NOT freshness. Inv 32 and Inv 33 now PATH-QUALIFY the
  fresh-context guarantee (system-cron path only) and document the fallback's
  compaction-managed context reuse; the mirrored SKILL.md prose (top blurb,
  Scheduling section, exit-paths block) and the `schedule-decision.py` script
  table row are corrected to match. Prose-only: NO invariant renumbered, no
  invariant added/removed, no cross-reference broken; the Inv 33 title is
  reworded from "Immediate fresh-context refire" to "Immediate refire when
  work remains" (the over-claim was in the title itself). No code change. The
  spec-prose regression `test/test-spec-cron-invariant.py` is extended (#736
  checks) to assert the fresh-context claim is path-qualified and the
  fallback reuse/compaction wording is present in spec.md and the SOURCE
  SKILL.md (RED before the edit, GREEN after). Versions bumped 0.55.1 →
  0.55.2 across feature.json, docs/spec.md + docs/contract.md frontmatter,
  and the source SKILL.md; the deployed `.claude/skills/` copy is republished
  by the dispatcher (out of this feature's edit scope).
- **v0.55.1 — 2026-06-03** — Removed the invariant count-floor ratchet from
  `test/test-spec-invariant-numbering-contiguous.py` (#750). The test had a
  `COUNT_FLOOR = 59` constant and an assertion (c) failing whenever the invariant
  count dropped below the #725 baseline — a one-way ratchet that forbade
  consolidating or retiring any invariant and turned the gate red on legitimate
  housekeeping (e.g. the upcoming #751 deep-slim). The constant, its assertion
  block, and the associated comment/docstring clause are deleted; assertions
  (a) contiguous 1..N and (b) no dangling in-range `Inv n` references are kept
  unchanged. The (a)/(b) logic was lifted into helper functions so a #750
  regression guard can exercise it against a small contiguous surface whose
  count is far below the old floor, proving no count constraint survives.
  Test-only change; no spec/contract/SKILL body prose changed (frontmatter
  version bumped lockstep, dispatcher republishes the deployed SKILL copy for
  the version field).

- **v0.55.0 — 2026-06-03** — Fixed the Inv 33 immediate-refire one-shot being
  intermittently dropped (~14% of the time) by a minute-boundary skid (#748).
  `schedule-decision.py` pinned the one-shot's cron minute as `current minute +
  1` at DECISION time, but the dispatcher arms it only after the Inv 49 dedup
  round-trip (`CronList` → `CronDelete` → `CronCreate`), which eats several
  seconds. A decision landing in the final seconds of a wall-clock minute let
  that round-trip cross the minute boundary, so the `+1` pinned minute became
  the CURRENT (already-started) minute; since the one-shot is pinned to a
  specific `M H * * *` minute (not `*/1`), cron's next match was ~24h later —
  the refire was effectively parked (liveness backstopped by the heartbeat, so
  a responsiveness, not a liveness, regression). The deterministic fix changes
  the pinned-minute buffer from `+1` to `+2` (`_ONESHOT_MINUTE_BUFFER` in
  `schedule-decision.py`), keeping the pinned minute strictly in the future even
  after the multi-second round-trip while staying "~1 min" responsive and
  minutes-based. The `#refire` marker and `durable: false` / `recurring: false`
  semantics are unchanged. Inv 33 prose in `docs/spec.md` and the dispatcher
  prose in `skills/rabbit-auto-evolve/SKILL.md` now document the `+2` buffer and
  its arm-time-skid rationale. `test/test-schedule-decision.py` gains scenario J
  (the pinned minute is `>= 2` min ahead for every near-boundary decision
  minute, the cron stays a valid pinned `M H * * *`, and the marker + flags are
  preserved); `test/test-spec-cron-invariant.py` now requires the buffer prose.
  `schedule-decision.py` bumped to 1.3.0.

- **v0.54.0 — 2026-06-03** — Opted rabbit-auto-evolve into the contract STRICT
  contiguous invariant-numbering tier (#738, a #724 follow-up). The strict tier
  (contract Inv 30 / `check_invariant_monotonic_order`) is per-feature opt-in
  via `feature.json "contiguous_invariants": true`; rae reflowed to contiguous
  1..N under #725 and now declares the flag, so the contract suite permanently
  enforces contiguity (no gaps) on rae instead of merely tolerating it. A fresh
  `scripts/reflow-invariants.py --dry-run` confirmed the numbering was ALREADY
  contiguous 1..59, so NO renumber was needed — this release is the single-flag
  opt-in plus its regression guard. New e2e test
  `test/test-contiguous-invariants-optin.py` asserts (a) the feature.json flag
  is `true`, (b) docs/spec.md `## Invariants` is contiguous 1..N, and (c) the
  live contract strict-tier check runs GREEN for rae. No SKILL.md body change
  (frontmatter version bump only; dispatcher still republishes the deployed
  copy for the version field).

- **v0.53.1 — 2026-06-04** — Locked in the contiguous invariant-numbering
  reflow required by #725. Re-assessment of the CURRENT `docs/spec.md` found
  the numbering ALREADY contiguous 1..59 with NO gaps, no duplicates, and no
  dangling rae-local `Inv N` references — the 14-gap set the #725 issue body
  describes (gaps at 10,11,12,17,31,32,34,39,41–46; 33 live invariants → 47)
  predates the housekeeping that has since landed (the earlier gap-closing
  reflows and #726/#731). No spec renumbering was therefore needed; doing one
  would have been a no-op rewrite. The deliverable is a durable regression
  guard: new e2e test `test/test-spec-invariant-numbering-contiguous.py`
  asserting (a) the `## Invariants` section is exactly contiguous 1..N (no
  gaps/dups), (b) no in-range `Inv n` citation dangles (numbers above N are
  cross-feature references — contract Inv 64/65, rabbit-config Inv 17 — and
  are excluded), and (c) the invariant count never drops below the #725
  baseline of 59. The contract-suite monotonic check (contract Inv 38) only
  guards strictly-increasing order and tolerates gaps; this feature-level
  test adds the missing CONTIGUITY guarantee. No SKILL.md body change
  (frontmatter version bump only; dispatcher still republishes the deployed
  copy for the version field).

- **v0.53.0 — 2026-06-03** — Forbade "de-queue" — the convergence hole that
  stranded open valid issues (#731). The loop had been removing `rabbit-managed`
  from OPEN issues as a parking/hand-back action, dropping them out of
  `fetch-queue.py`'s `--state open --label rabbit-managed` view so the
  convergence guarantee (Inv 25) — which only governs issues that still reach
  triage — could never apply. Four-part fix: (1) new Red-Flag **Inv 59** in
  `docs/spec.md` and the SKILL.md `Red Flags — STOP` section forbidding label
  removal from an OPEN issue, alongside the Inv 13 AskUserQuestion ban;
  (2) made the Inv 25 convergence guarantee explicitly LABEL-INDEPENDENT — an
  open valid issue must converge regardless of whether it still carries
  `rabbit-managed`, and removing the label while open is NOT a convergence
  outcome; (3) added a deterministic leak detector
  `fetch-queue.py --detect-leaks` (script bumped 1.0.0 → 1.1.0) that surfaces
  `{"leaks": [...]}` for OPEN issues with a `filed-by:*` provenance label but
  missing `rabbit-managed`; (4) new e2e test
  `test/test-spec-forbid-dequeue-invariant.py` plus scenario C in
  `test/test-fetch-queue.py` (synthetic mock-`gh` de-queue case). The
  follow-up "blocked-on-human-precondition" tracked state is explicitly
  DEFERRED by #731 (maintainer call) and NOT built here. Numbering stays
  contiguous 1..59. SKILL.md body changed (dispatcher republishes).

- **v0.52.0 — 2026-06-04** — Slimmed the ten largest invariants in
  `docs/spec.md` (#726, under #639). The spec was the largest in the repo;
  the 10 biggest invariants totalled 1,264 lines (~37% of the Invariants
  section). This pass TIGHTENED their prose — removing duplicated
  explanation, restated rationale, narrative incident retellings, and verbose
  multi-sentence restatements — while PRESERVING every normative/load-bearing
  statement, MUST/MUST-NOT rule, script name, schema field, decision-table
  row, and cross-reference (verified: all 23 spec-invariant tests still
  GREEN). No invariant was deleted and none renumbered (that is the sibling
  #724/#725 job); the numbering stays contiguous 1..58. The SKILL.md body was
  NOT touched (spec-only). spec.md: **3,594 → 3,451 lines (−143)**.
  Per-invariant before→after (cut): Inv 3 246→227 (−19); Inv 32 177→149
  (−28); Inv 4 132→114 (−18); Inv 6 123→110 (−13); Inv 7 118→109 (−9);
  Inv 30 115→103 (−12); Inv 56 95→76 (−19); Inv 1 93→81 (−12); Inv 18 83→75
  (−8); Inv 29 82→77 (−5); top-10 total 1,264→1,121 (−143). New e2e
  `test/test-spec-housekeeping-726-top10-invariants-slimmed.py` pins (a) all
  58 invariants present + contiguous, (b) the spec.md total line-count drop,
  and (c) a sample of load-bearing literals still present.
- **v0.51.0 — 2026-06-03** — Configurable tick cadence (#722). The cadence
  was single-sourced (#723) but still hardcoded to `CADENCE_MINUTES = 30` —
  tuning it required a source edit + redeploy. Now the cadence is OPERATIONAL
  CONFIG with 30 (`*/30`) as the DEFAULT: `install-cron.py` (script
  1.3.0 -> 1.4.0) resolves the effective cadence via a new
  `_configured_cadence()` helper with precedence env var
  `RABBIT_AUTO_EVOLVE_CADENCE` > `cadence_minutes` in the OWN state-dir config
  file `<state_dir>/auto-evolve-cadence-config.json` (mirroring the
  `auto-evolve-log-config.json` pattern; NOT rabbit-cage's `configuration`
  array nor rabbit-config) > the `CADENCE_MINUTES` default. The resolved value
  is VALIDATED (integer in `1..59`); a non-integer or out-of-range value is
  REJECTED — the script warns (branded) and falls back to the default rather
  than install a nonsense cron line. BOTH scheduler paths derive from the SAME
  resolved cadence at install time: the system-cron entry line and the
  `CronCreate`-fallback heartbeat move together (e.g. cadence 15 →
  `*/15 * * * *` + `13,28,43,58 * * * *`). New e2e
  `test/test-cron-cadence-config.py` pins the default-30, the env override, the
  config-file override (both paths), and validation/rejection. The default
  (no env, no config file) is unchanged: `*/30 * * * *` + `13,43 * * * *`.
- **v0.50.0 — 2026-06-03** — Single cadence source of truth (#723). The tick
  cadence had no single source: `install-cron.py` held TWO independent
  hardcoded literals — `SCHEDULE = "*/30 * * * *"` (system-cron path) and
  `HEARTBEAT_EXPR = "13,43 * * * *"` (CronCreate fallback) — that were
  decoupled, so changing the system-cron cadence left the fallback silently at
  the old value; the heartbeat literal was additionally duplicated verbatim
  into `docs/spec.md` and the source `SKILL.md`. Fixed by codifying the cadence
  ONCE as `CADENCE_MINUTES` in `install-cron.py` (script 1.2.0 -> 1.3.0): both
  `SCHEDULE` and `HEARTBEAT_EXPR` now DERIVE from it via `_system_cron_expr()`
  and `_heartbeat_expr()` — the heartbeat is the same cadence shifted off the
  `:00`/`:30` marks by a fixed `HEARTBEAT_OFFSET` (deterministic transform, not
  a second literal), so changing the cadence propagates to BOTH paths. New e2e
  `test/test-cron-cadence-source.py` pins the single source, the derivation,
  the :00/:30 avoidance, and every spec.md / SKILL.md cron literal to the
  codified value so any drift fails the gate. The default cadence is unchanged
  (system cron `*/30 * * * *`, heartbeat `13,43 * * * *`).
- **v0.49.0 — 2026-06-04** — Decomposed-parent autoclose (#721). The loop
  decomposed cross-feature mandates into N per-feature children but never
  closed the parent once all children closed (#530, #677 both lingered OPEN
  and were closed by hand). Two root causes fixed: (1) the parent->children
  link was only a prose comment table (a machine-first violation) — now
  recorded machine-readably under the new `decomposition_parents` state map
  (schema bumped 1.2.0 -> 1.3.0) by the new `scripts/record-decomposition.py`
  helper, which the SKILL.md decomposition path invokes at decompose time;
  (2) no tick phase rolled the parent up — now the new
  `scripts/close-decomposed-parents.py` runs each tick inside
  `run-post-merge.py` (after the catch-up phase): for every tracked parent
  whose recorded children are ALL closed it closes the parent
  (`gh issue close --reason completed`) and drops the parent key; a parent
  with any open child is left untouched; idempotent no-op when the map is
  empty. New Inv 58 documents the deterministic lifecycle. New E2E tests
  `test/test-record-decomposition.py` (linkage round-trips + schema 1.3.0
  validation) and `test/test-close-decomposed-parents.py` (all-children-closed
  -> parent closed + key dropped; one-open-child -> untouched; empty map ->
  no-op), both wired into `test/run.py`; `test/test-run-post-merge.py` asserts
  the wiring.

- **v0.48.5 — 2026-06-03** — Housekeeping (#695, follow-up of #681, under #639).
  Remove the stale pre-implementation "Current behaviour" scaffolding preamble from
  `docs/spec.md` — the paragraph claiming "The feature directory was scaffolded in
  Phase B of the plan. No scripts, no SKILL.md, and no tests exist yet ... become
  verifiable once Phase C through Phase E merges complete." A #639 behaviour check
  proves it dead: the feature is fully implemented (36+ scripts, a deployed SKILL.md,
  70+ passing tests; "Known gaps" already says "All implementation phases complete").
  The live `## Current behaviour` section header and its behaviour bullets are kept;
  only the false narration paragraph is deleted (REMOVAL, not reword). #681 deferred
  this removal because the contract historical-tags ALLOWLIST was line-number-pinned,
  so a line shift reddened the gate; #696 made that allowlist content-keyed, making
  the removal safe. New E2E regression
  `test/test-spec-housekeeping-695-current-behaviour-preamble-removed.py` (wired into
  `test/run.py`) asserts the dead phrases stay absent.

- **v0.48.4 — 2026-06-03** — Land the gitignore-seeding feature (#691, closes
  #398, authorized by #701). Inv 57 (proactive `.gitignore` seeding is the
  policy; reactive single-file additions are a fallback) is added to
  `docs/spec.md`; the repo-root `.gitignore` gains the per-feature
  `.rabbit-scope-active-*` scope-marker glob (the bare `.rabbit-scope-active`
  token does not match a per-feature `.rabbit-scope-active-<feature>` marker,
  so a stray marker could be committed without the glob). New E2E regression
  `test/test-gitignore-seeded-runtime-artifacts.py` (wired into `test/run.py`)
  copies the repo-root `.gitignore` into a tempdir git repo, writes each
  artifact in the known seed set including a per-feature scope marker, and
  asserts `git status --porcelain` reports none of them. Landed by merging
  `origin/dev` into the PR branch; the only content conflict was the transient
  `feature.json` `spec_no_change_reason` field, removed here since `docs/spec.md`
  does change in this landing (it gains Inv 57). Four version surfaces bumped
  0.48.3 → 0.48.4 in lockstep.

- **v0.48.3 — 2026-06-03** — Housekeeping round 2 (#681, under #639): measured
  dead-prose REMOVAL pass on `docs/spec.md` (the whale; round 1 reworded instead
  of removing). Deleted, each verified DEAD by a deterministic #639 check:
  (1) the "Current behaviour" preamble claiming "No scripts, no SKILL.md, and no
  tests exist yet … become verifiable once Phase C through Phase E merges
  complete" — behaviour check: the scripts/, SKILL.md, and 70+ tests all exist
  and pass; (2) the entire "Open questions (to resolve during Phases C–E)"
  section (6 items, RESOLVED or moot) — the feature is fully implemented and the
  resolved facts already live inline in the relevant invariants; (3) Inv 22's
  "Ownership migration: As of v0.7.5 … does NOT yet call this script … a
  follow-up cycle … will refactor" block and Inv 14's mirror "this invariant
  will be revised to defer line-2 ownership to Inv 22" — cross-feature
  inspection: `contract.lib.runtime.emit_auto_evolve_banner` now delegates to
  `scripts/banner-status.py`, so the follow-up HAS landed; (4) Inv 15's stale
  "current target is `0.4.0` (set during Phase E Task 14)" — live version is
  0.48.3, not 0.4.0; (5) Inv 42's "the steps that the in-session `start`
  sequence used to run before invoking the walk are removed" past-refactor
  narration. The dangling "(resolved Open Question N)" provenance tags left by
  removing the Open-questions section were trimmed (the normative facts they
  cited stay inline). Each surviving invariant keeps its current normative
  statement; only stale/pre-implementation/past-edit narration was deleted.
  Net: spec.md ~3570 → ~3490 lines. Regression-guarded by
  `test/test-spec-housekeeping-681-dead-prose-removed.py`. Four-way version
  lockstep bump (feature.json + spec + contract + SKILL).

- **v0.48.2 — 2026-06-04** — Cross-scope false-positive fix for bare
  feature-NAME mentions (Inv 56(a.2), issue #669; follow-up to #667). A
  single-feature sub-issue (one `feature:` label, edit-paths under ONE feature
  dir) whose descriptive PROSE merely MENTIONS other feature NAMES (e.g. `use
  rabbit-issue vocabulary`, `mirrors rabbit-spec`) was mis-flagged `cross_scope:
  true` because the cross-scope feature-set signal counted bare feature-name
  tokens; plan-batch then mis-shaped it `multi-subagent-barrier` instead of
  `parallel-per-feature` (observed live for #420's sub-issues #660–#666, whose
  descriptions say `use rabbit-issue vocabulary`). `triage-issue.py` now derives
  the cross-scope feature-set signal from EDIT-TARGET references ONLY — the
  `feature:` label plus every distinct `.claude/features/<name>/` PATH reference
  (dirs the issue will write under); bare feature-NAME mentions are excluded
  (`_edit_target_features`). `plan-batch.py` treats an EXPLICIT `cross_scope:
  false` as the authoritative single-scope signal, shaping such an item
  `parallel-per-feature` even when its `features` count is inflated by bare-name
  mentions (the `features` list still carries those names for Inv 26 / #443
  visibility). Genuine detection is preserved: a body listing ≥ 2 distinct
  feature EDIT-PATHS still yields `cross_scope: true` (barrier/decomposition), as
  does a bare repo-wide sweep outside a parent-reference line. Spec Inv 56 gains
  sub-section (a.2); `test/test-cross-scope.py` adds a bare-name-mention case
  (cross_scope false → parallel-per-feature) and a ≥2-edit-path case
  (cross_scope true). No contract change; `docs/contract.md` version unchanged.
- **v0.48.1 — 2026-06-04** — Cross-scope false-positive fix for decomposition
  sub-issues (Inv 56(a.1), issue #667). A shape-3 decomposition sub-issue scoped
  to exactly ONE feature typically QUOTES its parent's framing on a
  parent-pointer line (e.g. `Sub-issue of parent #420 (retire B/B terminology
  repo-wide)`); the quoted `repo-wide` phrase previously set `cross_scope: true`,
  so plan-batch mis-shaped the single-feature sub-issue as
  `multi-subagent-barrier` instead of `parallel-per-feature` (observed live for
  #420's sub-issues #660–#666). `triage-issue.py` now strips parent-reference
  lines (matched by `sub-issue of`, `part of #N`, `parent #N`, `child of #N`,
  `decomposed from #N`, `split from #N`, ...) before evaluating the cross-scope
  PHRASE signal, so a quoted parent phrase no longer triggers `cross_scope`.
  Genuine detection is preserved: a body whose OWN scope enumerates ≥ 2 distinct
  feature paths, or instructs `sweep every feature` / `across all features`
  outside a parent line, STILL yields `cross_scope: true`. Spec Inv 56 gains
  sub-section (a.1) documenting the exclusion; `test/test-cross-scope.py` adds a
  sub-issue case (cross_scope false + plan-batch parallel-per-feature) and two
  genuine-detection-preserved cases. No surface change.

- **v0.48.0 — 2026-06-03** — Cross-scope detection + routing (Inv 56, issue
  #433). `triage-issue.py` now emits `cross_scope` (bool) and
  `cross_scope_features` (sorted feature set) on EVERY triage record:
  `cross_scope` is `true` when the issue body implicates more than one feature
  — either the distinct `features` set spans ≥ 2 dirs (the Inv 26 union of
  label + `.claude/features/<name>/` body paths + bare names) OR the body/title
  carries an explicit cross-scope phrase (`repo-wide`, `every feature`,
  `across all features`, `across every feature`, `all features`, `rename
  across`), else `false`. `plan-batch.py` folds the body-derived `cross_scope`
  signal into Stage-2 shaping: a `cross_scope` work item is NEVER shaped
  `parallel-per-feature` (even when its single `feature:` label would mislead
  the planner) — it gets `decomposition` at/above `--decompose-threshold`, else
  `multi-subagent-barrier`. Every `cross_scope` work item is surfaced under the
  new `cross_scope_items` plan output key (sorted, always present). This fixes
  the dispatch-abort-at-first-cross-feature-write class: a body-spanning sweep
  no longer routes to a bounded single-feature subagent that cannot write
  across features. Bounded scope itself is unchanged (Inv 26(d)) — the fix is
  detection + routing, not widening subagent scope. Tests:
  `test/test-cross-scope.py` (triage `cross_scope` true/false cases via gh
  shim; plan-batch shapes a cross_scope item as multi-subagent-barrier /
  decomposition, never parallel-per-feature; `cross_scope_items` surface) and
  `test/test-spec-cross-scope-invariant.py` (spec carries Inv 56). Lockstep
  version bump 0.47.0 -> 0.48.0 across `feature.json`, `docs/spec.md`,
  `docs/contract.md`, and `skills/rabbit-auto-evolve/SKILL.md`.
- **v0.47.0 — 2026-06-03** — Deterministic deployed-surface republish step
  (Inv 55, issue #562). Added `scripts/republish-feature.py`: given a feature
  name (and optional `--repo-root`), it reads that feature's `feature.json`
  `manifest` and INVOKES `contract.lib.publish.<api>(**args, feature_dir=...,
  repo_root=...)` for every `publish_*` entry, refreshing the deployed copies a
  version-bumping TDD subagent cannot write (out-of-scope). Idempotent (no-op
  when deployed already matches source); emits a JSON summary of what was
  (re)published; a feature with no manifest / no publish entries is a clean
  no-op. The cross-scope INVOKE of `contract.lib.publish` is declared in this
  feature's own `docs/contract.md` `invokes.modules` (the contract feature is
  not edited). SKILL.md now documents the post-handoff dispatcher step: after a
  version-bumping subagent returns (or any HANDOFF reporting a changed deployed
  surface), the dispatcher runs `republish-feature.py <feature>` in the
  worktree BEFORE opening the PR, so the deployed copy is in the PR and
  `contract/test/test-deployed-skills-match-source.py` is green. Tests:
  `test/test-republish-feature.py` (fixture-repo e2e: differing copy made to
  match + reported; matching copy no-op; no-manifest clean no-op) and
  `test/test-spec-republish-feature-invariant.py` (spec/contract/SKILL
  documentation guard). Lockstep version bump 0.46.0 -> 0.47.0 across
  `feature.json`, `docs/spec.md`, `docs/contract.md`, and
  `skills/rabbit-auto-evolve/SKILL.md`.
- **v0.46.0 — 2026-06-03** — Housekeeping Phase 2 final step: strict-tier
  opt-in flipped. Set top-level `"housekeeping_clean": true` in `feature.json`,
  enrolling rabbit-auto-evolve in the contract strict tier
  (`test-spec-bodies-no-historical-tags.py`: bare `#NNN` refs, "per issue/bug/PR"
  prose, and `superseded`/`retired`/`obsoleted` tombstone language). The
  v0.45.0 doc-surface scrub (#650) removed all 187 strict-tier hits and the
  contract-owned line-pinned ALLOWLIST entry (#651) suppresses the one
  irreducible status-enum literal — `feature.json.status == "retired"` on the
  Inv-22 triage decision-table row (`docs/spec.md:462`), the verbatim value
  `triage-issue.py` checks. The live strict test now PASSES with the real flag
  set. Data-driven opt-in only: no `docs/spec.md` body change (frontmatter
  lockstep version bump 0.45.0 -> 0.46.0 across `feature.json`, `docs/spec.md`,
  `docs/contract.md`, and `skills/rabbit-auto-evolve/SKILL.md`; line 462 not
  shifted).
- **v0.45.0 — 2026-06-03** — Housekeeping Phase 2: history-free doc surfaces.
  Scrubbed historical-burden tags (bare `#NNN` issue/PR refs, "per issue/bug/PR"
  prose, parenthetical issue trailers, and version-narrative "this invariant was
  introduced by issue #NNN in vX" paragraphs) from `docs/spec.md`,
  `docs/contract.md`, and `skills/rabbit-auto-evolve/SKILL.md` — ~187 strict-tier
  hits removed. Every invariant NUMBER, substantive rule, operational
  instruction, command, and script path is preserved; only the historical
  framing was stripped and rewritten present-tense. Stale-but-live descriptions
  were corrected to current reality (the spec/contract live at the flat `docs/`
  layout, not `specs/`; the `scripts/` surface is on disk, not "Phase C planned").
  Removed the dead "Phase A prerequisites landed in commits …" intro block and
  the "prerequisites landed on dev" Known-gaps bullet (relocated here). The
  strict-tier opt-in flag (`housekeeping_clean`) is NOT yet flipped: one
  irreducible status-enum literal remains — `feature.json.status == "retired"` in
  the triage decision table (Inv-22 rule 4), the verbatim value
  `triage-issue.py` checks — which needs a contract-owned ALLOWLIST entry (the
  #634 precedent for contract/rabbit-config). A follow-up lands the allowlist
  entry and flips `housekeeping_clean: true` together.
- **v0.44.0 — 2026-06-03** — Observability-log attribution: `tick` and
  `session_id` now carry real, deterministic values instead of the stubs
  (`tick:0` / `session_id:''`) that made Inv 37's cross-session attribution
  non-functional (Inv 54, issue #627). `log-tick.py emit` derives both from the
  Inv 35 running marker when the flags are omitted: `session_id` = `pid<n>-<ts>`
  (stable per session) and `tick` = a monotonic per-session counter persisted in
  `<state_dir>/auto-evolve-log-tick.json` (`tick-start` increments, other kinds
  reuse it). The marker source is injectable via
  `RABBIT_AUTO_EVOLVE_RUNNING_MARKER` so the derivation is deterministic under
  test. Explicit `--tick` / `--session-id` are still honored verbatim.
- **v0.43.0 — 2026-06-03** — Tick-start orphan sweep that bounds disk usage
  from parallel TDD dispatch (Inv 53, issue #628). Parallel dispatch
  (worktree isolation, #430) creates one `agent-*` git worktree per subagent
  under `.claude/worktrees/`; the Agent tool only auto-removes an UNCHANGED
  worktree on exit, so changed TDD worktrees are never removed and accumulate
  (61 leftover / 577 MB observed), and `.rabbit/prompts/` grew unbounded
  (264 files / 23 MB observed). New `scripts/prune-worktrees.py` runs in
  `run-tick-phases.py`'s pre-dispatch segment (BEFORE Phase 5 dispatch — at
  tick start no dispatch is live, so every existing `agent-*` worktree is an
  orphan and safe to force-remove). The sweep `git worktree remove --force`s
  every `agent-*` worktree under `.claude/worktrees/` then `git worktree
  prune`s; it NEVER touches the main checkout, a non-`agent-*` path, or a
  path outside `.claude/worktrees/`, is a clean no-op with no orphans, and
  never fails the tick on a sweep error (disk hygiene must never block
  evolution). The same step bounds `.rabbit/prompts/` by INVOKING the
  contract-owned `contract.lib.runtime.cleanup_old_prompts(max_age_days=7,
  repo_root=...)` API (cross-scope INVOKE declared in `docs/contract.md`
  `invokes.modules`; rabbit-auto-evolve does NOT edit the contract feature).

- **v0.42.0 — 2026-06-03** — New advisory-restart marker
  `.rabbit-auto-evolve-restart-advised` and its lifecycle script
  `scripts/advise-restart.py` (Inv 52, issue #545, Part A). This is a
  structured, persistently-surfaced restart signal that mirrors the hard
  `.rabbit-auto-evolve-restart-needed` marker but is ADVISORY — it never
  pauses, blocks, holds, or auto-resumes the loop. `advise-restart.py write
  "<reason>"` writes the marker with a structured reason (latest reason wins,
  overwrites if present); `advise-restart.py status` emits
  `{"advised": true, "reason": "..."}` when present and `{"advised": false}`
  when absent (always exit 0), mirroring `check-auto-resume.py`'s invoke
  surface so rabbit-cage's Stop/SessionStart dispatcher (Part B, separate
  feature, same branch) can surface the advisory line cross-feature;
  `advise-restart.py clear` removes the marker idempotently so SessionStart
  can clear it after the advised restart occurs. The read/clear invoke
  surfaces are declared in `docs/contract.md` `provides.scripts` so Part B's
  cross-scope use is contract-bound. The advisory path NEVER touches the hard
  `.rabbit-auto-evolve-restart-needed` marker. Marker added to the spec
  Markers list + table and `contract.md` `manages.runtime_markers`; the
  repo-root `.gitignore` glob `.rabbit-auto-evolve-*` already covers it.
  Regression covered by `test/test-advise-restart.py` and
  `test/test-spec-advise-restart-invariant.py`. `advise-restart.py` → v1.0.0;
  no SKILL.md change.

- **v0.41.0 — 2026-06-03** — `classify-merge-restart.py` (Inv 8, the 3-rung
  catch-up ladder) now classifies a merged PR touching `.claude/agents/*.md`
  (agent definitions) as `restart` — for BOTH pure-adds AND modifications
  (#537). Claude Code loads agent definitions at session start, so any change
  to an agent def — added or edited — does not take effect until the session
  is restarted, which is exactly the `restart` rung's purpose. Previously such
  changes fell through to `no-op`, silently dropping the catch-up. New
  sub-rule (d) on the `restart` rung; unlike the SKILL.md pure-add rule (b),
  agent-def modifications also trigger restart since the existing definition is
  already loaded into the running session. Inv 8 amended; regression covered
  by `test/test-classify-merge-restart.py` scenarios D2 (add) and D3 (modify).
  `classify-merge-restart.py` → v1.1.0; no SKILL.md change.

- **v0.40.0 — 2026-06-03** — `triage-issue.py` now emits `issue_type` and
  `created_at` on every triage record so the #441 computed-priority score's
  bug-vs-enhancement and age signals are non-zero (Inv 51, #606). Before
  this, `plan-batch.py`'s `_computed_score` (Inv 46) read
  `item.issue_type == "bug"` and `item.created_at`, but triage never emitted
  either field — so both signals were silent dead letters contributing
  `0.0`, collapsing the score to the filer/fanout/scope subset.
  `issue_type` is derived from the issue's GitHub `bug`/`enhancement` label
  (bug wins when both are present), read from the labels array gh already
  returns; `created_at` echoes the issue's ISO-8601 UTC `createdAt`, added to
  the field list of the SAME single `gh issue view` call (no new gh round-
  trip). Both are always present (work/defer/close/research), `null` when the
  label/timestamp is absent (contributing zero, no crash). A deterministic
  in-scope completion of #441. `triage-issue.py` → v1.8.0; no SKILL.md
  change.

- **v0.39.0 — 2026-06-03** — `last_merged_sha` / `last_tagged_version` are
  now persisted at the source (Inv 50, #564). After #513 converged phase 10
  on the deterministic re-read-and-validate persist (Inv 40), no phase
  script wrote these two informational state fields: `merge-prs.py` wrote
  only `pending_post_merge` and `release-bump.py` emitted to stdout only, so
  both fields lagged perpetually (live evidence: state stuck at
  `last_merged_sha: da1bb2e` / `last_tagged_version: v1.9.1` after recent
  merges/releases). `merge-prs.py --record-pending` now writes the merge
  commit SHA into `last_merged_sha` in the same atomic read-modify-write
  that updates `pending_post_merge`; `release-bump.py` writes the cut tag
  into `last_tagged_version` on the `released` status via the identical
  pattern. Phase 10's re-read (`update-state.py`) then captures both off
  disk — never dispatcher hand-set (the #513 anti-pattern Inv 40 forbids).
  A non-success (skipped/failed merge or release) leaves the field
  untouched. These fields are informational (surfaced by
  `status-report.py`), not control-critical.
- **v0.38.1 — 2026-06-03** — Refire one-shots no longer accumulate (Inv 49,
  #559). Every tick's phase 11 scheduled an immediate-refire one-shot (Inv 33)
  but nothing cancelled a prior pending refire, so overlapping/retried ticks
  piled up refires that fired together (an observed double-fire at a
  non-heartbeat minute). The refire one-shot's prompt now carries a
  recognizable refire marker (`/rabbit-auto-evolve tick #refire`) while the
  recurring heartbeat keeps the bare `/rabbit-auto-evolve tick`, so refires
  are distinguishable from the heartbeat. `schedule-decision.py` exposes a
  pure, unit-testable `is_refire_oneshot(entry)` predicate (marker present AND
  non-recurring AND non-durable) and, on the `immediate-refire` decision,
  emits a `dispatcher_actions` block computed from the injected `CronList`
  snapshot (env `RABBIT_AUTO_EVOLVE_CRON_LIST`): the prior refire ids to
  `CronDelete` (`delete_refire_ids`), the heartbeat ids to PRESERVE
  (`preserve_heartbeat_ids`, never deleted), and the single refire to
  `CronCreate` (`create_refire`). The dedup targets refire one-shots ONLY and
  never removes the recurring heartbeat. SKILL.md "Scheduling" gains the
  emitted `dispatcher_actions` contract shape.
- **v0.38.0 — 2026-06-03** — `release-bump.py` reads the closing issue's
  priority when the PR carries none (Inv 48, #529). The dispatch flow opens
  PRs WITHOUT copying the source issue's `priority:<level>` label, so the
  Inv 7 bump table saw no priority on the PR and always patch-bumped —
  minor/major signals never reached the version stream. `release-bump.py` now
  resolves the priority in strict precedence: an explicit priority label ON
  the PR still wins (unchanged); when the PR has none, it resolves the closing
  issue from the PR body (`Fixes|Closes|Resolves #N`, case-insensitive) and
  reads that issue's `priority:<level>` label via
  `gh issue view <N> --json labels`; if neither the PR nor a resolvable
  closing issue has a priority label, it keeps the existing `patch` default.
  The lookup is a single bounded `gh issue view` call, skipped entirely when
  the PR already has a priority label or a major trigger fires. Deterministic
  (script-tier, no LLM inference); no dispatcher prose change needed.
- **v0.37.0 — 2026-06-03** — Post-merge re-sync to `origin/dev` before the
  release drain (Inv 47, #516). `run-tick-phases.py run_post_dispatch` now
  fast-forwards the local `dev` checkout to `origin/dev` (reusing
  `sync-tree.py` — `git pull --ff-only`, never `git merge`) AFTER the Phase-6
  remote squash-merge reports merged PRs and BEFORE the phases 7-9
  `run-post-merge.py` / `release-bump.py` drain. Previously the release phase
  ran on the STALE local `dev` (lagging `origin/dev` after the remote merge),
  so `release-bump.py`'s safety-check / next-tag computation saw stale state
  and SKIPPED the release on the FIRST in-loop attempt — relying on the #512
  next-tick retry. Now the first attempt runs on fresh state and succeeds.
  Gated on actual merges (zero merges → no re-sync, a harmless no-op); a tree
  that cannot be fast-forwarded aborts the tick before the drain, inheriting
  Inv 38's dirty-tree / non-ff refusal.
- **v0.36.0 — 2026-06-03** — The loop computes its OWN priority score rather
  than blindly trusting the filer-set `priority:` label (Inv 46, #441).
  `plan-batch.py` now blends deterministic, observable signals — blocking-fanout
  (count of OTHER batch items blocked-by this issue, weight 0.30),
  filer `priority:` label (0.15), scope size (smaller = boost, 0.10),
  bug-vs-enhancement (0.05), and age (0.05) — into a `computed_score` in [0, 1]
  that is the PRIMARY Stage-1 ordering key, refining the issue #479 composite
  key (the contract-touch barrier is preserved as the SECONDARY tiebreak, issue
  asc as the final tiebreak). The filer label is one input among several, no
  longer the sole determinant, so a mislabeled or stale-priority issue is
  ordered sensibly. The score is computed in a script (script-tier, no LLM
  inference, no gh/git/fs reads) and emitted under a `computed_scores` map for
  transparency. The recurrence-count and test-coverage-delta signals proposed in
  #441 are NOT deterministically computable in the pure JSON processor and are
  deferred (recorded as discovered issues). Enforced by `test/test-plan-batch.py`
  (fanout ordering, bug-outranks-enhancement, equal-signals determinism,
  transparency, score-tier barrier preservation) and
  `test/test-spec-priority-score-invariant.py`.
- **v0.35.0 — 2026-06-03** — Broaden the SKILL.md `description:` trigger
  enumeration to recognize common natural phrasings (Inv 45, #415): the
  unhyphenated "auto evolve" spelling, the "enter auto[-]evolve mode" framing,
  an enable/turn-on autonomous phrasing ("turn on / enable autonomous evolve"),
  and "resume the loop", in addition to the pre-existing canonical triggers.
  Description-coverage only — skill behavior is unchanged; the description stays
  a single coherent paragraph per the SKILL.md authoring standard. Enforced by
  `test/test-skill-description-triggers.py`. skill-creator validation deferred
  (description-accuracy only, behavior unchanged) per the dispatch note.
- **v0.34.0 — 2026-06-03** — Extend the Inv 43 pre-merge cleanup to detect and
  restore a leaked main-HEAD branch switch (Inv 44, #596). Same root cause as
  #583 (a subagent's process cwd is sometimes the MAIN checkout under worktree
  isolation), but a more severe symptom: a subagent's `git checkout -B <branch>
  origin/dev` switches the dispatcher's MAIN HEAD onto a feature branch, so
  safety-check Inv 1 ("branch is dev") fails and `merge-prs.py` skips the whole
  batch with a CLEAN tree (not the #583 file-leak path). As its FIRST step,
  `scripts/clean-dispatch-leaks.py` now restores HEAD to `dev` via `git checkout
  dev` when the tree is clean and the branch has no un-pushed unique commits
  (the feature work lives on its pushed branch), and logs it; if the tree is
  dirty or the branch has un-pushed unique commits it REFUSES loudly (non-zero,
  tick aborts per Inv 20) and never discards the work. The existing #583
  leak-class cleanup is unchanged and runs after the branch restore.
- **v0.33.0 — 2026-06-03** — Add a deterministic, defense-in-depth pre-merge
  cleanup of KNOWN worktree-dispatch leak-class noise (Inv 43, reopened #583).
  Worktree-isolated Phase 5 dispatches sometimes leak a stray
  `.rabbit-scope-active-<feature>` marker or a bookkeeping-only
  `<feature>/feature.json` edit into the dispatcher's MAIN tree (a harness
  cwd limitation the #589 cwd-based `_repo_root` fix reduced but did not
  eliminate), tripping safety-check Inv 5 so `merge-prs.py` skipped the whole
  batch. New `scripts/clean-dispatch-leaks.py` removes untracked stray
  `.rabbit-scope-active-*` markers and restores ONLY a `feature.json` whose
  diff touches solely loop-bookkeeping keys, and `run-tick-phases.py`
  `run_post_dispatch` invokes it as the FIRST action of Phase 6, before merge.
  Any UNEXPECTED tracked change makes the cleanup refuse non-zero (the tick
  aborts, Inv 20) — a genuine uncommitted change is never destroyed. Cleanup
  is logged via `tick-log.py` (Inv 36). Four-way version bump in lockstep.

- **v0.32.0 — 2026-06-03** — Relocate the feature's documentation surfaces to
  the flat `docs/` layout shared workflow-wide (#399 Phase 2b):
  `specs/spec.md` → `docs/spec.md`, `specs/contract.md` → `docs/contract.md`,
  and the root `CHANGELOG.md` → `docs/CHANGELOG.md`. The existing `docs/bugs/`
  directory is preserved as a sibling of the relocated doc files; the now-empty
  `specs/` directory is removed. The contract resolver's coexistence window
  (flat `docs/` preferred, `specs/` fallback) keeps cross-feature spec
  resolution green during and after the move. Spec and contract bodies are
  unchanged; only the four-way version (`feature.json`, `docs/spec.md`,
  `docs/contract.md`, source `SKILL.md`) advances in lockstep.

- **v0.31.0 — 2026-06-03** — Fix #565 (the in-session `start` false-skipped
  the whole tick on the loop's OWN fresh start-loop marker). After #513 the
  in-session `start` sequence was running-guard (passes) → `start-loop.py`
  (writes `.rabbit-auto-evolve-running`) → "run one tick" =
  `run-tick-phases.py pre-dispatch`. But pre-dispatch internally re-ran
  `running-guard.py` (Inv 35), which then saw the loop's OWN fresh live-PID
  marker and returned `{action: "skip", reason: "tick-running"}` — so the walk
  false-skipped the entire tick on the marker the loop itself had just written.
  The headless path was unaffected (no separate start-loop step before
  pre-dispatch). The guard and the marker write were sequenced in the wrong
  order across the "Start the loop" steps and the pre-dispatch segment.
  - The running-marker write now lives in the shared phase-walk
    (`run-tick-phases.py`, 1.0.0 → 1.1.0): pre-dispatch runs the running-guard
    FIRST and, ONLY after it returns `proceed`, writes
    `.rabbit-auto-evolve-running` (the durable owner-PID + ISO-8601 timestamp
    content for the Inv 35 guard). Because the marker is written AFTER the
    guard, neither the in-session nor the headless path false-skips on a marker
    it itself wrote. Concurrency protection is preserved: a FRESH marker from a
    DIFFERENT live tick that already exists BEFORE the walk starts still makes
    pre-dispatch skip.
  - `start-loop.py` (1.5.0 → 1.6.0) is now strictly the EXPLICIT USER `start`
    self-heal entry: it keeps ONLY its cancel-stop (Inv 19/41) and
    state-bootstrap, and no longer writes the running marker. The redundant
    pre-walk running-guard + marker-write steps were removed from the SKILL.md
    "Start the loop" sequence (the shared walk owns guard→mark). The
    marker-content shape stays defined in ONE place (`start-loop.py`'s
    `_marker_content`) and is imported by the phase-walk.
  - Start-vs-tick authority preserved (new Inv 42, no regression to #558 / Inv
    41): the explicit user `start` runs `start-loop.py` (cancel-stop +
    bootstrap) BEFORE invoking the walk; a MACHINE-fired `tick` invokes the
    walk DIRECTLY with NO cancel-stop, so a heartbeat can never resurrect a
    halted loop. The shared walk writes ONLY the running marker (after the
    guard), never the stop-cancel. `end-tick.py` still removes the running
    marker on every exit path (Inv 20, unchanged mirror).
  - This is a re-read-from-disk self-modifying migration (Inv 39): no
    coexistence window, no restart marker — it takes effect on the next tick
    after merge + sync. spec.md adds Inv 42, updates Inv 19/20 ownership notes;
    SKILL.md updates the "Start the loop" and "tick (internal)" sections.
    Four-way version bump 0.30.0 → 0.31.0.

- **v0.30.0 — 2026-06-03** — Fix #558 (a user stop did not hold — the cron
  heartbeat resurrected a halted loop). A `stop` writes
  `.rabbit-auto-evolve-stop-requested` and the current tick halts at phase 0,
  but the recurring heartbeat and the immediate-refire one-shot fired
  `/rabbit-auto-evolve start`, and `start-loop.py`'s first action (Inv 19)
  deletes the stop marker and starts a fresh tick — so a MACHINE (cron)
  wake-up inherited the USER-intent `start`'s stop-cancel semantics and the
  loop silently resumed. Every machine wake-up now fires the INTERNAL
  `/rabbit-auto-evolve tick` instead, which respects but never deletes the stop
  marker. The marker is cleared EXCLUSIVELY by an explicit user `start`. A
  user stop now HOLDS across heartbeats until the user explicitly resumes
  (new Inv 41). Concretely: `schedule-decision.py` (1.0.0 → 1.1.0) emits
  `prompt`/`croncreate.prompt` of `/rabbit-auto-evolve tick`, and
  `install-cron.py` (1.1.0 → 1.2.0) emits `prompt: "/rabbit-auto-evolve tick"`
  in its restricted-host `CronCreate`-fallback heartbeat signal (the crontab
  path already fired the headless `tick-headless.py`, unchanged). SKILL.md
  documents the `tick`-not-`start` machine-wake-up routing and the stop-hold
  guarantee. Guarded by the new `test/test-stop-holds.py` (e2e) plus updated
  assertions in `test/test-schedule-decision.py` and `test/test-cron-trigger.py`.
  NOTE: the already-running durable heartbeat `CronCreate` job must be recreated
  by the dispatcher to fire `tick` (runtime migration, out of this cycle's
  scope).

- **v0.29.0 — 2026-06-03** — Fix #513 (converge the in-session tick on the
  scripted phase-walk): the in-session tick's Phase 10 persist no longer
  requires the dispatcher to read `update-state.py` source + the schema and
  hand-assemble the full new-state JSON by LLM inference. The deterministic
  tick phases now live in ONE shared scripted implementation,
  `scripts/run-tick-phases.py`, which BOTH the headless tick
  (`tick-headless.py`) and the in-session tick invoke. The walk runs in two
  segments — `pre-dispatch` (tick-start sync, phase 0/1 short-circuit,
  running-guard, phases 2-4) and `post-dispatch` (phase 6 merge, phases 7-9
  post-merge, phase 10 persist) — and the in-session path differs from the
  headless path ONLY by inserting Phase 5 (dispatch, the one phase needing
  Claude) between them. Phase 10 persist re-reads the on-disk state (already
  mutated by the phase scripts), drops the transient `merge_ready` key, and
  pipes the object through `update-state.py`, identically in both paths — every
  in-session phase handoff is script-to-script, none hand-assembled.
  `tick-headless.py` (1.1.0 → 2.0.0) was refactored to delegate to the shared
  walk's `run_pre_dispatch` / `run_post_dispatch` functions, so there is exactly
  one phase-walk implementation. Added spec invariant **Inv 40** (the next
  monotonic number in this feature's `## Invariants` section). Per the Inv 39
  self-modifying-migration playbook this is a re-read-from-disk migration: no
  coexistence window, no restart — it takes effect on the next tick after merge
  + sync. New tests: `test/test-run-tick-phases.py` (e2e per-segment walk),
  `test/test-tick-persist-convergence.py` (the in-session path persists
  byte-identical state to the headless tick for the same on-disk mutations), and
  `test/test-spec-scripted-phase-walk-invariant.py`. Updated `SKILL.md` to
  describe the in-session tick as the scripted phase-walk (dispatcher supplies
  only Phase 5). Versions bumped 0.28.0 → 0.29.0 in lockstep across
  feature.json, specs/spec.md, skills/rabbit-auto-evolve/SKILL.md, and this
  CHANGELOG.

- **v0.28.0 — 2026-06-03** — Feat #450 (self-modifying migrations): replaced
  the residual human a/b/c escalation for "self-modifying migrations" (work
  that changes loop-critical runtime state the loop itself depends on — a
  marker the tick driver reads, an agent type the loop dispatches, a resolved
  path, or a schema/config key it loads) with three deterministic
  safe-execution patterns chosen by HOW the loop consumes the state. Added spec
  invariant **Inv 39** (the next monotonic number in this feature's
  `## Invariants` section) naming the self-modifying-migration category, the
  three patterns (coexistence-window / last-tick-action / restart-safe), the
  consumption-based decision rule, and the "restart-required is signaled via
  the `.rabbit-auto-evolve-restart-needed` marker, never a human stop" rule.
  Added a data-driven registry
  `scripts/schemas/self-modifying-migration-registry.json` mapping known
  markers, resolved paths, agent types, and config keys to a consumption type
  (with a documented fallback heuristic: markers & paths →
  disk-each-tick/coexistence; agent types & session config →
  memory-at-start/restart-safe). Extended the Stage-2 classifier in
  `scripts/plan-batch.py` (1.3.0 → 1.4.0) to detect a self-modifying migration
  per work item, tag the chosen pattern in the new `self_modifying_migrations`
  output key, and list restart-safe items under the new `restart_needed` key —
  `plan-batch.py` stays a pure JSON processor (writes no marker; the tick
  driver sets the restart marker for `restart_needed` items via
  `mark-restart-needed.py`, Inv 17). New tests:
  `test/test-self-modifying-migration.py` (e2e),
  `test/test-self-modifying-migration-registry.py`, and
  `test/test-spec-self-modifying-migration-invariant.py`. Versions bumped
  0.27.1 → 0.28.0 in lockstep across feature.json, specs/spec.md,
  specs/contract.md, skills/rabbit-auto-evolve/SKILL.md. No contract
  `provides`/`reads`/`invokes`/`never` schema change — the registry and the new
  plan-batch output keys are internal to rabbit-auto-evolve.
  NOTE: the originating issue's instruction to number the invariant "Inv 66"
  reflects the *contract* feature's invariant namespace; this feature's
  `## Invariants` section is locally numbered and 38 was the prior highest, so
  39 is the correct next monotonic number (no gap, no renumber). See the
  dispatcher's discovered-issues handoff.

- **v0.27.1 — 2026-06-03** — Fix #542 (TOMBSTONE — Decision B): `specs/spec.md` carried DUPLICATE invariant numbers — two `29.` and two `31.` — because the two `[SUPERSEDED by Inv 32 — issue #414.]` tombstones (the old ScheduleWakeup `schedule-check` invariant and the old ScheduleWakeup queue-emptiness delay-tuning invariant) kept their original `29.`/`31.` numbers ahead of the live invariants that re-used those numbers. That made the `## Invariants` sequence non-monotonic (…,28,**29,29**,30,**31,31**,32,…) and turned contract's cross-feature `test/test-check-invariant-monotonic-order.py` RED on `dev` with `29 → 29 not monotonic` and `31 → 31 not monotonic` violations. **Fix (Decision B — delete the superseded blocks rather than renumber):** both `[SUPERSEDED by Inv 32 — issue #414.]` invariant blocks were DELETED in full from `specs/spec.md` — (a) the old `29.` ScheduleWakeup schedule-check block (which had retained the historical `schedule-check.py` / `delaySeconds` / `/rabbit-auto-evolve tick` re-invoke text now superseded by the cron model), and (b) the old `31.` ScheduleWakeup queue-emptiness delay-tuning block. After deletion the live `29. status-report.py` (#405) and `31. check-auto-resume.py` (#424) invariants remain as the SOLE holders of 29 and 31, so the sequence is strictly increasing again (…,28,29,30,31,32,…) with NO numbering gap — the numbers are retained by the surviving invariants. No live invariant was renumbered; the real 29/30/31/32 blocks are untouched. `ScheduleWakeup`/`/loop` remain documented (only) as FORBIDDEN inside the live Inv 32, so `test/test-spec-cron-invariant.py` stays green. The full rabbit-auto-evolve suite stays green and contract's `test/test-check-invariant-monotonic-order.py` no longer reports the 29→29 / 31→31 violations. Versions bumped 0.27.0 → 0.27.1 in lockstep across feature.json, specs/spec.md, specs/contract.md, skills/rabbit-auto-evolve/SKILL.md (frontmatter only — no skill surface change; the change is a spec-text correction). No contract `provides`/`reads`/`invokes`/`never` schema change — the fix is internal spec hygiene.

- **v0.23.0 — 2026-06-03** — Fix #521 + #509 (CRITICAL): canonical loop work-model + **CronCreate-fallback scheduler**, with #509's two-tier Inv 32 amendment folded in. Implements the ratified D1–D4 state machine. **D1 immediate fresh-context refire:** at the end of a tick (and at a heartbeat) the loop schedules the next tick to fire near-immediately (~1 min) in a FRESH Claude context as a ONE-SHOT when the queue is non-empty, then ends the turn (NOT inline continuation; each fired tick is a full in-session tick incl. phase 5); when the queue is empty it schedules nothing and relies on the heartbeat. **D2 scheduler detection:** system `crontab` WHERE AVAILABLE, durable `CronCreate` fallback where crontab is blocked. `CronCreate` is the Claude idle-REPL prompt scheduler (durable, persists to `.claude/scheduled_tasks.json`) — NOT `/loop`, NOT `ScheduleWakeup` (both stay FORBIDDEN). **D3 stale-marker running-guard:** a STALE `.rabbit-auto-evolve-running` marker (mtime older than the max-tick window, or a dead owner PID) is cleared and logged so the loop never wedges silently. **D4 logged decisions:** every heartbeat/guard/schedule decision is logged. **CRITICAL boundary:** `CronCreate` is a Claude TOOL — a script cannot call it; scripts own detection/guard/logging/decision, the DISPATCHER (via SKILL.md) performs the `CronCreate(...)` tool action (exactly like phase 5 dispatch). **New scripts:** `detect-scheduler.py` (1.0.0, D2 — probes `crontab -l` via `RABBIT_CRONTAB_CMD`, emits `{scheduler, reason}`); `running-guard.py` (1.0.0, D3 — proceed/skip + stale-clear via mtime/PID, `RABBIT_AUTO_EVOLVE_MAX_TICK_SECS` override); `tick-log.py` (1.0.0, D4 — minimal append-only JSON-per-line logger to `.rabbit/tick.log`; full verbosity config is #404's scope); `schedule-decision.py` (1.0.0, D1 — counts open work authoritatively via `fetch-queue.py`, reads the mechanism from `detect-scheduler.py`, emits `immediate-refire` vs `idle`, logs the decision). **Modified:** `install-cron.py` (1.0.0 → 1.1.0): on a crontab-restricted host it no longer prints only the #507 sysadmin message — it emits a machine-readable `{"scheduler":"croncreate","action":"dispatcher-must-create-heartbeat","cron":"13,43 * * * *","prompt":"/rabbit-auto-evolve start","durable":true}` signal (heartbeat avoids the :00/:30 marks per CronCreate guidance) plus a branded line that the durable CronCreate heartbeat will be set up on the next `start`; `start-loop.py` (1.3.0 → 1.4.0): the running marker content now records `pid=<n> ts=<iso> session` for the D3 PID-liveness check (existence-based readers — `status-report.py`, `end-tick.py` — are unaffected; they key on the filename). **Spec:** Inv 32 AMENDED IN PLACE (additive, per spec-rules §3 — not deleted): two-tier model (housekeeping tick never self-chains, `tick-headless.py`; development tick re-triggered by the scheduler firing `/rabbit-auto-evolve start` in a fresh context) and the crontab-or-CronCreate mechanism + sanctioned fallback, cross-referencing #414/#509/#521; new **Inv 33–36** document D1–D4. **SKILL.md (source feature-dir copy only):** phase 11 is no longer a pure no-op — it runs `schedule-decision.py` and the dispatcher schedules the refire (CronCreate one-shot, or crontab transient hint); `on` describes detection + the idempotent durable-heartbeat creation (check `CronList` first); `start` runs `running-guard.py` first; the deprecated wakeup/loop mechanisms are kept OUT of the SKILL entirely. **Test surgery:** `test/test-spec-cron-invariant.py` rewritten — `ScheduleWakeup`/`loop` still forbidden in spec + BOTH SKILL.md copies, `CronCreate` now REQUIRED present in the SOURCE spec.md + SOURCE feature-dir SKILL.md as the documented fallback; the DEPLOYED copy is NOT asserted for CronCreate presence (out of scope; lags until redeployed under #511 — comment cites it). `test/test-cron-trigger.py` scenario F updated to assert the croncreate-fallback JSON signal + branded notice instead of the old `*/30` sysadmin message. `test/test-loop-markers.py` updated for the new running-marker content (contains "session"). **New tests:** `test/test-detect-scheduler.py`, `test/test-running-guard.py`, `test/test-tick-log.py`, `test/test-schedule-decision.py`; `run.py` registers all four. Versions bumped 0.22.0 → 0.23.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md. No cross-feature contract `provides`/`reads`/`invokes`/`never` schema change — the new scripts and the marker-content change are internal to this feature's tick lifecycle; the deployed-SKILL redeploy is #511's concern. NOTE: the pre-existing missing 0.21.0 CHANGELOG entry (#517) and the non-monotonic Inv 29/31 duplicates (#518) are NOT fixed here (out of scope).

- **v0.22.0 — 2026-06-03** — Fix #512 (HIGH): `scripts/run-post-merge.py` (1.0.0 → 1.1.0) treated a release-bump *skip* as a success and silently dropped the owed release with no retry. Phase 7 invoked `release-bump.py <pr#>` and keyed success on `proc.returncode` ALONE, but `release-bump.py` EXITS 0 even when its stdout JSON `status` is `"skipped"` (e.g. safety-check-failed: "no git mutation, exit 0") or `"failed"` — so a skipped release was indistinguishable from a real one; `run-post-merge.py` proceeded to cleanup/catch-up and cleared `pending_post_merge`, dropping the owed release with NO retry (the exact silent-drop class #499 set out to eliminate). OBSERVED live on PR #510: release-bump inside run-post-merge returned rc0 but created no tag; a manual re-run released v1.0.7 with identical repo state. **Fix (minimal/surgical):** phase 7 now parses `release-bump.py`'s captured stdout JSON and keys success on `status == "released"` (in addition to exit 0). A release whose `status` is `"skipped"`, `"failed"`, or whose stdout is unparseable is treated as a NON-success: the run sets the result `status` to `"failed"`, includes the offending release JSON, does NOT proceed to cleanup/catch-up, does NOT clear `pending_post_merge`, and EXITS NON-ZERO — leaving the owed work INTACT so the next tick's phase-1.5 tick-start drain retries it (matching the documented "a phase failure exits non-zero and leaves `pending_post_merge` intact" contract; per SKILL.md a non-zero `run-post-merge.py` exit is an Inv 20 error-abort the dispatcher surfaces). The all-released happy path is unchanged. The deeper root cause of WHY safety-check skipped on the first invocation is out of scope (noted in #512 for separate investigation); this fix is narrowly: stop treating a skip as success. Spec **Inv 30** (run-post-merge / post-merge phases) updated to state that the release phase keys success on `release-bump`'s `status` field (not merely exit code) and leaves `pending_post_merge` intact on a skipped/failed release. **Tests:** `test/test-run-post-merge.py` gains a release-skipped scenario — a fake `release-bump.py` shim emitting `{"status":"skipped"}` with exit 0 makes `run-post-merge.py` exit non-zero, NOT invoke cleanup/catch-up, NOT clear `pending_post_merge`, and report result `status: "failed"`; the shim helper now lets the release shim emit stdout and the all-released happy path explicitly emits `{"status":"released"}`. Versions bumped 0.21.0 → 0.22.0 across feature.json, specs/spec.md, specs/contract.md, skills/rabbit-auto-evolve/SKILL.md (lockstep — no SKILL surface change; the status-keying is internal to `run-post-merge.py`, so no `publish_skill` republish beyond the version bump). No contract `provides`/`reads`/`invokes`/`never` schema change — `status` is read from `release-bump.py`'s already-in-scope stdout.

- **v0.21.0 — 2026-06-03** — Fix #507: `scripts/install-cron.py` (1.0.0 → 1.1.0) now degrades gracefully on a host where the `crontab` binary is administratively restricted instead of failing opaquely. After #414 made system cron the sole tick scheduler, a `set-evolve-mode.py on` (or a direct install) on a restricted host hit a permission denial from `crontab -l` / `crontab -` and surfaced an opaque non-zero failure, so the mode flip looked broken even though the loop can still run via the manual in-session `/rabbit-auto-evolve start` path. **Fix:** `install-cron.py` distinguishes a genuine permission denial on the read or write (the restricted-host case) from the legitimate empty "no crontab for user" case, and on detecting restriction EXITS 0 with an actionable `rabbit_print` message — it states that crontab is restricted, that the loop will not auto-tick headlessly on this host, prints the exact `*/30` sysadmin entry to install manually, and points the user at the `/rabbit-auto-evolve start` manual path. Cron remains the SOLE tick scheduler where available (Inv 32 unchanged in substance); the fallback covers ONLY the restricted-host case so a mode flip is never blocked by an un-installable cron. The message uses the contract `rabbit_print` renderer (no hardcoded ANSI/brand, per contract Inv 48). The `RABBIT_CRONTAB_CMD` and `RABBIT_AUTO_EVOLVE_REPO_ROOT` overrides are preserved. Spec **Inv 32** documents the restricted-host graceful fallback. **Tests:** `test/test-cron-trigger.py` gains scenario F (a fake restricted crontab shim that denies permission on read/write — the install exits 0 and emits the restricted-host notice rather than failing); scenarios A–E (install idempotency, uninstall absent-safety, unrelated-line preservation, `--help` smoke) stay green against the injected fake crontab so the real user crontab is never touched. Versions bumped 0.20.0 → 0.21.0 across feature.json, specs/spec.md, specs/contract.md, skills/rabbit-auto-evolve/SKILL.md (lockstep). No cross-feature contract `provides`/`reads`/`invokes`/`never` schema change — the fallback is internal to this feature's cron-install lifecycle.

- **v0.20.0 — 2026-06-03** — Fix #414 (HIGH/ARCHITECTURAL): replace the in-session self-chained `ScheduleWakeup` tick scheduler with a **system-cron external trigger** — the cron is now the SOLE tick scheduler. Before this change phase 11 (`schedule`) re-chained the loop by emitting a `ScheduleWakeup` call from inside a live Claude session (Inv 29 / Inv 31); that coupled the loop's cadence to an open session and made the next tick a Claude-harness side effect that could silently drop (the #409 incident: a dropped wakeup once stalled the loop 5h+ with no error). **Architecture:** a single `*/30` crontab entry runs the new headless tick on a fixed cadence, completely decoupled from any session. **New `scripts/install-cron.py` (1.0.0):** idempotently installs the crontab entry `*/30 * * * * cd <repo_root> && python3 .claude/features/rabbit-auto-evolve/scripts/tick-headless.py >> .rabbit/tick-headless.log 2>&1` via the `crontab -l` (read) + append + `crontab -` (write) pattern — running twice yields exactly one entry; unrelated crontab lines are preserved; the `crontab` binary is resolvable via `RABBIT_CRONTAB_CMD` (tests inject a fake shim) and the repo root via `RABBIT_AUTO_EVOLVE_REPO_ROOT`. **New `scripts/uninstall-cron.py` (1.0.0):** idempotently removes the entry via the `crontab -l | grep -v tick-headless | crontab -` pattern; a safe no-op when the entry — or the whole crontab — is absent. **New `scripts/tick-headless.py` (1.0.0):** the Claude-free tick fired by the cron; walks phase 0 (`stop-check`), phase 1 (`restart-check`), phases 2–4 (`fetch | triage | plan`), phase 6 (`merge-prs.py --record-pending` for the state's `merge_ready` PRs), phases 7–9 (`run-post-merge.py`), and phase 10 (`update-state.py`); it SKIPS phase 5 (`dispatch`, which needs Claude) and phase 11 (`schedule`, a no-op — the cron fires next); a stop/abort marker short-circuits it to a clean no-op; it emits a JSON result with `dispatch: "skipped"`. **`set-evolve-mode.py` (1.2.0 → 1.3.0):** `on` invokes `install-cron.py` after writing the three activation markers; `off` invokes `uninstall-cron.py` before tearing them down — both best-effort (a cron failure does not by itself fail the mode flip). **`ScheduleWakeup` and `CronCreate` are removed entirely** — neither appears in any script or in `skills/rabbit-auto-evolve/SKILL.md`; `scripts/schedule-check.py` and its two tests were deleted. New spec **Inv 32** documents the cron-owned scheduling, the headless/session tick split, and the cron lifecycle; old Inv 29 (schedule) and Inv 31 (immediate refire) are marked SUPERSEDED. **SKILL.md:** phase-11 row is now a no-op, the "Schedule phase" / "Queue-emptiness delay selection" subsections are replaced by "Scheduling is cron-owned (Inv 32)" and "Headless tick (cron)" subsections, the `on`/`off`/`start`/`stop` bodies reference the cron install/uninstall, and every `ScheduleWakeup` / `CronCreate` / `/loop` reference is purged; the deployed copy is republished via the `publish_skill` manifest contract. **Tests:** new e2e `test/test-cron-trigger.py` (install installs exactly one entry + is idempotent; uninstall removes it + is a safe no-op when absent; unrelated crontab lines preserved; `--help` smoke — all against an injected fake crontab so the real user crontab is never touched); new e2e `test/test-tick-headless.py` (the headless tick runs phases 2–4, 6, 7–9, 10 via stub phase scripts and NEVER runs dispatch; stop/abort markers short-circuit; no-ready-PR skips the merge phase; `--help` smoke); new e2e `test/test-spec-cron-invariant.py` (Inv 32 spec text present AND neither SKILL.md copy contains any `ScheduleWakeup` / `CronCreate` / `/loop` reference and both document cron-owned scheduling + the headless tick); `test/test-set-evolve-mode.py` gains scenario I (a fake-crontab-backed assertion that `on` installs and `off` removes the tick-headless entry) and injects a fake crontab on every script run so the suite never mutates the real crontab; `test/test-tick-skill.py` now asserts SKILL.md has NO `ScheduleWakeup` and documents the cron; the obsolete `test/test-schedule-check.py` and `test/test-spec-schedule-invariant.py` were removed; `run.py` updated. Versions bumped 0.19.0 → 0.20.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (source + deployed). No cross-feature contract `provides`/`reads`/`invokes`/`never` schema change — the cron entry, the three new scripts, and `merge_ready` are all internal to this feature's tick lifecycle.

- **v0.19.0 — 2026-06-03** — Two HIGH fixes landed in this release.
  - Fix #412 (HIGH): the auto-evolve loop now **refires immediately when the queue is non-empty** instead of always waiting the full hourly cron interval. Before this change the `schedule` phase (phase 11) always used the canonical hourly delay (`delaySeconds=3600`, Inv 29), so a tick that just dispatched work — or that found items still waiting in `state.queue` / `state.in_flight` — sat idle for a full hour before the loop looked again, capping throughput at roughly one batch per hour regardless of how much actionable work was queued. **Fix:** new spec **Inv 31** mandates that phase 11 choose `delaySeconds` from the queue emptiness read from `<state_dir>/auto-evolve-state.json`: when `len(state.queue) > 0 OR len(state.in_flight) > 0` (work remains) use `delaySeconds=60` (the harness minimum — refire immediately) with `reason="queue non-empty, refiring immediately"`; when BOTH `state.queue` AND `state.in_flight` are empty use `delaySeconds=3600` (the hourly idle check) with `reason="queue empty, waiting for new issues"`. A missing/empty/malformed state file is treated as queue-empty (the long idle delay). Both `60` and `3600` are inside the Inv 29 band `60 <= delaySeconds <= 3600`, so `schedule-check.py` accepts either; the `prompt` (`/rabbit-auto-evolve tick`) and the pre-call `schedule-check.py` validation (Inv 29) are unchanged. This invariant REPLACES the single fixed `3600` delay with the two-delay rule. `skills/rabbit-auto-evolve/SKILL.md` gains a "Queue-emptiness delay selection (Inv 31 — issue #412)" subsection (the two delay/reason pairs, the state-file read with its dir resolution, the missing-file conservative idle default, and a `schedule-check.py` example for each case) and the `delaySeconds`/`reason` bullets in the existing schedule section now reference the queue-emptiness rule; the deployed copy is republished via the `publish_skill` manifest contract. `scripts/schedule-check.py` docstring notes that both Inv 31 delays are accepted (no logic change — the validator already accepts the whole `60..3600` band). **Tests:** `test/test-schedule-check.py` gains an Inv 31 regression asserting both `(60, "queue non-empty, refiring immediately")` and `(3600, "queue empty, waiting for new issues")` validate (exit 0 + `ok:true` + matching `delay_seconds`), so neither delay is silently dropped; the end-to-end `test/test-spec-schedule-invariant.py` is extended to assert the Inv 31 spec text (the issue number, both reason strings, the queue-emptiness 60-vs-3600 branch) AND that both the source and deployed SKILL.md phase-11 docs pin BOTH the `60` (queue-non-empty refire) and `3600` (queue-empty idle) cases, both reason strings, and the queue/in_flight emptiness check. Versions bumped 0.18.0 → 0.19.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (source + deployed). No contract `provides`/`reads`/`invokes`/`never` schema change — the delay selection is internal to the tick's schedule phase, reading the already-in-scope state file.
  - Fix #424 (HIGH): make auto-evolve mechanically self-resume on a fresh Claude restart instead of relying on the human reading the SessionStart banner and manually pasting `/rabbit-auto-evolve start`. After a `restart-needed` tick the loop's recovery was convention-enforced: the SessionStart banner (Inv 22 line-2 `resume after restart` variant) told the human to restart Claude and re-run `start`; a missed read silently stalled the loop. Per spec-rules §1 (`script > CLI > spec > prompt`) the resume decision is moved out of human convention and into a deterministic script. New `scripts/check-auto-resume.py` (1.0.0) inspects the runtime markers at the repo root and emits `{"resume": true, "action": "/rabbit-auto-evolve start"}` when — and only when — ALL THREE conditions hold: (1) `.rabbit-auto-evolve-active` present (mode on), (2) `.rabbit-auto-evolve-restart-needed` present (a restart was needed), AND (3) `.rabbit-auto-evolve-running` NOT present (no tick already running); otherwise it emits `{"resume": false, "action": null}`. The script reads files only (`os.path.exists`), never invokes `ls`/`test -f`, resolves the repo root via `RABBIT_AUTO_EVOLVE_REPO_ROOT` (fallback `os.getcwd()`) matching `check-preconditions.py` / `banner-status.py` / `status-report.py`, and exits 0 on every path (the verdict is carried in `resume`). The `.rabbit-auto-evolve-aborted` marker is intentionally NOT consulted — abort handling remains the banner's responsibility (Inv 22); this script answers only the narrow "should we mechanically re-launch the loop after a restart" question. New spec **Inv 31** documents the script, the three auto-resume conditions, the always-exit-0 contract, and the cross-scope INVOKE pattern (rabbit-cage's SessionStart hook should INVOKE this script and surface `action` when `resume` is true). **Tests:** new e2e `test/test-check-auto-resume.py` drives the real script as a subprocess against seeded marker fixtures exactly as the hook will — all-three-met → `resume: true`/`action: /rabbit-auto-evolve start`; active+restart-needed but running present → `resume: false`/`action: null`; active but restart-needed absent → no resume; active absent (mode off) → no resume; clean repo → no resume; `--help` smoke; and a spec-text assertion that Inv 31 documents the three conditions. `run.py` registers it. Versions bumped 0.18.0 → 0.19.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), and skills/rabbit-auto-evolve/SKILL.md source frontmatter (no SKILL surface change — the new script is consumed by rabbit-cage's SessionStart hook, not by the skill, so no `publish_skill` republish was required beyond the lockstep version bump). No contract `provides`/`reads`/`invokes`/`never` schema change — the script is invoked cross-scope BY rabbit-cage (an INVOKE the consumer declares), not a surface this feature provides to others. **DISCOVERED ISSUE (rabbit-cage scope):** the SessionStart hook (owned by rabbit-cage) must be wired to INVOKE `check-auto-resume.py` and, when `resume` is true, emit the `action` so the loop auto-resumes — filed as a companion rabbit-cage touch (not edited here; scope-guard owns `.claude/hooks/`). This is the integration that makes the mechanical resume observable end-to-end at SessionStart.

- **v0.18.0 — 2026-06-03** — Fix #499 (CRITICAL): tick phases 7 (`release`), 8 (`cleanup`), and 9 (`catch-up`) never ran because the LLM-walked tick ended after phase 6 (`merge`). When phase 6 merged a large batch of PRs, the orchestrator ended the tick for scale/context reasons and the prose descriptions of phases 7–9 in `SKILL.md` were silently dropped — the same class of LLM-walked-prose skip as #405/#409/#439, but here it meant releases were never tagged, merged branches never cleaned up, and restart/refresh catch-up never classified. **Fix:** move the phase-7-through-9 sequencing out of prose and into a deterministic, non-skippable script. New `scripts/run-post-merge.py` (1.0.0) reads a new `pending_post_merge` array (merged PR numbers owed post-merge processing) from `.rabbit/auto-evolve-state.json` and runs, IN ORDER, `release-bump.py <pr#>` (phase 7, once per PR) → `cleanup-branches.py <pr-list>` (phase 8, once) → `classify-merge-restart.py <pr#>` (phase 9, once per PR), then clears `pending_post_merge`; an empty/absent list is a clean no-op, and a phase-script failure exits non-zero and leaves `pending_post_merge` intact so the next tick's tick-start drain retries the owed work. **State schema 1.1.0 → 1.2.0:** `scripts/schemas/auto-evolve-state.schema.json` gains the optional `pending_post_merge` (array of int) field — a backward-compatible additive change (states written without it still validate); `update-state.py` (1.1.0 → 1.2.0) and `start-loop.py` (1.2.0 → 1.3.0, default-state bootstrap) recognize it. **merge-prs.py 1.3.0 → 1.4.0:** gains a `--record-pending` flag that appends every successfully-merged PR number (de-duplicated) to `pending_post_merge` after processing the PR list; without the flag the behavior and stdout result array are unchanged. **SKILL.md:** the phase table replaces the prose phase-7/8/9 rows with a single `run-post-merge.py` post-merge row plus a phase-1.5 tick-start drain row, phase 6 now invokes `merge-prs.py --record-pending`, and a new "Post-merge phases (Inv 30)" subsection documents the two invocation points (after phase 6, and at tick start to drain a previous truncated tick) and the error-abort contract; the deployed copy is republished via the `publish_skill` manifest contract. New spec **Inv 30** documents the runner, the `pending_post_merge` field, the `--record-pending` flag, and the SKILL invocation contract; the Inv 9 schema table and the Public-surface scripts table gain the new field/script. **Tests:** new `test/test-run-post-merge.py` (non-empty pending → all three phases invoked in order, release/catch-up once per PR, cleanup once with the comma-joined list, field cleared; empty/missing → clean no-op, status `noop`, no phase invoked; a phase failure → non-zero exit and field NOT cleared; `--help` smoke); new e2e `test/test-spec-post-merge-invariant.py` (asserts the Inv 30 spec text AND that both source and deployed SKILL.md invoke `run-post-merge.py` after the merge phase and at tick start with `--record-pending`); `test/test-merge-prs.py` gains four `--record-pending` regressions (appends merged PRs, de-duplicates, skips non-merged PRs, no state write without the flag); `test/test-state-persistence.py` bumped to schema 1.2.0 with three `pending_post_merge` scenarios (accepted/round-trips, optional/additive, non-int rejected). `run.py` registers both new tests. Versions bumped 0.17.0 → 0.18.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (source + deployed). No contract `provides`/`reads`/`invokes`/`never` schema change — the new script is internal to the tick, and `pending_post_merge` is an internal state field.

- **v0.17.0 — 2026-06-03** — Three HIGH fixes landed in this release.
  - Fix #443 (HIGH): `scripts/triage-issue.py` (1.6.0 → 1.7.0) now detects features referenced by **bare name** in an issue body or title, fixing the Stage-2 cross-feature miss that gave multi-feature issues a single-feature dispatch shape. Previously the `features` set was the union of only (a) the `feature:<name>` label and (b) literal `.claude/features/<name>/` path references; an issue that named features in prose or a markdown table without the full path — e.g. "#416 touches rabbit-auto-evolve, rabbit-issue, rabbit-meta" — was seen as single-feature and got `parallel-per-feature` instead of `multi-subagent-barrier` / `decomposition`. The fix adds a third detection method: `_discover_feature_names()` builds the canonical feature vocabulary by listing `.claude/features/` at triage time (each subdir carrying a `feature.json`, excluding non-feature entries like `policy`), and `_bare_name_matches()` scans the body+title for each name with a word-boundary regex (`\b<name>\b`). The match is whole-word only, so a substring of a longer token (`rabbit-metadata-store`) does NOT pull in the feature `rabbit-meta`. The `features` field is now the union of all three methods. `plan-batch.py` is unchanged — it already derives the dispatch shape from the `features` set length once it is populated correctly. The research classifier (`_is_research`, #478) is intentionally unaffected: it keys off `.claude/features/<name>/` path references only, not the broadened bare-name set, so its over-trigger guard is preserved. Spec Inv 3 `features` field description updated to document the three detection methods and the word-boundary discipline. **Tests:** `test/test-triage-rules.py` gains four E2E regressions — three features named by bare name in prose → 3-feature set; the same in a markdown table (no full paths) → `len(features) == 3`; a bare feature name in the TITLE detected; and a substring of a longer token NOT matched (word-boundary). All pre-existing rule, reconciliation, research, and priority scenarios still pass. Versions bumped 0.16.0 → 0.17.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (frontmatter — no SKILL surface change; the triage record's `features` detection is an internal data-contract mechanic not described in SKILL.md, so no `publish_skill` republish was required beyond the lockstep version bump). No contract `provides`/`reads`/`invokes`/`never` schema change — the feature vocabulary is read from the already-in-scope `.claude/features/` directory listing.
  - Fix #409 (HIGH): the auto-evolve loop silently stopped scheduling — tick 6 ended and five subsequent hourly ticks (`ScheduleWakeup` at :17 past each hour) never fired across a 5h+ window, with NO error, NO log line, and NO halt (the session was alive; it answered `/status` interactively). **Root cause:** the `schedule` phase was under-specified. SKILL.md's phase-11 row documented only the bare string "`ScheduleWakeup` (unless stop-check matched)" and never pinned the three call parameters (`delaySeconds`, `prompt`, `reason`), so the dispatcher had no deterministic instruction on what delay to use or which prompt re-enters the tick — an under-specified call can silently emit nothing, a 0/out-of-range delay the harness ignores, or a prompt that never re-invokes `/rabbit-auto-evolve tick`, every one of which produces exactly the observed silent stall. **Fix:** new spec **Inv 29** mandates that phase 11 (`schedule`) call `ScheduleWakeup` with valid parameters — `delaySeconds` an integer in the inclusive band `60 <= delaySeconds <= 3600` (canonical hourly value `3600`), `prompt` the literal tick-reinvoke string `/rabbit-auto-evolve tick`, and a non-empty `reason` — and that the phase run the new `scripts/schedule-check.py` validator BEFORE emitting the call. `schedule-check.py` (1.0.0) does NOT call `ScheduleWakeup` (a Claude Code harness feature, not a Python function); it validates the LOGIC that determines the call's parameters and exits non-zero with a `{"ok": false, "errors": [...]}` payload on any violation (out-of-range delay, empty/non-re-invoking prompt, empty reason), exit 0 + `{"ok": true, ...}` on valid params. A non-zero validator exit is an error-abort (Inv 20): run `end-tick.py` and surface the failure rather than emit a silently-dropped wakeup — converting the silent-stop failure mode into a loud, locatable one. `skills/rabbit-auto-evolve/SKILL.md` gains a "Schedule phase (Inv 29)" subsection (the three pinned parameters, the canonical `3600`/`/rabbit-auto-evolve tick` values, and the `schedule-check.py` pre-call gate) and the phase-11 table row now references the validator + call; the deployed copy is republished via the `publish_skill` manifest contract. **Tests:** new `test/test-schedule-check.py` (CLI param-validation unit tests: in-range happy path, the 0/59/3601 out-of-range rejections, inclusive 60/3600 boundaries, empty/non-re-invoking prompt rejection, empty-reason rejection, error-payload shape, `--help` smoke) and end-to-end `test/test-spec-schedule-invariant.py` (asserts the Inv 29 text is present in the spec AND that both the source and deployed SKILL.md phase-11 docs pin a concrete in-range `delaySeconds`, the `/rabbit-auto-evolve tick` re-invoke prompt, a `reason`, and the `schedule-check.py` pre-call validation); `run.py` registers both. Versions bumped 0.16.0 → 0.17.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (source + deployed). No contract `provides`/`reads`/`invokes`/`never` schema change — the new script is internal to the tick's schedule phase.
  - Fix #405 (HIGH): the read-only `status` subcommand now has a deterministic backing script instead of an LLM-assembled bash pipeline. Before this change `skills/rabbit-auto-evolve/SKILL.md` described the `status` output in prose, so on every invocation the dispatcher improvised an ad-hoc `ls`/`cat`/`jq` pipeline — a non-deterministic, untestable surface that drifts and emits ugly `ls: cannot access ...: No such file or directory` stderr noise on a fresh clone where the state file and the five runtime markers legitimately do not yet exist. Per spec-rules §1 (`script > CLI > spec > prompt`) this is now a script. New `scripts/status-report.py` (1.0.0) reads ONLY `.rabbit/auto-evolve-state.json` (emitting defaults — queue length 0, empty in-flight, null last-merged/last-tagged, 0 consecutive-failures — when the file is missing, empty, or malformed, which is the legitimate fresh-clone case, NOT an error) and the five runtime markers via `os.path.exists`; it performs no mutations, no `gh`, and no `git`, and resolves the repo root via the `RABBIT_AUTO_EVOLVE_REPO_ROOT` env override (fallback `os.getcwd()`), matching `check-preconditions.py` and `banner-status.py`. It emits a single fixed-format JSON object on stdout (`queue_length`, `in_flight`, `last_merged_sha`, `last_tagged_version`, `consecutive_failures`, `markers_present` — the sorted subset of the five marker basenames present — and `state_file` ∈ {`present`, `absent`, `malformed`}); exit code is 0 on every path including the defaults paths, with non-zero reserved for genuine invocation errors. New spec **Inv 29** documents the read surface, the defaults-on-missing contract, the output schema, the always-exit-0 rule, and the SKILL-must-invoke-not-improvise requirement; the spec Public-surface scripts table gains the `status-report.py` row. `skills/rabbit-auto-evolve/SKILL.md` `status` section is rewritten to invoke `python3 .claude/features/rabbit-auto-evolve/scripts/status-report.py` and forbid bare `ls .rabbit-auto-evolve-*` / `cat .rabbit/auto-evolve-state.json` patterns; the deployed copy is republished via the `publish_skill` manifest contract. **Tests:** new `test/test-status-report.py` covers a known-state fixture (every field matches), missing state file (defaults, `state_file: absent`), malformed state file (defaults, `state_file: malformed`, no crash), marker subset detection (sorted `markers_present`), a `--help` smoke test, and a SKILL-surface assertion (both source and deployed `SKILL.md` invoke the script and contain no bare `ls .rabbit-auto-evolve-*` pattern); `run.py` registers it. Versions bumped 0.16.0 → 0.17.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), and skills/rabbit-auto-evolve/SKILL.md (source + deployed). No contract `provides`/`reads`/`invokes`/`never` schema change — the new script is an internal CLI, not a cross-feature surface.

- **v0.16.0 — 2026-06-03** — Two HIGH fixes landed in this release.
  - Fix #430 (HIGH): formalize **worktree isolation for parallel TDD dispatches** as a binding invariant. The auto-evolve loop's phase-5 dispatch fans out one Agent call per selected work item; when several run in parallel they share the dispatcher's single git working directory, and one subagent's branch checkout reverts another's edits, commits land on the wrong branch, and each subagent's `.rabbit-scope-active-<feature>` marker clobbers the others' (directly observed: 3 of 4 parallel dispatches in one tick collided). New spec **Inv 28** mandates that EVERY Agent call for a TDD-subagent dispatch MUST include `isolation: "worktree"` — a DISPATCHER policy, not a subagent policy (the subagent is isolation-agnostic; the dispatcher requests the isolated worktree). The invariant documents the rationale (a shared git working directory cannot host concurrent branch/HEAD state), that worktrees branch from `dev` HEAD per the `worktree.baseRef: "head"` setting in `.claude/settings.local.json` (not `main`, not a fresh tree), and the known stale-base limitation (the `worktree.baseRef: "head"` setting requires a session restart to take effect; until then a subagent may need to re-branch from `origin/dev` manually — a Claude Code worktree-harness limitation, not fixable from this feature's scope). It formalizes an already-manual practice (the maintainer has been passing `isolation: "worktree"` by hand). `skills/rabbit-auto-evolve/SKILL.md` gains a "Worktree isolation for TDD dispatches (Inv 28)" subsection in the dispatch-shape area and a Red Flags entry ("Never dispatch a TDD subagent without `isolation: \"worktree\"`"); the deployed copy is republished via the `publish_skill` manifest contract. No script behavior change — the isolation parameter lives on the Agent call the dispatcher emits from SKILL.md, which has no rabbit-auto-evolve-owned wrapper script. **Tests:** new `test/test-spec-dispatch-worktree-isolation-invariant.py` asserts the Inv 28 text is present in the spec AND that both the source and deployed SKILL.md document the `isolation: "worktree"` dispatch requirement; `run.py` registers it. Versions bumped 0.15.0 → 0.16.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (source + deployed). No contract `provides`/`reads`/`invokes`/`never` schema change.
  - Fix #400 (HIGH): the auto-evolve loop can now cut its very first release. `scripts/release-bump.py` (1.0.0 → 1.1.0) crashed Phase 7 in any repo with zero git tags: `_prior_tag()` ran `git describe --tags --abbrev=0`, which exits non-zero ("fatal: No names found, cannot describe anything.") on a tag-free repo, and raised `RuntimeError` that propagated out of `run()` → traceback + non-zero exit → Phase 7 silently skipped on every loop iteration (the loop has never tagged a release). The fix makes `_prior_tag()` return `None` instead of raising when `git describe` exits non-zero, and `run()` treats `prior_tag is None` as the first-release case: `next_tag = FIRST_RELEASE_TAG` (`v1.0.0`) regardless of the bump kind (the bump table only governs how an EXISTING version is incremented), then proceeds through the unchanged `safety-check.py --phase release --next-tag v1.0.0` gate (Invariant 4 passes because `v1.0.0` does not yet exist) and the tag/push/`gh release` steps. Once `v1.0.0` exists, subsequent releases bump it per the §9 table exactly as before — the existing-tag path is unchanged. Spec Inv 7 execution-order step 3 now documents the tag-free `git describe` as the non-error first-release case (`prior_tag: null`, `next_tag: v1.0.0`) and reorders the listed steps so `git describe` precedes the safety-check (matching the actual data dependency: the next tag must be known before it can be passed to `--next-tag`); the enforced-tests list gains the zero-prior-tags case. **Tests:** `test/test-release-bump.py` git shim gains a `describe_exit` knob (simulating the tag-free `git describe` exit 128 + stderr), and a new first-release block runs the script against a zero-tag repo for `priority:high` (would-be minor), `priority:critical` (would-be major), and `priority:low` (would-be patch), asserting in every case `prior_tag: null`, `next_tag: "v1.0.0"`, `status: "released"`, and that `git tag` IS invoked (via the shim call log). All pre-existing bump-table, safety-fail, threshold, and happy-path scenarios still pass; no actual tag or release is cut in the test (git/gh/safety-check are all shimmed). Versions bumped 0.15.0 → 0.16.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills); SKILL.md frontmatter bumped for version lockstep (no SKILL surface change — the first-release behavior is internal to release-bump.py and not described in SKILL.md, so no `publish_skill` republish was required beyond the version bump). No contract `provides`/`reads`/`invokes`/`never` schema change.

- **v0.15.0 — 2026-06-03** — Fix #484 (HIGH): `scripts/triage-issue.py` (1.5.0 → 1.6.0) now emits a `priority` field on every triage record, making the #479 priority-primary plan-batch ordering live instead of a dead letter. The label value was already parsed (`priority_label = _label_value(labels, "priority")`) but never added to the output object, so every record arrived at `plan-batch.py` without `priority`; `_sort_key` then mapped all of them to `_NO_PRIORITY_RANK = 4`, collapsing the priority-primary ordering (#479) back to the contract-touch-only tiebreak — the old barrier-overrides-priority bug stayed effective. The fix adds `"priority": priority_label` to the `base` triage dict (echoing the `priority:<level>` label, e.g. `priority:high` → `"high"`; `null` when no `priority:` label is present, e.g. a malformed-labels issue). `plan-batch.py` is unchanged — it already consumes `priority` correctly; it just needed the data to arrive. Spec Inv 3 triage-output schema gains the `priority` field with a note that triage MUST emit it on every record (the omission is exactly the silent-collapse failure this fixes). **Tests:** `test/test-triage-rules.py` gains two regressions (a `priority:high` issue's record contains `priority: "high"`; a no-priority-label malformed issue carries `priority: null` as a present key); new e2e `test/test-triage-priority-flow.py` runs `triage-issue.py` (gh shim) on a high-priority non-contract issue and a low-priority contract issue, pipes the two emitted records into `plan-batch.py`, and asserts the high non-contract item leads `selection_order` with `barrier_first` empty — failing on the pre-fix dead-letter symptom (`selection_order == [low-contract, high-non-contract]`). `run.py` registers the new test. Versions bumped 0.14.0 → 0.15.0 across feature.json, specs/spec.md, specs/contract.md (frontmatter + provides.skills), skills/rabbit-auto-evolve/SKILL.md (no SKILL surface change; the triage record schema is an internal data contract not described in SKILL.md, so no `publish_skill` republish was required beyond the lockstep version bump). No contract `provides`/`reads`/`invokes`/`never` schema change.

- **v0.14.0 — 2026-06-03** — Fix #478 (HIGH): add a non-TDD **research/investigation** deliverable path (the 4th dispatch shape) so the loop stops closing valid research/spike items as `not-planned` (an Inv 25 convergence violation). **Triage classification:** `scripts/triage-issue.py` (1.4.0 → 1.5.0) gains a research classifier that runs AFTER rule 7 would return `work` (alongside the #463 reconciliation; it never overrides a close/blocked/malformed verdict). When ALL three signals hold — a research verb (`study`, `evaluate`, `investigate`, `survey`, `assess`, `recommend`, `compare`, `explore`, whole-word case-insensitive) in the title or body; no concrete code-change target (no extra `.claude/features/<name>/` path beyond the labelled dir and no imperative implement/fix/add phrasing); and the body asks for a recommendation/findings/report/analysis — triage emits `decision=research`, `reason_code=research`, with a non-empty `planning_note` summarizing what to investigate. Research items are NEVER `close-not-planned` (valid) and NEVER `work`/`dispatch` (no code). A normal "implement X" item without a research verb is unaffected (the over-trigger guard). **plan-batch routing:** `scripts/plan-batch.py` (1.2.0 → 1.3.0) adds `research` as the 4th dispatch shape: a `decision == "research"` item is retained (no longer dropped), appears in `selection_order` by the same composite sort, carries `dispatch_shapes[N] == "research"`, and its issue number is listed under a new `research_items` output key — but it NEVER enters `barrier_first` or `groups` (findings edit no code, so the conflict-graph grouping and contract-touch barrier do not apply). The output always carries `research_items` (empty list when none). **Spec:** new Inv 27 (Research/Investigation shape) documenting classification signals, the read-only research subagent, the findings-doc deliverable under `docs/findings/<issue-N>-<slug>.md` committed directly to the feature scope (the `--commit-sha` for the `completed` close), and the "valid research items are NEVER `not-planned`" guarantee; Inv 3 (decision set + new "Research/investigation classification" subsection) and Inv 4 (research routing + `research_items` key) updated. **Tests:** `test/test-triage-rules.py` gains two regressions (study-X findings issue → research, never not-planned; implement-X stays work), `test/test-plan-batch.py` gains a research-routing regression, and new `test/test-spec-research-shape-invariant.py` asserts the Inv 27 text. **DISCOVERED ISSUE (rabbit-issue scope):** `item-status.py close --reason completed` should accept a `--findings-comment-url <url>` alternative to `--commit-sha` for comment-only research deliverables — deferred to a follow-up rabbit-issue touch (not edited here; the committed-doc path reuses the existing `--commit-sha` gate). Versions bumped 0.13.0 → 0.14.0 across feature.json, spec.md, contract.md (frontmatter + provides.skills), SKILL.md (source + deployed copy republished via the `publish_skill` manifest contract). No contract `provides`/`reads`/`invokes`/`never` schema change.

- **v0.13.0 — 2026-06-03** — Fix #463 (CRITICAL): `scripts/triage-issue.py` (1.3.0 → 1.4.0) now reads the FULL comment thread and the issue state reason, and reconciles a correction comment / conflicting retitle that supersedes the original body — previously it read only `title,body,labels,state` and silently implemented the stale original design when an issue was reopened with a correction (the canonical #399 incident: body said `docs/spec/ → specs/`, a correction comment + retitle said the real target was `docs/` with a CHANGELOG, and the loop shipped 13 PRs of wrong work). The `gh issue view` read surface gains `stateReason` and now consumes the `comments` array. A new `_reconcile()` runs AFTER rule 7 would otherwise return `work` (it never overrides a close/blocked/malformed verdict): (1) a comment containing supersession language (case-insensitive: `supersedes`, `correction`, `corrected proposal`, `ignore the original`, `revised scope`, `original body was wrong`) is treated as authoritative — `decision=work` with the `rationale` noting a correction was applied; (2) a reopened issue (`stateReason == "reopened"`) whose title and body declare DIFFERENT target tokens, with no coherent superseding comment, is genuinely ambiguous → `decision=defer`, `reason_code=needs-judgment`, `planning_note="Body and correction comment conflict on target [X vs Y]; need maintainer clarification before dispatch."`; (3) a title/body target conflict on a non-reopened issue resolves to the title (most recent authored intent) with a `work` decision noting the conflict; (4) an actionable issue with no comments and no conflict reconciles to the exact pre-#463 behavior (strict no-regression). Spec Inv 3 read surface updated and a new "Comment-thread reconciliation (issue #463)" subsection + three enforced-scenario bullets added; `test/test-triage-rules.py` gains three E2E regressions (correction-comment → corrected intent; reopened+conflict → defer with both targets named; no-comment/no-conflict → unchanged behavior); all 7 rule rows + ambiguity + defer-planning-note + no-close-completed + contract_touch scenarios still pass. Versions bumped 0.12.2 → 0.13.0 across feature.json, spec.md, contract.md (frontmatter + provides.skills), SKILL.md (source + deployed copy republished via the `publish_skill` manifest contract). No contract `provides`/`reads`/`invokes`/`never` schema change — the added `gh issue view` fields are within the existing triage read surface.

- **v0.12.2 — 2026-06-03** — Fix #479 (CRITICAL): `scripts/plan-batch.py` (1.1.0 → 1.2.0) dispatch ordering now treats **priority as the PRIMARY key and the contract-touch barrier as a SECONDARY tiebreak**. Previously `plan()` partitioned ALL `contract_touch == true` items into `barrier_first` BEFORE applying priority, making the barrier a hard global override: a critical non-contract item lost unconditionally to a low-priority contract item (the real #463-vs-#469 regression). The fix sorts ALL work items once by the composite key `(priority_rank, contract_touch_rank, issue)` — priority desc, contract-touch leading WITHIN a tier, issue asc — and derives `barrier_first` as the LEADING run of contract-touch items in that order (empty when the top item is non-contract); the remainder (from the first non-contract item onward) feeds the unchanged conflict-graph coloring + `--max-parallel` cap. `_sort_key` gains the `contract_touch_rank` term so `selection_order` (Stage 1) and `barrier_first` (Stage 2) are derived from the SAME key and always agree; `contract_touch` is a barrier/conflict property, not a dispatch shape, so Stage-1 shape-blindness is preserved. `dispatch_shapes` is unchanged. Spec Inv 4 (algorithm rewritten to 5 priority-primary steps; enforced-scenarios list gains the priority-over-barrier and same-tier-tiebreak cases), Inv 26(a) (`selection_order` composite-key ordering), and the design-§6 summary bullet updated; SKILL.md `selection_order` description updated. `test/test-plan-batch.py` gains four E2E regressions: critical non-contract beats low contract (barrier_first empty), same-tier contract leads non-contract, the #463-vs-#469 scenario, and selection_order/barrier_first agreement; all six pre-existing scenarios still pass. Versions bumped 0.12.1 → 0.12.2 across feature.json, spec.md, contract.md (frontmatter + provides.skills), SKILL.md (source + deployed copy republished via the `publish_skill` manifest contract). No change to the conflict-graph grouping or cap logic.

- **v0.12.1 — 2026-06-03** — Phase 1 of #336 (rabbit-auto-evolve: check-preconditions dual-read). Issue #336 renames the `human-approval` configurable to `tdd-autonomous` (with a polarity flip) and will rename the live on-disk bypass marker `.rabbit-human-approval-bypass` → `.rabbit-tdd-autonomous`. To avoid breaking the running auto-evolve loop during that rename, this change opens a coexistence window by making the `approval-bypass` precondition reader dual-read: `scripts/check-preconditions.py` (1.0.0 → 1.1.0) replaces the single `APPROVAL_BYPASS_MARKER` constant with `APPROVAL_BYPASS_MARKER_LEGACY` (`.rabbit-human-approval-bypass`) and `APPROVAL_BYPASS_MARKER_NEW` (`.rabbit-tdd-autonomous`); `_check_approval_bypass` now passes when EITHER marker is present (OR logic) and emits a `detail` naming whichever marker(s) are present (or both names when neither is). No subcommand rename, no polarity change, and no change to the writer `set-evolve-mode.py` — those land in Phase 2. Spec Inv 21 (specs/spec.md) updated: the `approval-bypass` JSON example detail now mentions both names, and a "Dual-read of the bypass marker" subsection documents the OR logic, the coexistence-window rationale, and the Phase-2 fallback-drop criterion; the enforced-scenarios list gains the new-marker-alone and both-markers cases. `test/test-check-preconditions.py` gains a `_seed_tdd_autonomous` helper and three E2E scenarios: new marker alone satisfies approval-bypass (all_pass=true), both markers present satisfies it, and the legacy marker still satisfies it (live-state regression guard). Versions bumped 0.12.0 → 0.12.1 across feature.json, spec.md, contract.md (frontmatter + provides.skills), SKILL.md (source + deployed copy republished via the `publish_skill` manifest contract). No runtime behavior change for the live state (legacy marker still works); the fallback is dropped in a later phase once Phase 2 renames the live marker.

- **v0.12.0 — 2026-06-02** — Phase 2 of #399 (rabbit-auto-evolve). Migrated this feature's spec/contract layout from `docs/spec/` to the sibling `specs/` directory via `git mv .claude/features/rabbit-auto-evolve/docs/spec .claude/features/rabbit-auto-evolve/specs`; `specs/spec.md` + `specs/contract.md` now hold the spec and contract, while the unrelated `docs/bugs/` directory is retained (only `docs/spec` moved). Made the spec-resolving tooling this feature owns dual-read (#399 coexistence window opened in Phase 1): `scripts/triage-issue.py` (1.2.0 → 1.3.0) gains a `resolve_spec_path(feature_root, name)` helper that prefers `specs/<name>` and falls back to `docs/spec/<name>`, wired into the rule-6 `_read_spec_head_matter` read so triage classifies features on EITHER layout. Updated this feature's own spec references (`docs/spec/spec.md` → `specs/spec.md`, `docs/spec/contract.md` → `specs/contract.md`) and the rule-6 read-surface description in spec.md; added a "Paths governed" note documenting the `specs/` layout and the dual-read requirement for owned tooling. Made the spec-reading tests dual-read aware: `test/test-feature-shape.py`, `test/test-spec-convergence-invariant.py`, and `test/test-spec-dispatch-shape-invariant.py` now resolve the spec via the specs/-preferred, docs/spec/-fallback path. New E2E regression `test/test-specs-layout-migrated.py` asserts the real on-disk layout (specs/ present, docs/spec/ gone, docs/bugs/ retained, no hard-coded legacy self-reference) and that `triage-issue.py`'s resolver + rule-6 read resolve a spec from both layouts. Versions bumped 0.11.1 → 0.12.0 across feature.json, spec.md, contract.md (frontmatter + provides.skills), SKILL.md (source + deployed copy republished via the `publish_skill` manifest contract). No runtime behavior change beyond the relocated path; Phase 3 (separate PR) drops the docs/spec/ fallback once every feature has migrated.

- **v0.11.1 — 2026-06-02** — Part of #416 (rabbit-auto-evolve owner sweep). Metadata-only: changed the feature owner from the prior individual maintainer to the `rabbit-workflow team` in every owner-bearing location within the feature — `feature.json` owner, `docs/spec/spec.md` + `docs/spec/contract.md` frontmatter owner/version, `skills/rabbit-auto-evolve/SKILL.md` frontmatter owner, the top-level owner in `scripts/schemas/auto-evolve-state.schema.json`, and the docstring owner line in all 19 script/test modules (now `rabbit-workflow team (rabbit-auto-evolve)`, matching the repo convention). Synthetic owner values in `test/test-dispatch-shape.py` and `test/test-triage-rules.py` fixtures updated to the team. `test/test-feature-shape.py` gains assertion t6: every owner field/docstring/schema value names the rabbit-workflow team and no individual-owner token remains anywhere in the feature tree. No behavior change. Versions bumped 0.11.0 → 0.11.1 across feature.json, spec.md, contract.md (frontmatter + provides.skills), SKILL.md (source + deployed copy republished via the `publish_skill` manifest contract).

- **v0.11.0 — 2026-06-03** — Fix #435 (decouple work-selection from dispatch-shape). The loop now makes two SEPARATE decisions in order. **Stage 1 — work selection (dispatch-shape blind):** `scripts/plan-batch.py` (1.0.0 → 1.1.0) emits `selection_order` — work items ordered purely by priority desc then issue asc; it never consults dispatch shape, feature count, or "knows how", so a high-priority cross-feature item is selected before a low-priority single-feature item. **Stage 2 — dispatch shape (item-shaped):** `plan-batch.py` also emits `dispatch_shapes` (issue-number-string → shape), choosing the FIRST fitting shape from exactly THREE: `parallel-per-feature` (item edits one feature dir — the performance preference, not a correctness requirement), `multi-subagent-barrier` (item edits >1 feature dir below the threshold — per-feature subagents land serially on one shared branch, each a full single-feature touch with its own scope marker), `decomposition` (item edits ≥ `--decompose-threshold` feature dirs, default 10 — file N per-feature sub-issues via the rabbit-issue `file-item.py` contract invoke and keep the parent open). The per-item feature count comes from a new `features` field emitted by `scripts/triage-issue.py` (1.1.0 → 1.2.0): the sorted union of the `feature:<name>` label and every `.claude/features/<name>/` path referenced in the body. **Struck shape 2:** the original issue's "sequential single-subagent with scope override" shape is forbidden per the maintainer's binding policy — autonomous-evolve always uses a full per-feature touch gated by `.rabbit-scope-active-<feature>` and NEVER writes a persistent `.rabbit-scope-override session` for feature edits; bounded scope is a hard constraint, not waivable by autonomy. New spec Inv 26; contract gains the `file-item.py` invoke for the decomposition path. New `test/test-dispatch-shape.py` (single → parallel-per-feature; cross-feature → multi-subagent-barrier; 10+ features → decomposition; Stage-1 high-priority cross-feature selected before low-priority single-feature; no shape emits a session override; `features` extraction) and `test/test-spec-dispatch-shape-invariant.py`. Versions bumped 0.10.0 → 0.11.0 across feature.json, spec.md, contract.md, SKILL.md (frontmatter + provides.skills).

- **v0.10.0 — 2026-06-02** — Fix #423 (rabbit-auto-evolve half — Parts A, B, E + the merge-prs.py caller update). **Part A — defer classifier with planning notes:** `scripts/triage-issue.py` (1.0.0 → 1.1.0) now attaches a non-empty `planning_note` to every `defer` decision (describing what analysis would unblock dispatch) and `planning_note: null` to non-defer decisions. The decision set is documented as exactly `{work, defer, close-not-planned}`; `close-completed` is never emittable from triage — a completed closure is only ever asserted by the merge phase once work has landed. **Part B — anti-infinite-defer counter:** `scripts/triage-batch.py` (1.0.0 → 1.1.0) now owns a per-issue consecutive-defer counter persisted in `.rabbit/auto-evolve-state.json` under the new optional `defer_counts` map (keyed by issue-number string). A `defer` increments the counter; the 4th consecutive defer (counter already ≥ 3) is FORCED to `work` with `reason_code: defer-limit-reached` and the accumulated planning-note history surfaced; any non-defer decision resets the counter to 0. Persistence is best-effort atomic temp+rename (read-modify-write, preserving all other state keys); no state file means decisions pass through unchanged (tick liveness). State schema bumped 1.0.0 → 1.1.0 (`scripts/schemas/auto-evolve-state.schema.json` + `scripts/update-state.py` 1.0.0 → 1.1.0 validator) adding the optional `defer_counts` field — an additive, backward-compatible change (pre-1.1.0 states without it still validate). `scripts/start-loop.py` (1.1.0 → 1.2.0) default-state bootstrap now writes `schema_version: 1.1.0`. **Part C consumer — merge-prs.py:** `scripts/merge-prs.py` (1.2.0 → 1.3.0) now passes `--commit-sha <merge-sha>` to `item-status.py close --reason completed` (PR-A made `--commit-sha` REQUIRED for a completed closure). **Part E — spec invariant:** new spec Inv 25 (triage convergence guarantee). Feature versions bumped 0.9.2 → 0.10.0 across feature.json, spec.md, contract.md, SKILL.md (frontmatter). New `test/test-spec-convergence-invariant.py`; extended `test/test-triage-rules.py` (defer planning_note + no-close-completed), `test/test-triage-batch.py` (4 defer-counter scenarios), `test/test-merge-prs.py` (asserts `--commit-sha` is passed), `test/test-state-persistence.py` (schema 1.1.0 + `defer_counts` round-trip + optional), and `test/test-loop-markers.py` (default-state schema_version assertions updated to 1.1.0).

- **v0.9.2 — 2026-06-02** — Fix #429: `scripts/merge-prs.py` now performs a DIRECT squash merge (`gh pr merge <#> --squash`) instead of `gh pr merge <#> --squash --auto`. The `--auto` flag requires the repo to have auto-merge enabled (`enablePullRequestAutoMerge`); on a repo without it, `gh pr merge --auto` succeeds only for an immediately-mergeable PR and fails for the rest with `Auto merge is not allowed for this repository`. During a real tick this was order-dependent and intermittent: the first ready PR merged, its siblings fell behind, and `--auto` then tried to ENABLE the auto-merge queue (which the repo rejects). Mergeability is already gated by the `base == dev` refusal plus `safety-check.py`, so a direct merge is correct and never depends on the repo's auto-merge setting. `--delete-branch` was intentionally NOT added so `cleanup-branches.py`'s `git push origin --delete` remains a real deletion (no behavior change to cleanup). `merge-prs.py` module version 1.1.0 → 1.2.0; feature versions bumped 0.9.1 → 0.9.2 across feature.json, spec.md, contract.md, SKILL.md. Spec Inv 6 step 3 and the public-surface table updated to spell out the no-`--auto` rule; new `test/test-merge-prs.py` regression asserts the recorded `gh pr merge` call does NOT contain `--auto` and still uses `--squash`.

- **v0.9.1 — 2026-06-02** — Fix #397: `scripts/safety-check.py` Invariant 5 now rejects only on uncommitted modifications to TRACKED files (staged or unstaged), using two `git diff --quiet` calls (`git diff --quiet` for unstaged, `git diff --cached --quiet` for staged) instead of `git status --porcelain`. The old porcelain check counted `??` untracked files as dirtiness, which deadlocked the auto-evolve loop every time a new untracked runtime artifact appeared (e.g. `.rabbit-auto-evolve-*`, `.claude/scheduled_tasks.{lock,json}`) — untracked files cannot affect a merge, so the check was too strict. The check still protects against half-committed subagent work, manual interleaving, and hook-induced drift (all tracked-file modified states). Inv 5 short name and spec table row updated to "no uncommitted modifications to tracked files"; spec test obligations gained a tracked-vs-untracked discrimination bullet. `test/test-safety-check.py` Inv 5 negative test replaced with four scenarios: untracked file PASSES, tracked unstaged mod FAILS, tracked staged mod FAILS, clean tree PASSES. safety-check.py module version 1.0.0 → 1.1.0; feature versions bumped 0.9.0 → 0.9.1 across feature.json, spec.md, contract.md, SKILL.md.

- **v0.7.7 — 2026-06-02** — Fix #386: SKILL.md `start` subcommand now routes on the `check-preconditions.py` report shape rather than dumping the failing checklist on every `all_pass: false` case. On fresh state (`active-marker` check `ok: false`) the skill automatically invokes `/rabbit-auto-evolve on` and surfaces the script's branded restart prompt before ending the turn — the user no longer has to manually run `on` first. When markers exist but `bypass-permissions` has not loaded (forgot-to-restart case), the skill emits a short branded reminder line instead of re-running `on`. The verbatim failing-checklist surface is now reserved for the genuinely unexpected fallback branch (partial corruption, manual tampering). Inv 10 in `docs/spec/spec.md` rewritten with the explicit routing table; SKILL.md `start` section rewritten in matching prose; `test/test-start-stop-skill.py` extended to assert the routing keywords are present and the pre-#386 blanket "surface each failing" instruction is absent. Versions bumped 0.7.6 → 0.7.7 across feature.json, spec.md, contract.md (provides.skills version), SKILL.md frontmatter.

- **v0.7.6 — 2026-06-02** — Fix #384: `test/test-banner-suppression.py` synthetic tempdir now copies `scripts/banner-status.py` into `<td>/.claude/features/rabbit-auto-evolve/scripts/`. After PR #383 refactored `contract.lib.runtime.emit_auto_evolve_banner` to delegate line-1 and line-2 content to `banner-status.py` via subprocess, the test's synthetic `.claude/features/` tree lacked the script so the subprocess invocation returned non-zero (`No such file or directory`) and `emit_auto_evolve_banner` fell through to its best-effort `[]` failure path — scenarios S2/S3/S4 saw an empty banner. The fix copies the real `banner-status.py` (sourced via `__file__`-relative repo-root resolution) into the tempdir during `build_repo` so subprocess delegation resolves. No source-code change; spec Inv 14 unchanged.

- **v0.7.5 — 2026-06-02** — Fix #380 (step 1 of 2): new `scripts/banner-status.py` owns the active-banner line-2 text variants. Emits `{active, line1, line2}` JSON on stdout; always exits 0; reads markers only (no `git`, no `gh`, no filesystem writes). Four line-2 variants with `aborted > restart-needed > running > default` precedence; the new `running` variant (`loop in progress`) is NOT yet surfaced at SessionStart — the current `contract.lib.runtime` `emit_auto_evolve_banner` implementation still inlines the three pre-existing variants. A follow-up cycle against the `contract` feature will refactor `emit_auto_evolve_banner` to invoke `banner-status.py` instead, at which point Inv 14 will defer line-2 ownership to Inv 22. Added spec Inv 22 + ownership-migration note on Inv 14; new `test/test-banner-status.py` covers all 4 variants + 3 precedence pairs + always-exit-0 contract.

- **v0.7.4 — 2026-06-02** — Fix #377: `scripts/set-evolve-mode.py` `on`/`off` success now emits branded `rabbit_print` confirmation lines to stdout (matches SessionStart banner format). `on` emits two lines: red `AUTONOMOUS-EVOLVE MODE CONFIGURED — restart Claude Code to activate` (with `🚀` icon) + yellow `After restart, run: /rabbit-auto-evolve start` (with `👉` icon). `off` emits one green line: `Autonomous-evolve mode deactivated — full teardown complete` (with `✅` icon). All lines carry the `[🐇 rabbit 🐇]` brand prefix via the centralized renderer in `contract/scripts/rabbit_print.py`. SKILL.md `on`/`off` subcommand sections now instruct Claude to surface the script's stdout verbatim instead of paraphrasing — the prior flat `set-evolve-mode: on OK` line was easy to miss and the skill's paraphrase didn't match the visual weight of the rest of the rabbit surface. Extended spec Inv 1 with the branded-confirmation paragraph and two new test obligations; new test scenarios G and H in `test-set-evolve-mode.py` assert the brand prefix and key substrings appear on stdout for both `on` and `off`.

- **v0.7.3 — 2026-06-02** — Fix #375: new `scripts/check-preconditions.py` emits structured JSON `{all_pass, checks: [{id, ok, detail}]}` reporting on the three `start` preconditions (`active-marker`, `approval-bypass`, `bypass-permissions`). Exit code is ALWAYS 0 — the verdict lives in `all_pass`. SKILL.md `start` section now invokes this script and routes on `all_pass`, replacing the prior narrative description that invited bare `ls .rabbit-auto-evolve-*` precondition checks (which emit ugly `ls: cannot access ...: No such file or directory` stderr noise on fresh clones where the markers legitimately do not yet exist). Added spec Inv 21; extended `test-start-stop-skill.py` to assert the script invocation IS present AND bare `ls .rabbit-auto-evolve-*` patterns are absent; new `test-check-preconditions.py` covers all-fail / all-pass / partial / malformed-settings scenarios.

- **v0.7.2 — 2026-06-02** — Fix #373: tick lifecycle hardening. (1) `scripts/start-loop.py` now self-heals before writing the running marker — it deletes any stale `.rabbit-auto-evolve-stop-requested` (explicit `start` cancels a pending stop) and bootstraps `.rabbit/auto-evolve-state.json` with default content (atomic temp+rename, matching `update-state.py`) if the file is missing, empty, or fails JSON parse. A valid existing state file is left untouched. (2) New `scripts/end-tick.py` mirrors `start-loop.py`: it deletes `.rabbit-auto-evolve-running` and is idempotent (missing marker is a no-op). (3) `SKILL.md` tick documentation now invokes `end-tick.py` on EVERY exit path (normal completion, phase 0 halt, safety abort, error abort) — not just the happy path — so the running marker can never leak across sessions. Added spec Inv 19 (`start-loop.py` self-heal) and Inv 20 (`end-tick.py` mandatory at every exit); updated Inv 17 marker table to show start-loop.py writes / end-tick.py deletes `.rabbit-auto-evolve-running`. Extended `test/test-loop-markers.py` (start-loop self-heal scenarios + end-tick round-trip + idempotency) and `test/test-start-stop-skill.py` (SKILL.md must mention `end-tick.py` and the four named exit paths).

- **v0.7.1 — 2026-06-02** — Fix #371: `scripts/set-evolve-mode.py off` now performs a full teardown — it deletes the four loop-runtime markers (`.rabbit-auto-evolve-running`, `.rabbit-auto-evolve-stop-requested`, `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`) first (idempotent), then reverses the three activation mutations in inverse order. In v0.7.0 `off` only deleted `.rabbit-auto-evolve-active`, leaving the loop-runtime markers behind for the user to clean up manually (which scope-guard then denied because literal `rm`/`touch` of non-allowlisted markers is blocked). SKILL.md tick prose updated to reference `triage-batch.py` in the canonical `fetch-queue | triage-batch | plan-batch` pipe (Inv 18 follow-up from #369). Spec Inv 1 rewritten to detail the 4-step teardown and bumped to v0.7.1; `test-set-evolve-mode.py` extended with full-teardown and partial-state scenarios; `test-tick-skill.py` now asserts SKILL.md references `triage-batch.py`.

- **v0.7.0 — 2026-06-02** — Fix #369: add `scripts/triage-batch.py` bridge so the standard tick pipe `fetch-queue | triage-batch | plan-batch` works end-to-end. `triage-batch.py` reads the raw `gh issue list` shape on stdin, invokes `triage-issue.py` per item, and emits the concatenated triage-object array on stdout. Per-issue failures are converted to `defer/triage-failed` entries so a single bad issue cannot abort the batch. `plan-batch.py` now silently drops items where `decision != "work"` (items without the `decision` key continue to pass through for backwards compatibility). Added spec Inv 18 and `test-triage-batch.py`; extended `test-plan-batch.py` to cover the unfiltered triage array case.

- **v0.6.0 — 2026-06-02** — Fix #367: marker writes wrapped in scripts (`start-loop.py`, `stop-loop.py`, `mark-restart-needed.py`, `mark-aborted.py`) so scope-guard does not block them. SKILL.md's `start` and `stop` subcommand sections now instruct the dispatcher to invoke `python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py` / `stop-loop.py` rather than write the markers directly. Mirrors the proven `set-evolve-mode.py` pattern. Added spec Inv 17 plus `test-loop-markers.py`; extended `test-start-stop-skill.py` to assert SKILL.md contains the script invocations and forbids literal `touch .rabbit-auto-evolve-*` / `echo > .rabbit-auto-evolve-*`.

- **v0.5.2 — 2026-06-02** — Fix #364: drop `model: opus` from SKILL.md frontmatter (default session model handles dispatch); `feature.json` prompts[0].inject now uses full repo-relative paths (`.claude/features/policy/<name>.md`) so the prompt dispatcher resolves them and the Stop-hook `prompt-injection failures: rabbit-auto-evolve` line goes away. Spec Inv 10 + Inv 12 refined; test-prompts-declared.py extended to assert (a) no `model:` key in SKILL.md frontmatter, (b) every inject entry is a full repo-relative path to an existing file (no bare names).

- **v0.5.1 — 2026-06-02** — Fix #362: SKILL.md script references now use the full feature-relative path `.claude/features/rabbit-auto-evolve/scripts/<name>.py` (bare `scripts/<name>.py` was failing with file-not-found because Claude resolves SKILL paths relative to the deployed `.claude/skills/rabbit-auto-evolve/` location, which has no `scripts/` subdir). Added Inv 16 to spec; extended test-on-off-surface.py and test-tick-skill.py to assert feature-relative prefix.

- **v0.5.0 — 2026-06-02** — Surface consolidation (#360): `/rabbit-auto-evolve` now owns `on`/`off` activation; `/rabbit-config` no longer dispatches the auto-evolve loop. Removed `configuration[auto-evolve]` from `feature.json`; added `### on` and `### off` subcommand sections to SKILL.md; bumped version to 0.5.0 across feature.json, spec.md, contract.md, SKILL.md.

- **v0.4.0 — 2026-06-02** — Feature-shape compliance pass: aligned versions across feature.json, spec.md, contract.md, SKILL.md; added test-feature-shape.py guard.

- **v0.3.0 — 2026-06-02** — Phase D Task 12 + Task 13 — SKILL.md (4 subcommands + 12-phase tick), feature.json wiring (manifest, configuration, prompts, runtime, surface.skills), cross-scope registration in workspace-structure.json, passthrough template, banner-suppression e2e test.

- **v0.2.0 — 2026-06-02** — Phase C — all 10 scripts (set-evolve-mode, fetch-queue, triage-issue, plan-batch, safety-check, merge-prs, cleanup-branches, release-bump, classify-merge-restart, update-state) + auto-evolve-state.schema.json; spec invariants 1–9.

- **v0.1.0 — 2026-06-01** — Scaffold + seed spec (PR #333).
