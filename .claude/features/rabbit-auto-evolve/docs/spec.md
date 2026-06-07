---
feature: rabbit-auto-evolve
version: 0.86.1
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code or rabbit gains a native always-on autonomous-agent mode that supersedes this skill
status: active
---

# rabbit-auto-evolve — Spec

> Machine-targeted LLM-prose view. The structured source of truth is
> [`feature.json`](../../feature.json) and [`contract.md`](./contract.md).
>
> Initial spec body drafted by `rabbit-spec-create` (spec-creator subagent)
> in standalone mode. Source design doc:
> `docs/superpowers/specs/2026-06-01-rabbit-auto-evolve-design.md`.
> Implementation plan: `docs/superpowers/plans/2026-06-01-rabbit-auto-evolve.md`.

## Purpose

A self-driving rabbit loop that continuously fetches open ACTIONABLE
GitHub issues (those carrying a valid `feature:` + `priority:` label — the
actionability selection basis, see Inv 2),
triages each one, dispatches TDD subagents to implement
actionable work, merges approved PRs into `dev`, tags versioned releases,
and is fired on a fixed cadence by a system cron (the sole tick scheduler;
see Inv 32) until the user issues an explicit stop — all without requiring
human approval at each step.

## Paths governed

- (none — standalone feature)

This feature's own spec and contract live under the flat `docs/` layout
(`docs/spec.md`, `docs/contract.md`), with a sibling `docs/bugs/` directory.
Any tooling this feature owns that resolves a feature's spec/contract path
(e.g. `scripts/triage-issue.py`) MUST prefer the flat `docs/<name>` layout
and accept the legacy `specs/<name>` and `docs/spec/<name>` layouts as
fallbacks during the coexistence window.

## Public surface

The `scripts/` directory holds this feature's public surface scripts,
described below.

**Configuration entry (via `/rabbit-config`)** — declared in `feature.json`:

- `auto-evolve on` / `auto-evolve off` — compound activation mutator; both
  values dispatch via `run_feature_script → scripts/set-evolve-mode.py
  {on|off}`; `restart_required: true`.

**Skill: `rabbit-auto-evolve`** (declared in `feature.json.surface.skills`;
SKILL.md at `skills/rabbit-auto-evolve/SKILL.md`; `model: opus`):

- `start` — begin or resume the loop; enforces three preconditions (marker
  present, `human-approval` off, `bypass-permissions` on), writes
  `.rabbit-auto-evolve-running`, runs one tick, ends with `ScheduleWakeup`.
- `stop` — writes `.rabbit-auto-evolve-stop-requested`; the next tick sees
  it, posts a summary, and does not reschedule.
- `status` — read-only: prints queue length, in-flight set, last-merged PR,
  last-tagged version, consecutive-failure count, and which restart marker
  (if any) is present.
- `tick` — internal; only invoked by `ScheduleWakeup`; walks the 12 tick
  phases documented in SKILL.md.
- `log on|off|level <quiet|normal|debug>|path|tail [N]|clear` — manage the
  per-tick observability log (Inv 37): toggle the enable flag,
  set verbosity, print the log path, tail the last N lines (default 20), or
  truncate the log. State persists in rabbit-auto-evolve's own config (NOT
  rabbit-cage).

**Scripts:**

| Script | Kind | Description |
|---|---|---|
| `scripts/set-evolve-mode.py` | CLI | Compound mutator: `on` flips `human-approval=false`, `bypass-permissions=true`, writes `.rabbit-auto-evolve-active` in order with rollback on failure; `off` reverses in inverse order |
| `scripts/fetch-queue.py` | CLI | Lists open ACTIONABLE issues (valid `feature:` + `priority:` label) via `gh`, sorts by priority then `createdAt`, emits JSON array |
| `scripts/triage-issue.py` | CLI | Per-issue classifier; reads issue metadata and the named feature's spec front matter; emits a triage JSON object with `decision`, `reason_code`, `rationale`, `feature`, `contract_touch`, `blocked_by`, `duplicate_of` |
| `scripts/resolve-duplicate.py` | CLI | Records the GitHub-native duplicate resolution (Inv 60): `resolve <dup> <canonical>` closes the duplicate with `state_reason=duplicate` and cross-links the canonical issue; `status <n>` reports whether an issue is recognized as a duplicate (native state authoritative; legacy `duplicate` label honored on read as a deprecating mirror) |
| `scripts/plan-batch.py` | CLI | Reads a work-set JSON from stdin; partitions contract-touch issues into `barrier_first`; greedy graph-colors the rest by feature-conflict into `groups`; applies `max_parallel` cap |
| `scripts/integration_target.py` | CLI + lib | Resolves the loop's integration target branch (Inv 61): default `dev`, overridable to `main` via `RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET`; exposes `resolve_target`, `accepted_targets` ({dev, main}), `is_default_branch`; the sibling phase scripts import it |
| `scripts/safety-check.py` | CLI | Validates the bottom-line invariants (branch is the integration target, PR base is an accepted integration target, head branch matches `^feat/.+`, tag does not already exist, no uncommitted modifications to tracked files, and — merge phase only — the isolated install + update smoke passes via `install-smoke.py`, Inv 63); exits non-zero on any violation |
| `scripts/install-smoke.py` | CLI | Pre-merge install smoke (Inv 63): runs a network-free fresh install + `--update` of rabbit-cage's `install.py` against the current tree inside a tempdir, asserting no install/closure/publish failure; invoked as bottom-line check 6 by `safety-check.py --phase merge` so install breakage blocks the merge; skips gracefully when install.py is absent |
| `scripts/merge-prs.py` | CLI | Calls `safety-check.py --phase merge` then `gh pr merge --squash` (direct merge, NOT `--auto`) for each PR, adding `--admin` when the base is the protected default branch (`main`) to land past the required-review the loop cannot satisfy; accepts a base in the `{dev, main}` coexistence set and refuses any other; runs the manual close-after-merge only while the target is not the default branch |
| `scripts/release-bump.py` | CLI | Reads merged PR priority label and diff scope; applies patch/minor/major semver bump per design table; creates annotated git tag and `gh release` targeting the resolved integration target |
| `scripts/cleanup-branches.py` | CLI | Derives head branch from each merged PR; calls `safety-check.py --phase cleanup`; deletes branch locally and on origin; refuses to delete anything not matching `^feat/.+` |
| `scripts/classify-merge-restart.py` | CLI | Reads merged PR file list; classifies into `no-op`, `refresh`, or `restart` based on which path patterns appear; emits a single string on stdout |
| `scripts/update-state.py` | CLI | Reads JSON from stdin; validates against `schemas/auto-evolve-state.schema.json`; atomically writes `.rabbit/auto-evolve-state.json` via temp+rename |
| `scripts/status-report.py` | CLI | Read-only `status` backing script: reads `.rabbit/auto-evolve-state.json` (defaults on missing/empty/malformed) and the five runtime markers; emits a fixed-format status JSON on stdout |
| `scripts/run-post-merge.py` | CLI | Deterministic non-skippable runner for tick phases 8–10 (release → cleanup → catch-up): reads `pending_post_merge` from state, invokes `release-bump.py` / `cleanup-branches.py` / `classify-merge-restart.py` in order, then clears the field; clean no-op when empty (Inv 30); also prunes fully-`completed`/`aborted` ticks from `dispatch_journal` (Inv 54) |
| `scripts/record-dispatch.py` | CLI | The script-owned dispatch-journal WRITE point (Inv 54): atomic read-modify-write of a per-tick dispatch entry (issue, feature, shape, status, branch, worktree, pr) into `dispatch_journal` in `.rabbit/auto-evolve-state.json`; invoked by the dispatcher at Phase 6 |
| `scripts/resume-dispatch.py` | CLI | The script-owned dispatch-journal READ/RESUME point (Inv 54): reads the active tick's journal and partitions the planned `selection_order` (stdin) into `dispatch` (re-enter Phase 6) and `skip` (already completed/pr_open this cycle) |
| `scripts/install-cron.py` | CLI | Idempotently installs the `*/30` system-cron entry that fires `tick-headless.py` (the sole tick scheduler); invoked by `set-evolve-mode.py on` (Inv 32) |
| `scripts/uninstall-cron.py` | CLI | Idempotently removes the system-cron entry; safe no-op when absent; invoked by `set-evolve-mode.py off` (Inv 32) |
| `scripts/tick-headless.py` | CLI | The Claude-free headless tick fired by the system cron: walks phases 0–1, 3–5, 7, 8–10, 11; skips phase 6 (dispatch needs Claude); phase 12 is a no-op (Inv 32) |
| `scripts/detect-scheduler.py` | CLI | Probes `crontab -l` (via `RABBIT_CRONTAB_CMD`) and emits `{"scheduler":"crontab"|"croncreate","reason":...}`: crontab where usable, CronCreate fallback where restricted (Inv 34 / D2) |
| `scripts/running-guard.py` | CLI | Inspects `.rabbit-auto-evolve-running`, clears a STALE marker (mtime/PID), and emits a proceed/skip verdict so a wedged tick never blocks the loop (Inv 35 / D3) |
| `scripts/tick-log.py` | CLI | Minimal append-only JSON-per-line logger to `.rabbit/tick.log` for heartbeat/guard/schedule decisions; full verbosity config is Inv 37's scope (Inv 36 / D4) |
| `scripts/schedule-decision.py` | CLI | At tick end/heartbeat, counts DISPATCHABLE work via the `fetch-queue.py \| triage-batch.py \| plan-batch.py` pipe (the plan's `selection_order`, which excludes blocked/deferred items, decomposition parents, and non-work verdicts) and emits `immediate-refire` (near-immediate one-shot) vs `idle`; the dispatcher performs the `CronCreate` one-shot (Inv 33 / D1). Every decision also carries `authoritative_version` — the current version resolved FRESH this tick from `git describe --tags --abbrev=0` with a state `last_tagged_version` fallback (Inv 64) |
| `scripts/log-tick.py` | CLI | Full per-tick observability logger: owns all writes to the append-only JSON-lines log at `.rabbit/auto-evolve.log`; structured kwargs → one record/line, with on/off enable, three verbosity levels, a <2KB per-line cap and 5MB rotation (Inv 37). Distinct from the minimal `tick-log.py` (different file + purpose) |
| `scripts/log-path.py` | CLI | Prints the absolute path of the `.rabbit/auto-evolve.log` file so a cross-session daemon can `tail -f $(… log-path.py)` (Inv 37) |

**State file (runtime artifact):**

- `.rabbit/auto-evolve-state.json` — schema version `1.4.0`; required fields:
  `schema_version`, `updated_at`, `queue`, `last_merged_sha`,
  `last_tagged_version`, `consecutive_failures`, `stop_requested`,
  `restart_needed`; optional fields: `in_flight` (no longer required,
  subsumed by `dispatch_journal` per Inv 54), `defer_counts`,
  `pending_post_merge`, `decomposition_parents`, `dispatch_journal` (Inv 54).

**Runtime hooks (to be declared in `feature.json.runtime`):**

- `emit_auto_evolve_banner` (SessionStart) — implemented in
  `contract.lib.runtime` per contract Inv 65; emits the composite active
  banner replacing the two per-configurable alerts (suppressed per contract
  Inv 64 when `.rabbit-auto-evolve-active` is present).
- `emit_auto_evolve_stop_line` (Stop) — implemented in
  `contract.lib.runtime` per contract Inv 65; emits at most one status
  line per loop state.

**Disk markers (control flow):**

- `.rabbit-auto-evolve-active` — mode is on; suppresses per-configurable
  alerts.
- `.rabbit-auto-evolve-running` — loop is currently dispatching.
- `.rabbit-auto-evolve-stop-requested` — graceful stop pending.
- `.rabbit-auto-evolve-restart-needed` — loop merged a change requiring
  Claude restart.
- `.rabbit-auto-evolve-aborted` — safety violation detected; loop will not
  resume until marker is cleared.
- `.rabbit-auto-evolve-restart-advised` — ADVISORY restart signal (Inv 52);
  a structured reason describing a capability a restart would unlock. Never
  pauses the loop; distinct from the hard `.rabbit-auto-evolve-restart-needed`.

## Current behaviour

The end-to-end behaviour — activation/teardown, the SessionStart banner,
start preconditions, the twelve-phase tick, triage, the computed priority
score and dispatch grouping, merge/release/cleanup/catch-up, decomposition,
state persistence, stop, and self-resume — is specified normatively and in
full by the numbered Invariants below. Each invariant names the script that
owns the behaviour, the data shape, and the enforcing test; no behaviour
summary is restated here.

## Invariants

1. **`set-evolve-mode.py {on|off}` compound mutator.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py
   {on|off}` performs the three mutations that compose the auto-evolve
   activation/deactivation.

   On `on`, three deterministic mutations execute in order:
   1. Write `<repo_root>/.rabbit-human-approval-bypass` (content
      `"session"`) via `contract.lib.mutation.write_marker` — flips
      `human-approval` configurable to `false`. During the Phase 1
      coexistence window the script ALSO writes the new name
      `<repo_root>/.rabbit-tdd-autonomous` (same content) so a later
      read-path rename finds the marker; both names are honored on read
      (the dual-read described later in this Inv) until removal of the
      legacy write closes the window.
   2. Set `permissions.defaultMode: "bypassPermissions"` in
      `<repo_root>/.claude/settings.local.json` via
      `contract.lib.mutation.set_json_key` — flips `bypass-permissions`
      configurable to `true`.
   3. Write `<repo_root>/.rabbit-auto-evolve-active` via
      `contract.lib.mutation.write_marker` — signals auto-evolve mode active
      (consumed by `contract.lib.runtime` Inv 64 suppression and the Inv 65
      banner APIs).

   On `off`, the script performs a FULL teardown — innermost
   runtime markers first, then the three activation mutations in
   inverse order:

   1. Delete any of the four loop-runtime markers if present
      (`.rabbit-auto-evolve-running`,
      `.rabbit-auto-evolve-stop-requested`,
      `.rabbit-auto-evolve-restart-needed`,
      `.rabbit-auto-evolve-aborted`) via
      `contract.lib.mutation.delete_marker`. Idempotent
      (delete-if-exists; missing markers are no-ops). The script deletes
      these itself — manual `rm` of non-allowlisted markers is scope-guard
      blocked — so a subsequent `on` lands in a clean state.
   2. Delete `.rabbit-auto-evolve-active`.
   3. Delete the `permissions.defaultMode` key via
      `contract.lib.mutation.delete_json_key`.
   4. Delete `.rabbit-human-approval-bypass` AND the new
      `.rabbit-tdd-autonomous` (both bypass-marker names during the Phase 1
      coexistence window) via `contract.lib.mutation.delete_marker`.
      Idempotent — a missing marker of either name is a no-op.

   Failure handling: abort on first error and roll back prior steps
   best-effort (delete a just-written marker; restore the prior
   `permissions.defaultMode` if step 2 succeeded). Report the failed step
   and rollback outcome on stderr. Exit code: 0 on full success; non-zero on
   any step failure (after rollback attempt).

   Idempotency: both `on` and `off` are clean no-ops in the already-target
   steady state (the `contract.lib.mutation` APIs are themselves idempotent;
   the script only owns ordering and rollback coordination).

   **Branded confirmation on success** (per contract Inv 46 — brand prefix
   owned by `rabbit_print`). On `on` full success the script emits two lines
   via `contract.lib.runtime.rabbit_print`:

   - Line 1 — red — `🚀 AUTONOMOUS-EVOLVE MODE CONFIGURED — restart Claude Code to activate`
   - Line 2 — yellow — `👉 After restart, run: /rabbit-auto-evolve start`

   On `off` full success it emits one line via `rabbit_print`:

   - green — `✅ Autonomous-evolve mode deactivated — full teardown complete`

   SKILL.md's `on` / `off` subcommand bodies surface the script's stdout
   verbatim (no skill-generated paraphrase); the message text lives in the
   script so it stays centralized.

   Enforced by `test/test-set-evolve-mode.py` (`tempfile.TemporaryDirectory()`
   fixtures, rabbit-config Inv 17 isolation): `on` from clean state (all three
   side effects appear; `permissions.defaultMode == "bypassPermissions"`); `off`
   from on state (all three revert); step-2 failure simulation (monkey-patch
   `contract.lib.mutation.set_json_key` to raise → step 1's marker removed in
   rollback, non-zero exit, stderr names the step); idempotency
   (`on`-from-`on` / `off`-from-`off` clean no-ops); branded `on` confirmation
   (stdout has `[🐇 rabbit 🐇]`, `AUTONOMOUS-EVOLVE MODE CONFIGURED`, `restart
   Claude`, `/rabbit-auto-evolve start`); branded `off` confirmation
   (`[🐇 rabbit 🐇]` AND `deactivated`).

2. **`fetch-queue.py` deterministic queue emission.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/fetch-queue.py`
   emits a deterministic JSON array on stdout, sorted by priority
   (`critical` > `high` > `medium` > `low`) then `createdAt` ascending
   (oldest first within the same priority bucket). Selection is
   ACTIONABILITY-based: an OPEN issue appears iff it carries BOTH a valid
   `feature:<name>` label AND a valid `priority:<level>` label (one of the
   four recognized levels). This is the actionable-work gate; an issue
   lacking either label is not yet actionable and is excluded.

   Selection is purely ACTIONABILITY-based: only the `feature:` and
   `priority:` labels participate. No other label gates the queue, and this
   actionability basis aligns the selection with the already-LABEL-INDEPENDENT
   convergence guarantee (Inv 25).

   The script invokes `gh issue list --repo <repo> --state open
   --json number,title,labels,body,createdAt --limit 500` and filters to the
   actionable set in-script, where `<repo>` is resolved via
   `rabbit_issue._gh.resolve_repo` (importable from
   `.claude/features/rabbit-issue/scripts/`) — no `git remote get-url`
   shellouts. The script never reads or writes anything other than
   the `gh` CLI output stream — no git, no filesystem mutations.

   Exit code: 0 on success; non-zero on gh-auth failure or any
   unexpected `gh` error (stderr passthrough).

   Enforced by `test/test-fetch-queue.py`:
   - Smoke test: invoke with `--help`; assert exit 0 and recognizable
     usage text.
   - Sort-order test: under `tempfile.TemporaryDirectory()` create a
     `gh` shim on `$PATH` that emits a fixture JSON list of actionable
     issues (each carrying a `feature:` + `priority:` label) mixing all
     four priorities, with non-monotonic `createdAt` values inside each
     priority bucket. Invoke the script and assert: priority order
     (critical → high → medium → low) and ascending `createdAt` inside
     each bucket.
   - Actionability-selection test: a fixture mixing actionable issues
     (valid `feature:` + valid `priority:`) against non-actionable issues
     (missing a `feature:` label, missing a `priority:` label, an
     unrecognized priority value, or neither). Assert the selected set is
     exactly the actionable issues (the non-actionable ones are excluded).
   - Network-dependent listing against real GitHub is covered by the
     Phase F end-to-end smoke test, not by this unit test.

3. **`triage-issue.py` seven-rule decision table.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/triage-issue.py <issue#>`
   classifies a single issue and emits a JSON object on stdout:

   ```json
   {
     "issue": 123,
     "decision": "work" | "close-not-planned" | "defer" | "research",
     "reason_code": "<short-tag>",
     "rationale": "<one sentence>",
     "feature": "<feature-name or null>",
     "features": ["<feature-name>", "..."],
     "contract_touch": true,
     "priority": "critical" | "high" | "medium" | "low" | null,
     "issue_type": "bug" | "enhancement" | null,
     "created_at": "2026-01-02T03:04:05Z" | null,
     "blocked_by": [124],
     "duplicate_of": 90 | null,
     "planning_note": "<non-empty string for defer/research, else null>"
   }
   ```

   The `duplicate_of` field (Inv 60) is the matched closed issue's number when
   rule 3's duplicate-detection heuristic fires (`reason_code=duplicate`), else
   `null`. It is the canonical issue the duplicate resolves to;
   `resolve-duplicate.py` reads it to record the native duplicate state.

   The `issue_type` and `created_at` fields (see Inv 48) feed the
   bug-vs-enhancement and age signals of the computed priority score (Inv 44),
   and are emitted on EVERY record so `plan-batch.py`'s `_computed_score` can
   consume them. `issue_type` is `"bug"` (GitHub `bug` label, wins if both
   present), `"enhancement"`, or `null`. `created_at` echoes the issue's
   ISO-8601 UTC `createdAt` (trailing-`Z` preserved) or `null`.

   The `priority` field is the issue's `priority:<level>` label value or
   `null`. It is the PRIMARY ordering key `plan-batch.py` consumes for Stage-1
   selection (Inv 4); an omitted `priority` collapses the ordering to the
   contract-touch-only tiebreak, so triage MUST emit it on every record.

   The `features` field (Inv 26) is the sorted distinct set of feature dirs the
   item MENTIONS — the full-mention transparency set — the union of THREE
   detection methods: (a) the `feature:<name>` label; (b) every
   `.claude/features/<name>/` path referenced in the body; and (c) every
   canonical feature name (discovered by listing `.claude/features/` at triage
   time) appearing as a whole word (`\b<name>\b`) in the body OR title. Method
   (c) catches features named in prose or a table without the full path. A
   malformed-labels issue carries `features: []`.

   The `edit_features` field (Inv 51) is the sorted distinct EDIT-TARGET set —
   the features the item will WRITE to, NARROWER than `features`: the
   `feature:<name>` label PLUS body `.claude/features/<name>/` PATHs EXCEPT
   read-only-line paths (Inv 51(a.2)); bare-name mentions (method (c)) are
   EXCLUDED. The SHAPE-routing basis (Stage 2 / Inv 26(b)), `[]` when malformed.

   The decision set is EXACTLY `{work, defer, close-not-planned, research}`.
   `close-completed` is NEVER emittable from triage — a completed closure is
   the merge phase's job (Inv 6 step 4 via `item-status.py close --reason
   completed --commit-sha`). Every `defer` and `research` decision MUST carry
   a non-empty `planning_note`; `work` and `close-not-planned` carry
   `planning_note: null`.

   ### Research/investigation classification

   A research/spike item asks for FINDINGS, not a behavior change. Since the
   loop's only code-producing shape is a TDD-cycle PR, without a dedicated home
   such items would be wrongly closed `not-planned` — a valid issue dropped,
   violating Inv 25 (convergence). Triage routes them to the research dispatch
   shape (Inv 27). Classification runs AFTER rule 7 would return `work`
   (alongside comment-thread reconciliation) and NEVER overrides a
   `close-not-planned` / `blocked` / `malformed-labels` verdict. Detection
   signals (ALL must hold, so a normal "implement X" item is never misrouted):

   1. **Research verb present.** The title OR body contains a research verb
      (case-insensitive whole-word): `study`, `evaluate`, `investigate`,
      `survey`, `assess`, `recommend`, `compare`, `explore`.
   2. **No concrete code-change target.** No `.claude/features/<name>/` path
      beyond the labelled feature dir, and no imperative implement/fix/add
      phrasing pointing at a behavior change.
   3. **Findings/recommendation requested.** The body asks for a
      recommendation, findings, a report, an analysis, or an evaluation.

   When all three hold, triage emits `decision=research`,
   `reason_code=research`, and a non-empty `planning_note`. A research item is
   NEVER `close-not-planned` and NEVER `work`/`dispatch`.

   The script reads only:
   - Issue metadata via `gh issue view <N> --repo <repo> --json
     number,title,body,labels,state,stateReason,comments`. The `comments`
     array (`[{body, createdAt, author}, …]`, oldest first) and `stateReason`
     (e.g. `"reopened"`) feed comment-thread reconciliation (below).
   - The named feature's spec head matter (frontmatter + first section only)
     for rule 6, resolved dual-read (flat `docs/spec.md` preferred; legacy
     `specs/spec.md` / `docs/spec/spec.md` fallbacks).
   - The named feature's `feature.json` (rule 4 — `status` field).
   - Closed issues in the last 30 days (rule 3) via `gh issue list --state
     closed --search "closed:>=<date>"`.

   It MUST NOT read the codebase at large or any spec outside the named
   feature's head matter. Repo discovery uses `rabbit_issue._gh.repo_slug`
   (same as `fetch-queue.py`). No filesystem mutations.

   Decision rules (evaluated top-down, first match wins):

   | Rule | Condition | decision | reason_code |
   |---|---|---|---|
   | 1 | Issue lacks `feature:<name>` OR `priority:<level>` label | `defer` | `malformed-labels` |
   | 2 | Feature named by label does not exist at `.claude/features/<name>/` | `close-not-planned` | `unknown-feature` |
   | 3 | Issue title is a case-folded substring match of a closed-in-last-30-days issue's title (the DETECTION heuristic; the matched closed issue's number is echoed in `duplicate_of`) | `close-not-planned` | `duplicate` |
   | 4 | Feature's `feature.json.status == "retired"` | `close-not-planned` | `feature-retired` |
   | 5 | The issue is blocked by a still-open dependency. The AUTHORITATIVE source is the GitHub-native dependency relationship (`gh api repos/{slug}/issues/<n>/dependencies/blocked_by` returns a blocker whose `state` is `open`); the body `blocked-by: #N` text declaration is a deprecating coexistence mirror, consulted only when the native source reports no open blocker | `defer` (set `blocked_by`) | `blocked` |
   | 6 | Feature's spec head matter already documents the requested behavior verbatim (case-folded substring match of the issue title's content-word tail) | `close-not-planned` | `already-spec'd` |
   | 7 | Otherwise actionable; refined by research classification and comment-thread reconciliation | `work` / `research` / `defer` | `actionable` / `research` / `needs-judgment` |

   `contract_touch` is `true` iff the issue carries a
   `feature:contract` label OR the body literally declares any path
   under `.claude/features/contract/`.

   **Ambiguity default:** Any case the seven rules cannot resolve
   (e.g. unparsable spec head matter, `gh` returning a payload missing
   expected fields) defaults to `decision=defer`,
   `reason_code=needs-judgment`. The triage MUST NEVER fall through
   silently to `work`; the loop under-dispatches rather than
   over-dispatches.

   The blocked-state authority (rule 5) is the GitHub-native dependency
   relationship (Inv 59): triage reads `gh api
   repos/{slug}/issues/<n>/dependencies/blocked_by` and defers `blocked`
   when ANY listed blocker is still `open`. The body-text declaration is a
   deprecating coexistence mirror, consulted ONLY when the native source
   reports no open blocker so in-flight issues that pre-date a native link
   are not stranded. The body mirror is STRUCTURAL, never substring: a prose
   mention of the `blocked-by:` token mid-sentence — an issue that merely
   DESCRIBES the mechanism — is NOT a declaration and passes through as
   actionable, NEVER deferred. Only a STRUCTURAL declaration counts: the
   concrete `blocked-by: #N` form, or a line that STARTS with the
   `blocked-by:` token after only optional list/quote markers. A structural
   declaration that botches the issue number defers `needs-judgment`; an
   ambiguous prose occurrence resolves conservatively toward `work`.

   The duplicate authority (rule 3, Inv 60) separates DETECTION from
   RESOLUTION. Detection stays the case-folded substring heuristic above —
   the confidence gate is unchanged. Resolution is recorded in the
   GitHub-native duplicate state: the loop closes the duplicate issue with
   `gh api --method PATCH repos/{slug}/issues/<n> -f state=closed -f
   state_reason=duplicate`, the authoritative native marker, and cross-links
   the canonical issue (`duplicate_of`) so the native relationship is
   visible. A reinvented `duplicate` label is a deprecating coexistence
   mirror honored only on read; the native `state_reason=duplicate` is
   authoritative going forward.

   ### Comment-thread reconciliation

   Triage MUST read the FULL comment thread, not just the body: a body is
   frozen at filing time, and a maintainer who realizes the framing was wrong
   corrects it in a comment (often reopening/retitling). Reconciliation runs
   AFTER rule 7 would return `work`, never overrides a `close-not-planned` /
   `blocked` / `malformed-labels` verdict, and refines an actionable verdict
   between `work` and `defer`:

   1. **Detection signals** (any one triggers analysis):
      - A comment is present AND `stateReason == "reopened"`
        (case-insensitive) — STRONG signal; always reconcile.
      - A comment body contains supersession language (case-insensitive
        substring: `supersedes`, `correction`, `corrected proposal`,
        `ignore the original`, `revised scope`, `original body was wrong`) —
        treat as an authoritative correction.
      - Title and body describe DIFFERENT targets — a conflict when the title
        carries a path/target token (a `docs/...`/`specs/...` path, or text
        after a `→`/`->` arrow) absent from the body while the body declares
        its own distinct token.

   2. **Resolution:**
      - Correction comment present with coherent intent → MOST RECENT coherent
        intent is authoritative: `decision=work`, `reason_code=actionable`,
        `rationale` noting a `correction` was applied and naming the source.
      - Title/body conflict where the latest signal yields a single coherent
        target → latest/title wins: `decision=work`, `rationale` noting the
        conflict and winner.
      - Genuinely AMBIGUOUS (no single coherent latest intent) →
        `decision=defer`, `reason_code=needs-judgment`, `planning_note` of the
        form `"Body and correction comment conflict on target [X vs Y]; need
        maintainer clarification before dispatch."`.

   3. **No-signal pass-through:** no comments and no title/body conflict →
      the unreconciled base (`decision=work`, `reason_code=actionable`, no
      correction). Strict no-regression requirement.

   Exit code: 0 on successful classification (any decision); non-zero
   on `gh` failure or other unexpected error (stderr passthrough).

   Enforced by `test/test-triage-rules.py` (a `gh` shim on `$PATH` under
   `tempfile.TemporaryDirectory()` serves fixture `gh issue view` / `gh issue
   list` / `gh api .../dependencies/blocked_by` responses; no live network):
   one unit test per decision-table row (7 rules) from fixtures under
   `test/fixtures/triage/`; the native-dependency blocked path (OPEN native
   blocker defers `blocked`; all-CLOSED native blockers actionable; the body
   `blocked-by: #N` mirror still defers when no native blocker exists);
   a `needs-judgment`
   ambiguity case (a STRUCTURAL leading `blocked-by:` line with no integer
   ref) AND its converse — a body that merely MENTIONS the `blocked-by:`
   token in prose passes through as `work`/actionable, never deferred;
   comment-thread
   reconciliation (a correction comment → `decision=work` with `correction`
   noted in the `rationale`; an ambiguous reopened-retitle conflict →
   `decision=defer` / `needs-judgment` naming both targets; no comments and no
   conflict → the unreconciled `decision=work` no-regression base); research
   classification (a "study X" findings body → `decision=research`, never
   `close-not-planned`; a normal "implement X" item stays `work`); and a
   `--help` smoke.

4. **`plan-batch.py` conflict-graph + barrier dispatch planner.** The CLI
   `cat triage.json | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py [--max-parallel N]`
   reads a JSON array of triage objects on stdin and emits a
   deterministic dispatch plan to stdout. Items whose `decision` is
   neither `"work"` nor `"research"` are silently dropped
   (`close-not-planned`, `defer`, etc.) — the caller MAY pass a
   pre-filtered work-only array OR the full unfiltered triage output of
   `triage-batch.py` (per Inv 18 the standard pipe is
   `fetch-queue | triage-batch | plan-batch`). `research` items are retained
   (see "Research items" below). An item flagged `decomposition_parent: true`
   is also filtered out of the plan (Inv 58): a decomposition parent converges
   via child rollup, not dispatch. A still NATIVELY-BLOCKED item (a non-empty
   `blocked_by` of OPEN blockers plus a blocked-origin `reason_code`) is likewise
   filtered out even when its `decision` reads `work` (Inv 62).

   ```json
   {
     "selection_order": [124, 125, 123, 130],
     "dispatch_shapes": {"124": "parallel-per-feature", "125": "multi-subagent-barrier", "123": "decomposition", "130": "research"},
     "computed_scores": {"124": 0.55, "125": 0.42, "123": 0.30, "130": 0.30},
     "barrier_first": [123, 124],
     "groups": [[125, 126], [127]],
     "research_items": [130]
   }
   ```

   `computed_scores` (Inv 44) is the loop-computed priority
   score per selected item (issue-number string → float in `[0, 1]`), the
   PRIMARY ordering key; see Inv 44 for the signal blend.

   `selection_order` (Stage 1, Inv 26) and `dispatch_shapes` (Stage 2,
   Inv 26) are the two decoupled decisions; the `barrier_first` / `groups`
   partition (steps 1–4 below) is the parallel-dispatch grouping for the
   shape-1 items. The `--decompose-threshold N` flag (default 10, integer
   ≥ 1) sets the distinct-feature count at/above which an item's shape is
   `decomposition`.

   Each input item carries at least: `issue` (int), `feature` (string),
   `contract_touch` (bool), and `priority` (one of `critical` / `high`
   / `medium` / `low`; missing or unrecognized → sorts last). It MAY carry
   `features` (the distinct feature-dir set from triage); when absent the
   item is treated as touching one feature (the `feature` label).

   The script is a pure JSON processor — no `gh`, no `git`, no
   filesystem reads or writes other than stdin/stdout.

   `--max-parallel N` (default 4) is the cap. It MUST be integer-valued and
   ≥ 1; non-integer or `< 1` exits non-zero with an argparse error.

   Algorithm (computed-score-primary, barrier-secondary):

   **The loop's `computed_score` is the PRIMARY ordering key; the
   contract-touch barrier is the SECONDARY tiebreak, never a global override
   of the score.** A higher-scoring non-contract item dispatches BEFORE a
   lower-scoring contract-touch item; the barrier only sequences
   contract-touch items ahead of non-contract items _within the same score
   tier_. See Inv 44 for the `computed_score` signal blend.

   1. **Sort ALL work items by the composite key**
      `(computed_score desc, contract_touch_rank, issue)`:
      - `computed_score`: the loop-computed priority score in `[0, 1]`
        (Inv 44), descending (higher score dispatches first).
      - `contract_touch_rank`: `True`->0, `False`->1 (contract-touch
        items lead within the same score tier).
      - `issue` ascending (stable final tiebreak).
   2. **`barrier_first` is the leading run of contract-touch items** in that
      sorted order (those before the first non-contract item; EMPTY if the
      highest-scoring item is non-contract). The remainder (from the first
      non-contract item onward) feeds the conflict-graph grouping.
   3. **Build a conflict graph on the remainder.** Nodes are issues; an
      edge exists between A and B iff `A.feature == B.feature`.
   4. **Greedy graph coloring.** Walk the remainder in composite-key order,
      assigning each issue the lowest-numbered color (group index) with no
      neighbor in it. `groups` is the color partition, in color order.
   5. **Apply `--max-parallel` cap.** A group over the cap is split into
      consecutive sub-groups of size ≤ cap (parallel-safe within each;
      processed sequentially).

   `selection_order` (Stage 1) and `barrier_first` (Stage 2) agree on
   ordering: both derive from the same composite key, so a contract item never
   leads `barrier_first` unless it also leads `selection_order`.

   **Research items** (the 4th dispatch shape) are sorted into
   `selection_order` by the same composite key and get
   `dispatch_shapes[issue] = "research"` plus a `research_items` entry
   (sorted ascending; the key is always present, empty when none). They are
   EXCLUDED from `barrier_first` and `groups` (findings, not code).

   Exit code: 0 on success; non-zero on malformed stdin JSON or
   invalid `--max-parallel` value.

   Enforced by `test/test-plan-batch.py`: a contract-only set → all in
   `barrier_first`, `groups == []`; a same-feature set → one group per item
   (graph coloring forbids sharing); a mixed-feature set → a single group; an
   over-cap set with `--max-parallel 3` → sub-groups of size ≤ 3; priority over
   barrier (a `critical` non-contract item leads `selection_order` while a `low`
   contract item leaves `barrier_first` EMPTY); same-tier barrier tiebreak (two
   `high` items → the contract item precedes and holds `barrier_first`); a
   `research` item appears in `selection_order` with `dispatch_shapes[N] ==
   "research"` and `N` in `research_items`, absent from `barrier_first`/`groups`,
   the co-batched work item unaffected; and a `--help` smoke.

5. **`safety-check.py` five bottom-line invariants.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/safety-check.py <pr#> --phase {merge|release|cleanup} [--next-tag vX.Y.Z]`
   enforces the bottom-line safety invariants from design doc §9
   before any merge / release / cleanup action runs.

   **The next tag is passed via the
   `--next-tag vX.Y.Z` flag, NOT via env var.** The flag is REQUIRED
   iff `--phase release` and FORBIDDEN for `--phase merge|cleanup`.

   Six bottom-line checks (numbered for stable cross-reference; check 6 is the
   pre-merge install smoke, see the dedicated top-level Inv 63 below):

   | # | Invariant | Enforced in phases |
   |---|---|---|
   | 1 | Current git branch is the resolved integration target (`dev` OR `main` during the coexistence window; see Inv 61) | all |
   | 2 | PR base branch (via `gh pr view <#> --json baseRefName`) is an accepted integration target (`dev` OR `main` during coexistence; see Inv 61) | merge, release |
   | 3 | PR head branch (via `gh pr view <#> --json headRefName`) matches `^feat/.+` AND is not `dev`, `main`, or `release/...` | cleanup |
   | 4 | The tag passed via `--next-tag vX.Y.Z` does not already exist (`git rev-parse <tag>^{}` exits non-zero) | release |
   | 5 | No uncommitted modifications to tracked files — both `git diff --quiet` (unstaged) and `git diff --cached --quiet` (staged) exit 0. Untracked files (`??`) are intentionally ignored: they cannot affect a merge, and counting them deadlocked the loop whenever a new runtime artifact appeared. | all |
   | 6 | The isolated install + update smoke passes (spec Inv 63): the sibling `install-smoke.py` runs a network-free fresh install + `--update` of rabbit-cage's install.py against the current tree and exits 0 | merge |

   Phase-specific gating:
   - `merge` enforces checks 1, 2, 5, 6.
   - `release` enforces checks 1, 2, 4, 5.
   - `cleanup` enforces checks 1, 3, 5.

   Exit code: 0 on pass; non-zero on any violation. On violation, the
   stderr line names the violated invariant (`Invariant N (<short>)
   failed: <detail>`); the script never auto-fixes.

   The script reads `gh` and `git` state only — it makes no filesystem
   mutations of its own. The install smoke (check 6, Inv 63) runs entirely
   inside its own tempdir (cleaned up on exit), so the working tree is
   untouched.

   Enforced by `test/test-safety-check.py` under
   `tempfile.TemporaryDirectory()` fixtures:
   - One negative test per invariant: violate each in isolation
     (wrong branch / wrong PR base / non-feat head / pre-existing
     tag / tracked-file modification) under the appropriate phase →
     non-zero exit; stderr names the violated invariant.
   - Inv 5 tracked-vs-untracked discrimination: an
     untracked file in the working tree PASSES Inv 5; a tracked file
     with an unstaged modification FAILS; a tracked file with a
     staged modification FAILS; a clean tree PASSES.
   - Install-smoke merge-gating (check 6, Inv 63): a shim install-smoke.py
     (injected via `RABBIT_AUTO_EVOLVE_INSTALL_SMOKE`) that exits non-zero
     FAILS the merge phase (stderr names Invariant 6) and a passing shim
     PASSES; release and cleanup never run the smoke.
   - One positive test per phase: all required invariants satisfied
     → exit 0.
   - `--next-tag` required-when-release: omitting it under
     `--phase release` → argparse error, non-zero.
   - `--next-tag` forbidden-elsewhere: passing it under
     `--phase merge` (or `cleanup`) → non-zero error.
   - `--help` smoke: exit 0 with recognizable usage text.
   - Test fixtures use a real `git init` in a tempdir plus a `gh`
     shim on `$PATH` to serve PR base/head responses; no live network.

   Bottom-line check 6 (the merge-phase install smoke) is the sibling
   `scripts/install-smoke.py`, defined in full as the dedicated top-level
   **Inv 63** below.

6. **`merge-prs.py` + `cleanup-branches.py` delegation and refusal.**
   Both scripts delegate destructive actions to `safety-check.py` and
   emit a per-target JSON result array on stdout. Both always exit 0
   except on argparse / unexpected error — partial-outcome reporting
   is the caller's responsibility.

   ### `scripts/merge-prs.py`

   `python3 .claude/features/rabbit-auto-evolve/scripts/merge-prs.py <pr-list>`

   where `<pr-list>` is a comma-separated list of PR numbers. For each
   PR:
   1. Verify the PR base via
      `gh pr view <#> --json baseRefName -q .baseRefName`.
      Accept any base in the `{dev, main}` coexistence set (Inv 61); if the
      base is NEITHER → record
      `{pr: N, status: "skipped", reason: "base-not-accepted"}` and continue.
   2. Invoke `safety-check.py <pr#> --phase merge`. If non-zero exit →
      record `{pr: N, status: "skipped", reason: "safety-check-failed"}`.
   3. Otherwise call `gh pr merge <#> --squash` — a DIRECT squash merge,
      NOT `--auto` (the `--auto` flag fails with `Auto merge is not allowed
      for this repository` on repos without auto-merge enabled, and
      mergeability is already gated by steps 1–2). When the base IS the default
      branch (`main`), branch-protected with a required review the bot cannot
      satisfy on its own PR, the merge adds `--admin` to override ONLY that
      structural required-review; a `dev`-base merge keeps the plain `--squash`
      with NO `--admin` (Inv 61). On success →
      `{pr: N, status: "merged"}`; on failure →
      `{pr: N, status: "failed", reason: "gh-merge-failed: <stderr>"}`.
   4. After a successful merge, parse the merged PR title AND body
      (`gh pr view <#> --json title,body`) for closing-keyword references —
      `Fixes`/`Closes`/`Resolves #N` and variants, case-insensitive, unioning
      the numbers from either location so a title-only ref also closes and one
      in both is closed once. For each distinct referenced issue, fetch the
      merge SHA
      (`gh pr view <#> --json mergeCommit -q .mergeCommit.oid`) and invoke
      `item-status.py close <N> --reason completed --commit-sha <sha>
      --comment "TDD cycle complete in <sha>"`. The `--commit-sha` flag is
      REQUIRED for a `completed` closure (it must point at the real merge
      commit). Because `gh pr merge --squash` creates the squash commit on the
      REMOTE `dev` only, that SHA is not yet local and `item-status.py` would
      reject the close — so BEFORE the close calls, `merge-prs.py` runs
      `git fetch origin <sha>` (falling back to `git fetch origin dev`) to make
      it locally resolvable, NEVER `git merge` (permission-denied in the loop).
      The fetch is best-effort and never fails the merge. This manual-close
      step is CONDITIONAL on the PR's base — the branch it merged INTO — NOT
      being the default branch (Inv 61): GitHub's native `Fixes/Closes/Resolves`
      auto-close fires ONLY on a merge to the default branch (`main`), so a
      `dev`-base merge (a non-default branch) runs this explicit close while a
      `main`-base merge skips it because the native close fires. The merge SHA
      is still recorded as `last_merged_sha` under either base. `item-status.py close` is
      idempotent against already-closed issues, so it is called
      unconditionally on the dev-target path. Closed issue numbers go in the
      result row under `closed_issues` (sorted); close failures go under
      `close_failed` with a stderr warning and NEVER fail the merge (`status`
      stays `"merged"`); when the step is skipped both lists are empty.
      `item-status.py` is resolved via the `RABBIT_ISSUE_SCRIPT_DIR` env var
      when set, else relative to the repo's
      `.claude/features/rabbit-issue/scripts/`.

   Emits the result array on stdout. Exit 0 always except argparse /
   unexpected error.

   ### `scripts/cleanup-branches.py`

   `python3 .claude/features/rabbit-auto-evolve/scripts/cleanup-branches.py <pr-list>`

   For each merged PR:
   1. Derive head branch via
      `gh pr view <#> --json headRefName -q .headRefName`.
   2. If head does NOT match `^feat/.+` (or is `dev`, `main`, or
      starts with `release/`) → emit a stderr warning and record
      `{pr: N, branch: <head>, status: "skipped", reason: "non-feat-branch"}`.
   3. Otherwise invoke `safety-check.py <pr#> --phase cleanup`. If
      non-zero → record
      `{pr: N, branch: <head>, status: "skipped", reason: "safety-check-failed"}`.
   4. Otherwise call `git branch -D <branch>` (best-effort; non-zero
      exit acceptable — local branch may legitimately not exist) and
      `git push origin --delete <branch>`. On success → `status: "deleted"`;
      on `git push --delete` failure → `status: "failed"`.

   Emits result array on stdout. Exit 0 always except argparse /
   unexpected error.

   ### Refusal invariant

   `merge-prs.py` NEVER calls `gh pr merge` on a PR whose base is outside the
   `{dev, main}` coexistence set; `cleanup-branches.py` NEVER deletes a branch
   not matching `^feat/.+`. Defense-in-depth above `safety-check.py` — gating
   destructive actions even if `safety-check.py` were skipped.

   ### Tests

   `test/test-merge-prs.py`: a `--help` smoke; skip-on-base-not-accepted (a
   base that is neither `dev` nor `main`, e.g. `release/x` → `skipped` /
   `base-not-accepted`; `gh pr merge` NEVER called); coexistence (target=`dev`:
   a `dev`-based PR merges AND the manual close runs; target=`main`: a
   `main`-based PR merges AND the manual close is skipped); skip-on-safety-fail
   (safety-check non-zero → `skipped` / `safety-check-failed`; `gh pr merge`
   NEVER called); happy path → `merged`, exit 0; the no-`--auto` regression
   (the recorded `gh pr merge` MUST NOT contain `--auto`, still `--squash`);
   the admin-override merge axis (a `main`-base merge records `gh pr merge
   --squash --admin`; a `dev`-base merge records `gh pr merge --squash` WITHOUT
   `--admin`);
   close-after-merge (a body referencing `Fixes`/`Closes`/`Resolves`
   (case-insensitive) → `item-status.py` invoked once per distinct issue with
   `close <N> --reason completed --commit-sha <merge-sha>`, the row carries
   `closed_issues`; no refs → not invoked; a close failure leaves `status:
   "merged"` with the issue under `close_failed`; skipped PRs NEVER invoke it);
   fetch-before-close (a body with refs → `git fetch origin <merge-sha>` runs
   BEFORE the first close so the SHA resolves locally and the close succeeds,
   NEVER `git merge`).

   `test/test-cleanup-branches.py`: a `--help` smoke; skip-on-non-feat-branch
   (`headRefName=main` → `skipped` / `non-feat-branch`, stderr warning, no
   deletion); happy path (`feat/xyz` + safety-check pass → `deleted`, exit 0).

   Both suites use `tempfile.TemporaryDirectory()` + `git init` + a combined
   `gh`/`safety-check.py` shim on `$PATH`; no live network.

7. **`release-bump.py` priority-to-semver bumper.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/release-bump.py <pr#> [--features-threshold N]`
   reads the merged PR's labels, body, and changed-file list, applies
   the design-doc §9 bump table, runs `safety-check.py` under
   `--phase release --next-tag vX.Y.Z` BEFORE any git operation, then creates
   and pushes the annotated tag and a GitHub release targeting `dev`.

   `--features-threshold N` (default 3) sets the distinct-features-touched
   threshold for the major-bump rule.

   Bump table (evaluated top-down; major triggers always override
   minor/patch):

   | Trigger | Bump | `trigger` field |
   |---|---|---|
   | Issue body contains `bump:major` directive | major (`X+1.0.0`) | `body-directive` |
   | PR diff touches ≥ N distinct top-level feature directories under `.claude/features/` | major | `feature-count-threshold` |
   | PR diff touches any file under `.claude/features/contract/schemas/` | major | `contract-schema-touch` |
   | `priority:high` or `priority:critical` label | minor (`X.Y+1.0`) | `priority-high-critical` |
   | `priority:low` or `priority:medium` label | patch (`X.Y.Z+1`) | `priority-low-medium` |

   "Distinct top-level feature directories" = unique values of the
   second path segment (after `.claude/features/`) across the PR's
   changed-file list.

   **Priority source — PR label, with closing-issue fallback (Inv 46).** The `priority:<level>` consulted by the bump table is
   resolved in this precedence:

   1. If the PR itself carries a `priority:<level>` label, that label
      wins (unchanged). The closing issue is NOT consulted.
   2. Otherwise, resolve the closing issue from the PR body — the first
      `Fixes|Closes|Resolves #<N>` reference (case-insensitive) — and
      read THAT issue's `priority:<level>` label via
      `gh issue view <N> --json labels`. Use it as if it were on the PR.
   3. If neither the PR nor a resolvable closing issue carries a
      priority label (no reference, unresolvable issue, or issue without
      a priority label), keep the existing default → `patch` /
      `priority-low-medium`.

   This fallback is necessary because the dispatch flow opens PRs WITHOUT
   copying the source issue's priority label; without it every auto-evolve
   release would patch-bump. Resolution is deterministic (script-tier) and
   does not affect the major-trigger rows, which are evaluated first.

   Execution order:
   1. `gh pr view <#> --json number,title,labels,body,files` → fetch
      metadata + changed-file list. When the PR carries no
      `priority:<level>` label and no major trigger fires, resolve the
      closing issue from the body and `gh issue view <N> --json labels`
      to obtain the fallback priority (Inv 46).
   2. Apply bump table → determine the bump kind.
   3. `git describe --tags --abbrev=0` → `prior_tag`. A tag-free repo (the
      first-release case) makes `git describe` exit non-zero; this is NOT an
      error — `prior_tag` is `null` and `next_tag` is the fixed `v1.0.0`
      regardless of bump kind (the bump table only increments an EXISTING
      version), so the loop cuts its first release instead of crashing. When
      a `prior_tag` exists, `next_tag = vX.Y.Z` by applying the bump kind.
   4. `safety-check.py <pr#> --phase release --next-tag <next_tag>`.
      Non-zero → emit `{status: "skipped", reason: "safety-check-failed"}`
      and stop (no git mutation, exit 0).
   5. `git tag -a <next_tag> -m "<auto-evolve> #<pr> <title>"`.
   6. `git push origin <next_tag>`.
   7. `gh release create <next_tag> --notes-from-tag --target <integration
      target>` — the resolved integration target (Inv 61: default `dev`,
      `main` under the coexistence override).

   Output JSON (single object on stdout):

   ```json
   {
     "pr": 348,
     "prior_tag": "v0.5.2",
     "next_tag": "v0.5.3",
     "bump": "patch",
     "trigger": "priority-low-medium",
     "status": "released" | "skipped" | "failed",
     "reason": "<short>"
   }
   ```

   Exit 0 always except argparse / unexpected error.

   Enforced by `test/test-release-bump.py`: one test per bump-table row (5
   cases, each fixture exercising one trigger → assert `bump` + `trigger`);
   safety-check fail → `{status: "skipped", reason: "safety-check-failed"}` with
   NO `git tag`; `--features-threshold 5` override (4 features, no other major
   trigger → minor, not major); the closing-issue priority fallback (Inv 46) (a
   PR with NO priority label whose body `Closes #N` where issue N is
   `priority:high` → minor / `priority-high-critical`, case-insensitive
   `Fixes|Closes|Resolves`; an explicit PR label wins, `gh issue view` NOT
   called; both unlabeled → patch); first release (a tag-free repo makes `git
   describe` exit non-zero → `prior_tag: null`, `next_tag: "v1.0.0"`, `status:
   "released"`, for would-be minor/major/patch alike); and a `--help` smoke. The
   suite reuses the `tempfile.TemporaryDirectory()` + `git init` +
   `gh`/`git`/`safety-check.py` shim pattern.

8. **`classify-merge-restart.py` three-rung refresh ladder.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/classify-merge-restart.py <pr#>`
   reads the merged PR's file list via `gh pr view <#> --json files`
   and emits one of three literal rung names on stdout (followed by a
   single newline; no JSON):

   - `restart`
   - `refresh`
   - `no-op`

   The output line is consumed by the loop tick's
   `case`/`if`-style comparison; the trailing newline is required.

   Rungs are evaluated in this order; first match wins
   (`restart` > `refresh` > `no-op`):

   | Rung | Trigger (any file in the PR's diff matches) |
   |---|---|
   | `restart` | (a) any path containing `settings.json`, OR (b) a brand-new file under `.claude/skills/*/SKILL.md` (additions > 0 AND deletions == 0 — i.e. pure-add), OR (c) any path matching `.claude/hooks/*.py`, OR (d) any path matching `.claude/agents/*.md` — agent definitions load at session start, so BOTH a pure-add AND a modification require a restart |
   | `refresh` | any path matching `.claude/features/policy/*.md` OR `CLAUDE.md` (at any depth) |
   | `no-op` | none of the above |

   For the "brand-new SKILL.md" sub-rule, the deterministic check is
   that the `gh pr view --json files` entry for that path reports
   `additions > 0` and `deletions == 0` (a pure addition). The
   implementer MAY substitute `gh pr diff <#> --name-only` plus a
   git ls-files comparison if cleaner — tests assert behavior, not
   the specific gh command used.

   Exit code: 0 on success; non-zero on `gh` failure or other
   unexpected error (stderr passthrough).

   The script reads only the `gh` CLI output stream — no git
   shellouts, no filesystem mutations.

   Enforced by `test/test-classify-merge-restart.py` (a `gh` shim on `$PATH`
   serving fixture file-list JSON; no live network): `restart` from a
   `settings.json` touch, a brand-new `.claude/skills/foo/SKILL.md` add, a
   `.claude/hooks/bar.py` modification, and both a brand-new add and a
   modification of `.claude/agents/foo.md`; `refresh` from
   `.claude/features/policy/coding-rules.md` and from a `CLAUDE.md` touch;
   `no-op` from an arbitrary other-feature script touch; precedence
   (`settings.json` + a policy change → `restart`, not `refresh`); and a
   `--help` smoke.

9. **`update-state.py` + state schema persistence.** The CLI
   `cat new-state.json | python3 .claude/features/rabbit-auto-evolve/scripts/update-state.py`
   reads a JSON state object on stdin, validates it against
   `scripts/schemas/auto-evolve-state.schema.json`, and writes the
   validated state to `<repo_root>/.rabbit/auto-evolve-state.json`
   atomically via temp+rename.

   ### Schema

   Schema lives at
   `scripts/schemas/auto-evolve-state.schema.json` and declares the
   following fields (all required unless noted):

   | Field | Type | Notes |
   |---|---|---|
   | `schema_version` | string | Literal `"1.4.0"` |
   | `updated_at` | string | ISO 8601 UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ` |
   | `queue` | array of objects | each `{issue: int, decision: string, feature: string}` |
   | `last_merged_sha` | string \| null | last PR merge commit SHA |
   | `last_tagged_version` | string \| null | last release tag (e.g. `"v0.5.3"`) |
   | `consecutive_failures` | int | ≥ 0 |
   | `stop_requested` | bool | stop marker observed |
   | `restart_needed` | string \| null | reason string when set, else null (NOT a pure boolean) |
   | `in_flight` | array of int (optional) | no longer required (schema 1.4.0): subsumed by `dispatch_journal` (Inv 54). Still accepted as an optional field for backward compatibility; a state carrying it still validates |
   | `defer_counts` | object (optional) | per-issue consecutive-defer counter (Part B), keyed by issue-number string → non-negative int. Additive in schema 1.1.0; absent in pre-1.1.0 states |
   | `pending_post_merge` | array of int (optional) | merged PR numbers owed post-merge processing (phases 8–10). Additive in schema 1.2.0; absent in pre-1.2.0 states. See Inv 30 |
   | `dispatch_journal` | object (optional) | per-tick dispatch record keyed by tick-id string (Inv 54). Additive in schema 1.4.0; absent in pre-1.4.0 states |

   The schema file carries top-level `schema_version`, `owner`, and
   `deprecation_criterion` keys per spec-rules §3. Every bump is
   backward-compatible additive (older states still validate): 1.1.0 added
   `defer_counts` (Part B); 1.2.0 added `pending_post_merge`; 1.4.0 added
   `dispatch_journal` and dropped `in_flight` from the required set (Inv 54).

   ### `update-state.py`

   1. Read full stdin via `sys.stdin.read()`; parse as JSON.
   2. Validate against the schema (use `jsonschema` if importable; else
      inline minimal validator covering the table above).
   3. If invalid → write violation detail to stderr; exit non-zero;
      do NOT touch the state file.
   4. If valid → write to
      `<repo_root>/.rabbit/auto-evolve-state.json.tmp`, then
      `os.rename()` to `<repo_root>/.rabbit/auto-evolve-state.json`
      (atomic on POSIX). `<repo_root>` defaults to current working
      directory; can be overridden by `RABBIT_AUTO_EVOLVE_STATE_DIR`
      environment variable for tests.

   Exit code: 0 on successful write; non-zero on schema-validation
   failure or write error.

   ### `restart_needed` typing rule

   `restart_needed` is `string | null`. The string carries the
   restart reason (e.g. `"settings.json change"`, `"new skill: foo"`).
   Pure boolean is REJECTED by the schema — booleans get type-error
   responses. `null` indicates no restart is needed.

   Enforced by `test/test-state-persistence.py`: round-trip (valid object →
   update-state.py → read back, field-by-field equality); missing-required-field
   (each omission → non-zero, stderr names the field, file NOT created);
   `restart_needed` typing (accept `null` / a reason string; reject `true`,
   `42` with type-mismatch detail); atomicity (a stale state is fully replaced,
   no partial write/merge); `--help` smoke.

10. **`rabbit-auto-evolve` SKILL documents 6 subcommands and the
    12-phase tick.** `skills/rabbit-auto-evolve/SKILL.md` documents
    six subcommands. The SKILL MUST NOT pin a `model:` field in
    frontmatter — the user's default session model handles the
    dispatch; the heavy work (TDD subagent runs, triage decisions)
    is delegated to subagents which select their own model. The
    activation surface (`on`/`off`) lives on this SKILL — NOT on
    `/rabbit-config` (see Inv 11).

    - `on` — invokes `scripts/set-evolve-mode.py on` (which performs
      the three mutations per Inv 1). On success, prints a
      user-facing line instructing the user to restart Claude (so
      `permissions.defaultMode: bypassPermissions` from
      `settings.local.json` is picked up) and then run
      `/rabbit-auto-evolve start`.
    - `start` — invokes `scripts/check-preconditions.py` which
      reports on the three preconditions
      (`.rabbit-auto-evolve-active` present, `human-approval` off,
      `bypass-permissions` on) as structured JSON
      (per Inv 21). The skill MUST route on the report shape — it
      MUST NOT dump the raw failing-checklist to the user. Routing
      table:

      | Precondition shape | Action |
      |---|---|
      | `all_pass: true` | Invoke `scripts/start-loop.py` (writes `.rabbit-auto-evolve-running`), run one tick, call `ScheduleWakeup` to chain the next. |
      | `all_pass: false` AND `active-marker` check is `ok: false` (fresh state — user hasn't activated yet) | Automatically invoke `/rabbit-auto-evolve on` (Inv 1 runs the 3 mutations and emits the branded restart confirmation). End the turn after the branded prompt — the user restarts Claude, then runs `start` again. Do NOT show the failing checklist; do NOT ask for permission. The natural-language intent ("enter auto-evolve mode") is sufficient consent. |
      | `all_pass: false` AND `active-marker` check is `ok: true` but `bypass-permissions` check is `ok: false` (markers exist but user forgot to restart Claude after a previous `on`) | Surface a SHORT branded reminder line (`🔁 Markers set — restart Claude Code, then /rabbit-auto-evolve start again`). Do NOT re-run `on` (markers are already correct); do NOT show the full checklist. |
      | Any other `all_pass: false` shape | Surface the failing `checks[].detail` strings (this branch handles genuinely unexpected states, e.g. partial corruption). |

      Auto-on routing on fresh state keeps a single user intent from
      fragmenting into a two-step manual flow.
    - `stop` — invokes `scripts/stop-loop.py` (writes
      `.rabbit-auto-evolve-stop-requested`); the next tick observes and does
      NOT call `ScheduleWakeup`.
    - `status` — read-only: queue length, in-flight set, last-merged PR,
      last-tagged version, consecutive-failure count, restart marker (if any).
    - `tick` — internal; walks the 12 phases (0–11) in order, naming every
      script invoked (`set-evolve-mode.py`, `fetch-queue.py`,
      `triage-issue.py`, `plan-batch.py`, `safety-check.py`, `merge-prs.py`,
      `release-bump.py`, `cleanup-branches.py`, `classify-merge-restart.py`,
      `update-state.py`) and the disk-state path
      (`.rabbit/auto-evolve-state.json`).
    - `off` — invokes `scripts/set-evolve-mode.py off` to reverse the three
      mutations cleanly (delete `.rabbit-auto-evolve-active`,
      `permissions.defaultMode`, `.rabbit-human-approval-bypass`).

    SKILL.md also describes in-loop discovery handling (design §6): a HANDOFF's
    `discovered_issues` are filed via `rabbit-issue`; an `aborted_reason` labels
    `blocked-by:#N` on the original issue and leaves it open.

    Enforced by `test/test-tick-skill.py`,
    `test/test-start-stop-skill.py`,
    `test/test-on-off-surface.py`, and
    `test/test-discovered-issues.py`.

11. **No `auto-evolve` configurable in `feature.json` — activation
    surface is `/rabbit-auto-evolve on|off`.** `feature.json` does
    NOT declare an `auto-evolve` entry under `configuration`. Were
    such an entry present, `/rabbit-config auto-evolve on|off` would
    dispatch it — but the auto-evolve mode is a self-driving loop,
    not a configurable, and surfacing it through `/rabbit-config`
    muddles the model.

    The activation surface lives on the rabbit-auto-evolve SKILL
    itself: `on` and `off` subcommands (Inv 10) which invoke
    `scripts/set-evolve-mode.py {on|off}` (Inv 1). The
    `restart_required` contract still holds — the `on` subcommand
    surfaces the restart instruction inline in its printed output
    (rather than via a configurable's `restart_required: true`
    field, which would require the rabbit-config dispatch path).

    The `configuration` array in `feature.json` MUST be empty (or
    absent) — enforced by `test/test-prompts-declared.py`.

12. **`feature.json` declares the `prompts` and `runtime` entries
    binding rabbit-auto-evolve to the rabbit dispatcher.** The
    manifest's `prompts` array contains exactly one entry:

    ```json
    {
      "id": "rabbit-auto-evolve",
      "kind": "skill",
      "inject": [
        ".claude/features/policy/philosophy.md",
        ".claude/features/policy/spec-rules.md",
        ".claude/features/policy/coding-rules.md"
      ],
      "slots": ["args"]
    }
    ```

    Every `inject` entry MUST be a repo-relative path to an existing
    file (verified by the prompt dispatcher at SessionStart). Bare
    names (e.g. `"philosophy"`) are FORBIDDEN — the dispatcher does
    not resolve them and the Stop hook surfaces a
    `prompt-injection failures: <feature>` line.

    A matching passthrough template lives at
    `.claude/features/contract/templates/prompts/rabbit-auto-evolve.txt`.

    The `runtime` object carries:

    - `SessionStart`: `[{"api": "emit_auto_evolve_banner", "args": {}}]`
    - `Stop`: `[{"api": "emit_auto_evolve_stop_line", "args": {}}]`

    Both APIs are implemented by `contract.lib.runtime` per
    contract Inv 65; the suppression of the per-configurable
    `human-approval` and `bypass-permissions` alerts when
    `.rabbit-auto-evolve-active` is present is contract Inv 64.

    The `surface.skills` array contains `["rabbit-auto-evolve"]`;
    the `manifest` contains exactly one `publish_skill` entry
    pointing at `skills/rabbit-auto-evolve/SKILL.md`.

    Enforced by `test/test-prompts-declared.py`.

13. **In-loop AskUserQuestion ban (Red Flag).**
    While `.rabbit-auto-evolve-running` is present, the dispatcher
    MUST NOT emit `AskUserQuestion` calls. The user has affirmatively
    delegated authority by entering auto-evolve mode; routine
    "should I continue?" prompts are forbidden.

    On a genuine hard blocker (a test failure with no obvious fix,
    a safety violation, a spec ambiguity not covered by resolved Qs),
    the dispatcher writes `.rabbit-auto-evolve-aborted` with the
    abort reason and ends the turn without calling `ScheduleWakeup`.
    The next SessionStart banner surfaces the abort.

    This rule is recorded in the `Red Flags — STOP` section of
    `skills/rabbit-auto-evolve/SKILL.md` as the literal string:

    > **While `.rabbit-auto-evolve-running` is present, the dispatcher MUST NOT emit `AskUserQuestion` calls.**

    Enforced by `test/test-skill-no-askuserquestion-rule.py`, which
    asserts the literal rule string appears in SKILL.md.

14. **End-to-end banner suppression contract.** When
    `.rabbit-auto-evolve-active` is present at the repo root, the
    SessionStart and Stop dispatchers emit the auto-evolve composite
    banner (`emit_auto_evolve_banner` / `emit_auto_evolve_stop_line`)
    INSTEAD of the per-configurable alerts for `human-approval` and
    `bypass-permissions`. When the marker is absent, the standard
    per-configurable alert lines emit normally and the auto-evolve
    banner is a no-op.

    Composite banner shape:
    - Line 1 (red, always present when marker exists):
      `AUTONOMOUS-EVOLVE MODE ACTIVE — composite (human-approval +
      bypass-permissions + auto-evolve marker)`.
    - Line 2 (yellow), content varies by adjunct markers:
      - Neither `.rabbit-auto-evolve-restart-needed` nor
        `.rabbit-auto-evolve-aborted` present: literal start command
        to paste (`paste: /rabbit-auto-evolve start`).
      - `.rabbit-auto-evolve-restart-needed` present: a line
        matching the literal substring `resume after restart: paste
        /rabbit-auto-evolve start`.
      - `.rabbit-auto-evolve-aborted` present (highest precedence):
        a line matching the literal substring `loop aborted on safety
        violation` (full text may also surface the abort reason from
        the marker file).

    Enforced by `test/test-banner-suppression.py` exercising four
    scenarios (marker-absent, marker-present, marker+restart-needed,
    marker+aborted) against a synthetic `.claude/features/` tree
    under `tempfile.TemporaryDirectory()`. The test exercises the
    real `contract.lib.runtime` APIs (contract Inv 65) by importing
    them as a module — no shell
    invocations of the dispatchers.

    Line-2 text ownership is held by `scripts/banner-status.py` (Inv 22),
    which `contract.lib.runtime.emit_auto_evolve_banner` invokes.

15. **Feature-shape compliance.** All four version fields agree:
    `feature.json.version` == spec.md frontmatter `version` ==
    contract.md frontmatter `version` == SKILL.md frontmatter
    `version`.

    `feature.json` and SKILL.md MUST carry non-empty `owner` and
    `deprecation_criterion`. `feature.json.summary` MUST mention
    `rabbit-auto-evolve` (the skill name). Every entry in
    `feature.json.surface.skills` MUST have a matching entry in
    `contract.md` `provides.skills` (name + version).

    Enforced by `test/test-feature-shape.py`. Going forward, every
    landing change that touches any of the four versioned artifacts
    MUST bump them in lockstep — test-feature-shape will fail
    otherwise.

16. **Script references in SKILL.md MUST be feature-relative.**
    Every script path inside `skills/rabbit-auto-evolve/SKILL.md`
    (in subcommand sections, in the 12-phase tick table, in any
    Bash example) MUST use the literal prefix
    `.claude/features/rabbit-auto-evolve/scripts/`. Bare
    `scripts/<name>.py` is forbidden because Claude resolves SKILL
    paths relative to the SKILL.md's own location
    (`.claude/skills/rabbit-auto-evolve/`), which has no `scripts/`
    subdirectory — `publish_skill` copies only `SKILL.md`, not the
    scripts dir.

    Enforced by `test/test-on-off-surface.py` (asserts the on/off
    sections contain the full feature-relative prefix) and
    `test/test-tick-skill.py` (asserts every script reference in
    the 12-phase table uses the full prefix).

17. **All runtime-marker writes go through scripts (never literal
    `touch` in SKILL.md).** rabbit-auto-evolve owns five runtime
    markers at the repo root:

    | Marker | Written by | Script |
    |---|---|---|
    | `.rabbit-auto-evolve-active` | `on` subcommand | `scripts/set-evolve-mode.py on` |
    | `.rabbit-auto-evolve-running` | `start` subcommand | `scripts/start-loop.py` (write) / `scripts/end-tick.py` (delete) |
    | `.rabbit-auto-evolve-stop-requested` | `stop` subcommand | `scripts/stop-loop.py` |
    | `.rabbit-auto-evolve-restart-needed` | tick (when classify-merge-restart returns `restart`) | `scripts/mark-restart-needed.py "<reason>"` |
    | `.rabbit-auto-evolve-aborted` | tick (on safety violation) | `scripts/mark-aborted.py "<reason>"` |
    | `.rabbit-auto-evolve-restart-advised` | tick (advisory restart, Inv 52) | `scripts/advise-restart.py write "<reason>"` (write) / `scripts/advise-restart.py status` (read) / `scripts/advise-restart.py clear` (delete) |

    SKILL.md MUST NOT instruct Claude to literally `touch` or
    `echo > <marker>`. Scope-guard inspects the Bash command string
    and would deny such writes because the markers are not on its
    allowlist. Routing through a `python3 <script>.py` invocation
    hides the marker write inside the Python process, which
    scope-guard cannot inspect — this is the same pattern that
    `set-evolve-mode.py` already uses for `.rabbit-auto-evolve-active`.

    Marker write semantics:
    - `start-loop.py` and `stop-loop.py` take no args; the marker
      content is the literal string `session` (matching the
      `set-evolve-mode.py` convention).
    - `mark-restart-needed.py` and `mark-aborted.py` take a single
      positional `reason` arg and write it as the marker's content
      so that the SessionStart banner can surface it
      (per Inv 14 scenarios 3 + 4).
    - All four scripts are idempotent: re-running is a no-op if the
      marker already exists with the same content; with different
      content the marker is overwritten.

    Enforced by `test/test-loop-markers.py` (round-trip + idempotency
    for all 4 scripts) and `test/test-start-stop-skill.py` (asserts
    the SKILL.md `start` / `stop` sections contain the script
    invocations and DO NOT contain bare `touch .rabbit-auto-evolve-*`
    or `echo .* > .rabbit-auto-evolve-*` patterns).

18. **`triage-batch.py` bridges fetch-queue → plan-batch.** The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/triage-batch.py`
    reads a JSON array on stdin (the raw `gh issue list` shape from
    `fetch-queue.py`: `[{number, title, labels, body, createdAt}, …]`)
    and emits a JSON array of triage objects on stdout (the shape
    defined by Inv 3). It invokes `triage-issue.py <number>` in
    a subprocess for each input item; the per-issue triage objects
    are concatenated into a single array in input order.

    Failure semantics: a per-issue `triage-issue.py` non-zero exit yields a
    synthesized object `{issue: N, decision: "defer", reason_code:
    "triage-failed", rationale: "<stderr snippet>", feature: null,
    contract_touch: false, blocked_by: []}` and the batch CONTINUES — the
    script never aborts mid-batch (graceful degradation for tick liveness).

    Exit code: 0 on success (including with per-issue failures
    handled as defer entries); non-zero on malformed stdin JSON.

    `triage-batch.py` locates `triage-issue.py` via the same
    `RABBIT_AUTO_EVOLVE_SCRIPT_DIR` env override as the marker scripts (test
    seam).

    **Anti-infinite-defer counter (Part B).** `triage-batch.py` owns a
    per-issue consecutive-defer counter persisted in
    `.rabbit/auto-evolve-state.json` under the `defer_counts` map (keyed by
    issue-number string; state dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`,
    matching `update-state.py`). For each triaged issue:

    - a `defer` decision INCREMENTS the issue's counter; if it was already
      ≥ 3 (the 4th consecutive defer) the decision is FORCED to `work` with
      `reason_code: defer-limit-reached`, the accumulated planning-note
      history is surfaced in `planning_note`, and the counter resets to 0.
    - any non-`defer` decision RESETS the counter to 0 (it tracks
      CONSECUTIVE defers, not lifetime).

    The updated `defer_counts` map is written back via atomic temp+rename
    (read-modify-write, preserving every other state key). Persistence is
    best-effort: with no state file or a parse failure, counts default to
    empty and decisions pass through — tick liveness must never depend on the
    state file existing. This enforces the convergence guarantee in Inv 25.

    The canonical tick pipe in SKILL.md phases 3–5:

    ```
    python3 .claude/features/rabbit-auto-evolve/scripts/fetch-queue.py \
      | python3 .claude/features/rabbit-auto-evolve/scripts/triage-batch.py \
      | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py --max-parallel 4
    ```

    `plan-batch.py` silently drops items with `decision != "work"` (per
    Inv 4) so the unfiltered triage array passes through cleanly.

    Enforced by `test/test-triage-batch.py`:
    - Happy path: 3-item fetch-queue fixture on stdin + a
      `triage-issue.py` shim on PATH (or via
      RABBIT_AUTO_EVOLVE_SCRIPT_DIR) that emits 3 valid triage
      objects → output is a 3-item array in input order.
    - Per-issue failure: shim that exits non-zero for one issue →
      that issue's slot is filled with `defer/triage-failed`; the
      other two succeed; overall exit 0.
    - Malformed stdin JSON → non-zero exit, stderr names the
      parse error.
    - Defer counter (Part B): a shim that always defers
      the same issue, run 4 ticks against a seeded state file →
      decision sequence is `defer, defer, defer, work` and the
      forced-work entry carries `reason_code: defer-limit-reached`.
    - Defer-counter persistence: after one defer tick the state
      file's `defer_counts['<issue>']` is 1 and all pre-existing
      state keys are preserved.
    - Defer-counter reset: a state seeded with a non-zero count for
      an issue that then triages to a non-defer decision resets that
      issue's counter to 0.
    - No state file: defer decisions still pass through unchanged
      (best-effort persistence; tick liveness preserved).

19. **`start-loop.py` self-healing (the explicit user `start` entry).**
    `start-loop.py` is the entry the EXPLICIT USER `start` runs; it performs
    two self-healing steps tied to that user intent. It does NOT write the
    `.rabbit-auto-evolve-running` marker — that write is owned by the shared
    phase-walk (Inv 42), which runs the running-guard first and writes the
    marker only on `proceed`. The two self-heal steps are:

    1. **Cancel any pending stop.** If
       `.rabbit-auto-evolve-stop-requested` exists at the repo
       root, delete it. Rationale: invoking `start` is an explicit
       "I want this to run" signal — it cancels any pending stop
       (typical scenario: previous session was killed mid-tick,
       leaving the stop marker behind from a `stop` invocation that
       was never observed by a subsequent tick). This stop-cancel is the
       SOLE path that clears the stop marker (Inv 41): a MACHINE-fired
       `tick` invokes the shared phase-walk directly and never runs
       `start-loop.py`, so a heartbeat can never resurrect a halted loop.
    2. **Bootstrap state file.** If
       `.rabbit/auto-evolve-state.json` does NOT exist OR is empty
       OR fails JSON parse, create it with default content:

       ```json
       {
         "schema_version": "1.0.0",
         "updated_at": "<now ISO 8601 UTC>",
         "queue": [],
         "in_flight": [],
         "last_merged_sha": null,
         "last_tagged_version": null,
         "consecutive_failures": 0,
         "stop_requested": false,
         "restart_needed": null
       }
       ```

       If the file exists and parses successfully, leave it alone.
       Use the atomic write convention from Inv 9
       (`update-state.py`): write to `.tmp` then `os.rename` to
       avoid partial-write races.

    Enforced by `test/test-loop-markers.py`:
    - Pre-seed `.rabbit-auto-evolve-stop-requested`, invoke
      `start-loop.py`, assert: stop-requested marker is gone AND the
      running marker was NOT written (the shared phase-walk owns that
      write per Inv 42).
    - Pre-create an empty `.rabbit/auto-evolve-state.json`, invoke
      `start-loop.py`, assert: state file is now valid JSON with
      default content.
    - Pre-create a valid (non-default) state file, invoke
      `start-loop.py`, assert: state file is UNCHANGED (no
      clobbering of real state).

20. **Every tick ends with `end-tick.py`.** The tick MUST invoke
    `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`
    as its last action on EVERY exit path:

    - Normal completion (12-phase walk done, `ScheduleWakeup` called).
    - Phase 0 halt (stop-check observed `.rabbit-auto-evolve-stop-requested`).
    - Safety-violation abort (writes `.rabbit-auto-evolve-aborted` then ends).
    - Error abort (unexpected exception in any phase).

    `end-tick.py` deletes `.rabbit-auto-evolve-running` (mirror of the
    shared phase-walk's running-marker write, Inv 42). Idempotent: missing
    marker is a no-op. Without this, the running marker leaks across
    sessions and the user has to `rm -f` it manually — which scope-guard
    correctly denies.

    SKILL.md's tick documentation MUST show the `end-tick.py`
    invocation in EVERY documented exit path, not only the
    happy-path final phase.

    Enforced by `test/test-loop-markers.py` (round-trip:
    pre-create the running marker, invoke `end-tick.py`, assert
    it's gone; idempotency: invoke again with marker absent,
    exit 0) and `test/test-start-stop-skill.py` (asserts
    SKILL.md tick documentation contains
    `.claude/features/rabbit-auto-evolve/scripts/end-tick.py`).

21. **`check-preconditions.py` owns start preconditions.** The
    CLI `python3 .claude/features/rabbit-auto-evolve/scripts/check-preconditions.py`
    inspects the three `start` preconditions and emits a
    structured JSON report on stdout:

    ```json
    {
      "all_pass": false,
      "checks": [
        {"id": "active-marker",       "ok": false, "detail": ".rabbit-auto-evolve-active missing — run /rabbit-auto-evolve on"},
        {"id": "approval-bypass",     "ok": false, "detail": "neither .rabbit-human-approval-bypass nor .rabbit-tdd-autonomous present — run /rabbit-auto-evolve on"},
        {"id": "bypass-permissions",  "ok": false, "detail": "permissions.defaultMode != bypassPermissions in .claude/settings.local.json — restart Claude after /rabbit-auto-evolve on"}
      ]
    }
    ```

    Exit code is ALWAYS 0 — the verdict is carried in `all_pass`,
    not in the exit code. The script reads files only (`os.path.exists`
    + json parse of `.claude/settings.local.json`) and never invokes
    `ls`, `test -f`, or any other command that would exit non-zero
    on the expected "not yet activated" path. The SKILL.md `start`
    section MUST invoke this script and MUST NOT use bare `ls
    .rabbit-auto-evolve-*` patterns — those produce ugly stderr
    noise (`ls: cannot access ...: No such file or directory`)
    when files are legitimately absent.

    The three check IDs are stable identifiers (`active-marker`,
    `approval-bypass`, `bypass-permissions`). Callers may rely on
    their presence and order in the `checks` array.

    **Dual-read of the bypass marker (Phase 1 coexistence window).**
    The `approval-bypass` check is satisfied
    when EITHER the legacy `.rabbit-human-approval-bypass` OR the
    new `.rabbit-tdd-autonomous` marker is present at the repo root
    (OR logic — if either exists the check passes). The
    `human-approval` configurable is being renamed to `tdd-autonomous`
    (with a polarity flip); Phase 1 makes this reader accept both
    names so Phase 2 can rename the live on-disk marker without
    breaking the running auto-evolve loop. The `detail` string names
    whichever marker is present (or both, for transparency); when
    neither is present it mentions both names. Only this reader is
    dual-read in Phase 1; `set-evolve-mode.py` (the writer) and the
    subcommand/polarity are unchanged until Phase 2. The fallback to
    the legacy name will be dropped once Phase 2 renames the live
    marker and the coexistence window closes.

    Enforced by `test/test-check-preconditions.py`:
    - All three missing → `all_pass: false`, all three checks
      report `ok: false` with the documented `detail` strings.
    - All three present (legacy bypass marker) → `all_pass: true`,
      all three checks report `ok: true`.
    - `.rabbit-tdd-autonomous` present (active + new bypass marker +
      bypass-permissions) → `approval-bypass` reports `ok: true`.
    - Both bypass markers present → `approval-bypass` reports
      `ok: true`.
    - Partial (active marker exists, neither bypass marker set) →
      `all_pass: false`, only the failing checks report `ok: false`.
    - Exit code is 0 in all cases.

    `test/test-start-stop-skill.py` extends to assert SKILL.md
    `start` section contains the `check-preconditions.py`
    invocation AND does NOT contain bare `ls .rabbit-auto-evolve-*`
    patterns.

22. **`banner-status.py` owns active-banner line-2 text.** The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/banner-status.py`
    inspects rabbit-auto-evolve's runtime markers at the repo root
    and emits a JSON object on stdout describing the active banner.
    Always exits 0.

    When `.rabbit-auto-evolve-active` is absent:

    ```json
    {"active": false, "line1": null, "line2": null}
    ```

    When `.rabbit-auto-evolve-active` is present:

    ```json
    {
      "active": true,
      "line1": {"text": "AUTONOMOUS-EVOLVE MODE ACTIVE", "icon": "🤖", "color": "red"},
      "line2": {"text": "<see precedence table>", "icon": "<emoji>", "color": "<color>"}
    }
    ```

    Line-2 chosen by precedence (first match wins):

    | Adjunct marker(s) | line2.text contains substring | icon | color |
    |---|---|---|---|
    | `.rabbit-auto-evolve-aborted` (highest) | `loop aborted on safety violation` | 🛑 | red |
    | `.rabbit-auto-evolve-restart-needed` | `resume after restart` | 🔁 | yellow |
    | `.rabbit-auto-evolve-running` (NEW) | `loop in progress` | 🔄 | yellow |
    | none, `.rabbit/auto-evolve-state.json` ABSENT | `auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start` | ⏸ | yellow |
    | none, `.rabbit/auto-evolve-state.json` PRESENT | `paste: /rabbit-auto-evolve start` | ▶ | yellow |

    Marker contents (for aborted/restart-needed) MAY be concatenated
    into the text for surfacing the reason, but the substring listed
    above is always present.

    The two `none` rows distinguish the post-`on`/pre-`start`
    window from a started-then-idle loop, exactly as the symmetric
    Stop-hook line does (`contract.lib.runtime.emit_auto_evolve_stop_line`,
    Inv 55). `set-evolve-mode.py on` writes the activation markers but NOT
    `.rabbit/auto-evolve-state.json`; only `start-loop.py` creates that file
    on the first `start`. So its ABSENCE means "configured but never started
    — a restart is pending", and the restart-pending line2 is emitted
    VERBATIM the same as the Stop line so the SessionStart banner and the
    Stop line agree. Once the loop has been started at least once (state
    file present) the `paste: /rabbit-auto-evolve start` idle line is
    retained, extended for SessionStart↔Stop symmetry with the same next-tick
    ETA the Stop line carries, computed by mirroring Inv 55's cadence
    computation (the contract helper is a private internal, so this mirrors it
    rather than depending on it): read the heartbeat cron from repo-root
    `.claude/scheduled_tasks.json`, parse its MINUTE field against an
    unrestricted HOUR, and walk to the next matching wall-clock minute from an
    injectable `now`.

    The ETA is rendered as a single EXACT wall-clock time `HH:MM` — no `≥`,
    no `~`, no range, no qualifier. It is the next cron boundary PLUS the
    deterministic CronCreate jitter offset (Inv 56). CronCreate adds a
    deterministic per-job jitter to recurring tasks: recurring jobs fire up to
    10% of their period late, capped at 15 min. On an idle session this is a
    stable constant — the `13,43 * * * *` (30-min period) heartbeat fired a
    constant `+13` min late every time (ETA 21:43 fired 21:56, 22:13 fired
    22:26, 22:43 fired 22:56). So the honest displayed minute is
    `boundary + observed_jitter_minutes`, where `observed_jitter_minutes` is the
    empirically observed offset persisted by Inv 56 (computed from the recorded
    fire history; on a cold start with no recorded fires it falls back to the
    documented bound `min(15, ceil(period_minutes * 0.10))`). The ETA degrades
    to the bare idle line when the cadence is absent/unparseable. Only this
    started-then-idle line carries an ETA; the priority-marker, restart-pending,
    and `{active: false}` lines never do.

    The script reads the five runtime markers via `os.path.exists` and
    additionally probes for `.rabbit/auto-evolve-state.json` via
    `os.path.isfile` (the never-started distinction); for the idle ETA it
    reads `.claude/scheduled_tasks.json` for the cadence and the persisted
    jitter offset `.rabbit/auto-evolve-tick-jitter.json` (Inv 56) for the
    `observed_jitter_minutes` to add to the boundary — no other filesystem
    access, no git, no `gh`. Repo root resolution uses the
    `RABBIT_AUTO_EVOLVE_REPO_ROOT` env override fallback to `os.getcwd()`
    (matching the marker-write scripts). The wall-clock for the ETA is
    overridable via `RABBIT_AUTO_EVOLVE_NOW` (ISO-8601) for deterministic
    tests, falling back to the real clock.

    This script owns all line-2 text variants (including the `running`
    variant); `contract.lib.runtime.emit_auto_evolve_banner` invokes it
    to render the SessionStart banner's line 2.

    Enforced by `test/test-banner-status.py`:
    - Active marker absent → `{active: false, line1: null, line2: null}`.
    - Active only, state file ABSENT → `line2.text` is
      `auto-evolve configured — restart Claude Code, then run /rabbit-auto-evolve start`,
      icon ⏸, color yellow.
    - Active only, state file PRESENT, no cadence source → `line2.text`
      is the bare `paste: /rabbit-auto-evolve start` (no ETA), color yellow.
    - Active only, state file PRESENT, cadence source present → `line2.text`
      appends `, next tick HH:MM` where `HH:MM` is the next cron boundary plus
      `observed_jitter_minutes` (Inv 56) — a single exact time, no `≥`, no `~`,
      no qualifier, no range.
    - Active only, state file PRESENT, unparseable cadence → bare idle line,
      no ETA.
    - No rejected wording (`≥`, `(scheduler jitter)`, `(fires when the session
      is next idle)`, the idle-gating lower-bound framing) appears anywhere in
      `scripts/banner-status.py`.
    - The restart-pending and running lines carry no ETA even when the
      cadence source is present.
    - Active + running → `line2.text` contains `loop in progress`.
    - Active + restart-needed → `line2.text` contains `resume after restart`.
    - Active + aborted → `line2.text` contains `loop aborted on safety violation`.
    - Precedence: active + running + restart-needed → restart-needed wins.
    - Precedence: active + running + aborted → aborted wins.
    - Precedence: active + restart-needed + aborted → aborted wins.
    - Precedence: a priority marker wins even when the state file is absent.
    - Exit 0 in all cases.

23. **All runtime markers MUST be gitignored.** The repo-root
    `.gitignore` MUST carry the glob `.rabbit-auto-evolve-*` so that
    every one of the five runtime markers
    (`.rabbit-auto-evolve-active`, `.rabbit-auto-evolve-running`,
    `.rabbit-auto-evolve-stop-requested`,
    `.rabbit-auto-evolve-restart-needed`,
    `.rabbit-auto-evolve-aborted`) is excluded from `git status`.
    Without this gitignore entry, `safety-check.py` Invariant 5
    ("working tree clean") fails during the `merge` phase whenever
    the loop is running — the active and running markers show as
    `??` untracked files and every PR merge is refused, deadlocking
    the loop indefinitely. The gitignore entry belongs alongside the
    existing `.rabbit-human-approval-bypass` and `.rabbit-scope-*`
    patterns (same lifecycle: per-session operational state, never
    committed). Enforced by
    `test/test-markers-gitignored.py` which writes the five markers
    in a tempdir initialized as a git repo, copies the repo-root
    `.gitignore` into the tempdir, runs `git status --porcelain`,
    and asserts none of the five marker basenames appear in the
    output. The test fails loudly if `.gitignore` is missing the
    glob or matches only a subset of the markers.

24. **Claude Code runtime files MUST be gitignored.** The repo-root
    `.gitignore` MUST carry entries for `.claude/scheduled_tasks.lock`
    and `.claude/scheduled_tasks.json` — two files created by Claude
    Code's scheduling harness whenever `CronCreate` or `ScheduleWakeup`
    are active. Without these entries both files appear as `??`
    untracked in `git status`, causing `safety-check.py` Invariant 5
    ("working tree clean") to refuse every PR merge attempt as long as
    a Claude Code session is running. The entries belong with the existing
    `.claude/settings.local.json`, `.claude/tdd-report.json`,
    `.claude/worktrees/`, and `.claude/tmp/` exclusions (same lifecycle:
    per-session Claude Code runtime state, never committed). Enforced by
    `test/test-claude-runtime-files-gitignored.py`, which creates both
    files in a tempdir initialized as a git repo, copies the repo-root
    `.gitignore` into the tempdir, runs `git status --porcelain`, and
    asserts neither filename appears in the output.

25. **Triage convergence guarantee (Part E).** The triage
    classifier MUST converge every valid issue to completion. It MAY
    defer dispatch within the loop (up to 3 consecutive deferrals per
    issue, after which dispatch is mandatory). It MAY close an issue as
    not-planned with a strong reason. It MUST NOT close a valid issue as
    completed as a substitute for dispatch. It MUST NOT escalate work to
    human review as a non-dispatch action.

    This invariant is enforced operationally by three mechanisms already
    specified above:

    - **No `close-completed` from triage (Inv 3).** The triage decision
      set is exactly `{work, defer, close-not-planned}`; `close-completed`
      is unreachable from triage. A completed closure is only ever
      asserted by the merge phase (Inv 6 step 4) once work has actually
      landed, with `item-status.py close --reason completed --commit-sha`
      pointing at the real merge commit.
    - **Bounded deferral (Inv 18).** The per-issue consecutive-defer
      counter in `defer_counts` forces `work` on the 4th consecutive
      defer, so an issue can never be deferred indefinitely.
    - **No human-review escape hatch (Inv 13).** While the loop is
      running the dispatcher MUST NOT emit `AskUserQuestion`; the only
      non-dispatch terminal action is `.rabbit-auto-evolve-aborted` on a
      genuine hard blocker — not a routine "kick it to a human" deferral.
    - **No de-queue escape hatch (Red Flag).** While
      `.rabbit-auto-evolve-running` is present, **the dispatcher MUST NOT strip
      the actionability labels (`feature:`/`priority:`) from an OPEN issue as a
      parking or hand-back action.**
      "De-queue" — dropping a queue-gating label while leaving the issue OPEN —
      is the same human-handoff escape that the AskUserQuestion ban (Inv 13)
      forbids, leaking through a different mechanism: stripping the labels that
      make an issue actionable silently exits it from the loop's view and
      strands it open-but-untracked. `fetch-queue.py` selects on ACTIONABILITY
      — valid `feature:` + `priority:` — so removing either label is exactly
      what drops an open issue from the queue; the ban forbids that. The only
      permitted non-work outcomes remain a bounded `defer` (tracked) OR
      `close-not-planned` with a strong reason. This rule is recorded in the
      `Red Flags — STOP` section of `skills/rabbit-auto-evolve/SKILL.md` as the
      literal string:

      > **While `.rabbit-auto-evolve-running` is present, the dispatcher MUST NOT strip the actionability labels (`feature:`/`priority:`) from an OPEN issue as a parking or hand-back action.**

    **Convergence is label-independent.** Every open VALID issue must converge
    to a terminal-or-tracked state — worked → closed-completed,
    close-not-planned with a strong reason, or a bounded defer — and that
    obligation does NOT lapse short of those outcomes. Stripping
    the actionability labels while an issue is open is explicitly NOT a
    convergence outcome: it is the forbidden "de-queue" action. SELECTION and
    convergence share one basis — ACTIONABILITY (valid `feature:` +
    `priority:`), per Inv 2 — so dropping a gating label is the one way to
    drop an open issue the loop is obligated to converge.

    NOTE: a sanctioned, tracked "blocked-on-human-precondition" state — the
    durable home for items that fit neither bounded `defer` nor
    `close-not-planned` (e.g. an item that needs a human-paused window before the
    loop can safely self-modify its own live marker) — is explicitly DEFERRED as
    a maintainer-call follow-up and is NOT introduced here.

    Enforced by `test/test-spec-convergence-invariant.py` (asserts the
    invariant text is present in this spec),
    `test/test-spec-forbid-dequeue-invariant.py` (asserts the
    label-independence clause and the de-queue ban literal are present in spec
    and SKILL.md), `test/test-triage-rules.py` (asserts `close-completed` is
    never emitted and every defer carries a planning_note), and
    `test/test-triage-batch.py` (asserts the 4th consecutive defer is forced
    to `work`).

26. **Work-selection / dispatch-shape decoupling.** The loop
    makes two SEPARATE decisions, in order, and never lets the second
    contaminate the first.

    **(a) Stage 1 work selection is dispatch-shape blind.** The next item(s)
    to work are selected by the loop's `computed_score` (Inv 44 — a blend in
    which the filer `priority:` label `critical` > `high` > `medium` > `low`
    (no-priority last) is ONE weighted input among several), logical readiness,
    and issue age / queue position. Stage 1 MUST NOT consider dispatch shape,
    feature count, or whether the loop "knows how" to do the item.
    `plan-batch.py` emits the Stage-1 result as `selection_order`, ordered by
    the composite key `(computed_score desc, contract_touch desc, issue asc)`
    over work-only items: `computed_score` (Inv 44) is PRIMARY, the
    contract-touch barrier is the SECONDARY tiebreak (contract items lead
    WITHIN a score tier, never across tiers), and issue number is the final
    stable tiebreak. The filer `priority:` label is folded INTO
    `computed_score`, not a standalone primary key — so a higher-scoring `low`
    item can sort ahead of a `medium` whose other observable signals are weaker
    (Inv 44 by design). Because `barrier_first` (Inv 4) derives from the same
    composite key, `selection_order` and `barrier_first` always agree. The
    `contract_touch` flag is a barrier/conflict property, NOT a dispatch shape,
    so consulting it does not violate shape-blindness.

    **(b) Stage 2 picks among exactly THREE shapes in preference order.** For
    each selected work item, `plan-batch.py` emits `dispatch_shapes`
    (issue-number-string → shape), choosing the FIRST fitting shape. The
    item's feature-dir count for shaping is the EDIT-TARGET count
    `len(item["edit_features"])` (from triage), falling back to
    `len(item["features"])` when `edit_features` is absent/empty, then to 1; so
    an item that EDITS one feature but merely MENTIONS another shapes
    `parallel-per-feature` (Inv 51(b)).

    | Rank | Shape key | When it fits | Mechanics |
    |---|---|---|---|
    | 1 (perf preference) | `parallel-per-feature` | item edits exactly one feature dir | one full single-feature TDD touch, its own `.rabbit-scope-active-<feature>` marker; multiple such items dispatch in parallel |
    | 2 | `multi-subagent-barrier` | item edits >1 feature dir, below `--decompose-threshold` (default 10) | per-feature subagents land SERIALLY on ONE shared branch; the serialization contract is: subagent k+1 fetches subagent k's pushed commit before starting; each piece is a full single-feature touch with its own scope marker; one PR closes the item |
    | 3 | `decomposition` | item edits ≥ `--decompose-threshold` feature dirs | file N per-feature sub-issues via the contract INVOKE `rabbit-issue/scripts/file-item.py --parent <parent#>` (NOT a cross-feature edit — do not edit rabbit-issue files), each labelled with the right `feature:<name>` + `priority:<level>` label and born as a GitHub-native sub-issue of the parent; the parent stays OPEN and the sub-issues are queued, re-entering Stage 1/Stage 2 on the next tick; the parent->children linkage is recorded in `decomposition_parents` as a mirror and the parent is closed deterministically off the GitHub-native sub-issue rollup once it shows all sub-issues complete (Inv 53) |

    Every shape uses a full per-feature touch gated by
    `.rabbit-scope-active-<feature>`. The dispatcher MUST NOT skip, defer
    indefinitely, escalate to human, or file a meta-issue as a substitute for
    a valid item merely because it does not fit shape 1 — shapes 2 and 3
    handle cross-feature and very-large items.

    **(c) parallel-per-feature is a performance preference, not a correctness
    requirement.** It is the fastest-throughput shape, but items that do not
    fit it still get done via shapes 2 and 3, just slower.

    **(d) The session-override shape is forbidden — and why.** A proposed
    Stage-2 shape 2 — "sequential single-subagent with scope override",
    claiming "in autonomous mode the human-gating rule does not apply" —
    is STRUCK and MUST NOT be implemented. Per the maintainer's binding
    policy:
    autonomous-evolve ALWAYS uses a full per-feature touch gated by
    `.rabbit-scope-active-<feature>`; it NEVER writes a persistent
    `.rabbit-scope-override session` for feature edits. A one-time override is
    permitted ONLY for plan / temporary-document writing, never for feature
    code edits. **Bounded scope is a hard constraint, not waivable by
    autonomy** (CLAUDE.md philosophy §2 / spec-rules §2): autonomy changes
    *who* the actor is, not *what scope* an actor may write. `plan-batch.py`
    therefore never emits `sequential-with-override` — the valid shape set is
    exactly {`parallel-per-feature`, `multi-subagent-barrier`,
    `decomposition`}.

    Enforced by `test/test-dispatch-shape.py` (single-feature →
    parallel-per-feature; cross-feature independent edits →
    multi-subagent-barrier; very-large 10+-feature item → decomposition;
    Stage-1 selection picks the high-priority cross-feature item before the
    low-priority single-feature item; no shape is ever the struck
    session-override shape and the planner writes no marker), the `features`
    extraction in `test/test-dispatch-shape.py`, and
    `test/test-spec-dispatch-shape-invariant.py` (asserts this invariant text
    is present and that the struck shape is not listed as valid).

27. **Research/Investigation shape — the 4th dispatch shape.**
    The loop has a non-TDD execution path for research/spike/investigation
    items. Such items ("study X", "evaluate Y", "survey Z", "assess the
    tradeoffs", "recommend an approach", "compare A and B", "explore N")
    ask for FINDINGS or a RECOMMENDATION, not a behavior change. Because the
    loop's only code-producing shape is a TDD-cycle PR, before this
    invariant a research item could not be dispatched and was wrongly closed
    `not-planned` — a valid issue silently dropped, violating Inv 25
    (convergence). The research shape gives them a home.

    **(a) Classification (triage).** `triage-issue.py` classifies an item as
    `decision=research` (`reason_code=research`) when ALL three signals hold:
    a research/investigation verb (`study`, `evaluate`, `investigate`,
    `survey`, `assess`, `recommend`, `compare`, `explore`) appears in the
    title or body; the body declares no concrete code-change target; and the
    body asks for a recommendation / findings / report / analysis rather than
    a behavior change (Inv 3 "Research/investigation classification"
    subsection). A research item is NEVER `close-not-planned` (it is valid)
    and NEVER `work`/`dispatch` (it produces no code).

    **(b) Routing (plan-batch).** `plan-batch.py` emits the research shape as
    the 4th dispatch shape alongside `parallel-per-feature`,
    `multi-subagent-barrier`, and `decomposition`. A `decision == "research"`
    item appears in `selection_order` (by the same composite priority sort),
    carries `dispatch_shapes[issue] == "research"`, and its issue number is
    listed under the `research_items` output key. It is EXCLUDED from
    `barrier_first` and from the conflict-graph `groups` partition (Inv 4) —
    findings do not edit code, so the same-feature conflict edges and the
    contract-touch barrier do not apply.

    **(c) Execution.** Findings are produced by a READ-ONLY research
    subagent — it reads the codebase and the issue, and writes nothing
    except the findings document. No TDD cycle, no scope-active marker for
    code edits.

    **(d) Deliverable + close path — disposition by outcome size.** The
    deliverable mode is keyed to the SIZE of the findings, and EITHER WAY the
    request issue ALWAYS ends closed `completed` — findings inline (small) or
    linked (big), never left open, never with the deliverable buried:

    - SMALL outcome (a short verdict, a couple of paragraphs) → append the
      findings directly as a COMMENT on the request issue, then close it
      `completed` (the comment-only path: `item-status.py close --reason
      completed --findings-comment-url <url>`).
    - BIG outcome (substantial analysis, mapping tables, a multi-section
      recommendation) → write a detailed, self-contained findings DOCUMENT
      under the named feature's scope (`docs/decisions/` or `docs/research/`,
      or the historical `docs/findings/<issue-N>-<slug>.md`), with lifecycle
      frontmatter (owner, version, deprecation criterion). No PR is required —
      a direct commit of the findings doc provides the commit SHA. Then close
      the request issue `completed` with a clear pointer/link to the doc
      (`item-status.py close --reason completed --commit-sha <sha>`, the
      existing `completed` gate).

    A committed doc is preferred for the big case over a separate issue: it is
    version-controlled, owned, carries a deprecation criterion, and is
    discoverable in-repo, where a closed issue is an archive with none of
    those. A valid research item is NEVER closed `not-planned`.

    The comment-only close gate (`--findings-comment-url`) is provided by
    `item-status.py`, which is owned by `rabbit-issue` and is NOT edited by
    this feature. Where that gate is not yet available, the committed-doc path
    (`--commit-sha`) is used for both sizes — the small outcome becomes a
    short committed doc — but the issue still ends closed `completed`.

    **(e) Findings disposition is distinct from follow-up work.** This shape
    governs the FINDINGS record only. Any actionable FOLLOW-UP WORK surfaced
    by an exploration (a real code or spec change) is filed as its OWN work
    issue, separate from the findings record — never folded into the research
    item, which closes on the findings alone.

    Enforced by `test/test-triage-rules.py` (a "study X" findings issue →
    `decision=research`, never `not-planned`; a normal "implement X" issue
    stays `work` — the over-trigger guard), `test/test-plan-batch.py` (a
    research item → `dispatch_shapes[N] == "research"`, `N` in
    `research_items`, absent from `barrier_first`/`groups`; a co-batched work
    item unaffected), and `test/test-spec-research-shape-invariant.py`
    (asserts this invariant text is present in the spec).

28. **Parallel TDD dispatches MUST use isolated git worktrees.**
    Phase 6 (`dispatch`) dispatches each selected work item via the
    Agent tool (per Inv 26 the shape is `parallel-per-feature`,
    `multi-subagent-barrier`, or `decomposition`). **Every Agent call for a
    TDD-subagent dispatch MUST include `isolation: "worktree"`.** This is a
    DISPATCHER policy, not a subagent policy — the subagent itself is
    isolation-agnostic; the dispatcher is responsible for requesting an
    isolated worktree on the Agent call.

    **Why.** Without isolation, every parallel TDD subagent shares the
    dispatcher's single shared git working directory. The observed failure
    mode (3 of 4 parallel dispatches in one tick): one subagent's branch
    checkout reverts another's edits; commits land on the wrong branch; and
    each subagent's `.rabbit-scope-active-<feature>` marker clobbers the
    others'. A shared git working directory cannot host concurrent
    branch/HEAD state, so concurrency without per-dispatch isolation
    corrupts the batch. `isolation: "worktree"` gives each dispatch its own
    working tree, branch, HEAD, and scope marker, so parallel dispatches
    (`parallel-per-feature`) and the serial-on-one-branch shape
    (`multi-subagent-barrier`) never collide.

    **Worktree base ref.** Worktrees are created branched from `dev` HEAD —
    NOT from `main`, and NOT as a fresh/detached tree — per the
    `worktree.baseRef: "head"` setting in `.claude/settings.local.json`
    (the session's checked-out branch is `dev`, so `head` resolves to the
    `dev` tip). This keeps each dispatch's base in sync with the latest
    merged work on `dev`.

    **Known limitation (stale base).** The `worktree.baseRef: "head"`
    setting in `.claude/settings.local.json` requires a session restart
    to take effect; until the running session has been restarted after the
    setting was added, newly created worktrees may branch from a stale base
    and a subagent may need to re-branch from `origin/dev` manually at the
    start of its cycle. This is a documented operational limitation of the
    Claude Code worktree harness, not a defect in this feature; it resolves
    on the next session restart and cannot be fixed from within this
    feature's scope.

    This invariant makes passing `isolation: "worktree"` on every TDD
    dispatch a binding requirement rather than a manual practice, so it can
    never be silently dropped.

    Enforced by `test/test-spec-dispatch-worktree-isolation-invariant.py`,
    which asserts this invariant text is present in the spec AND that both
    the source and deployed `SKILL.md` document the
    `isolation: "worktree"` dispatch requirement.

29. **`status-report.py` owns the `status` subcommand output.** The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/status-report.py`
    is the deterministic backing script for the read-only `status`
    subcommand. It replaces the prior LLM-assembled ad-hoc `ls`/`cat`/`jq`
    pipeline — a non-deterministic, untestable surface that drifted and
    emitted `ls: cannot access ...` noise on a fresh clone — per spec-rules
    §1 (`script > CLI > spec > prompt`).

    The script reads ONLY:
    - `<repo_root>/.rabbit/auto-evolve-state.json` for the five state
      fields. When the file is MISSING, empty, or fails JSON parse, the
      script emits defaults (queue length 0, empty in-flight, null
      last-merged / last-tagged, 0 consecutive-failures) — a missing
      state file is the legitimate fresh-clone case, NOT an error.
    - The five runtime markers via `os.path.exists` only
      (`.rabbit-auto-evolve-active`, `.rabbit-auto-evolve-running`,
      `.rabbit-auto-evolve-stop-requested`,
      `.rabbit-auto-evolve-restart-needed`,
      `.rabbit-auto-evolve-aborted`).

    It performs NO mutations, NO `gh`, NO `git`. Repo root resolution uses
    the `RABBIT_AUTO_EVOLVE_REPO_ROOT` env override with an `os.getcwd()`
    fallback (matching `check-preconditions.py` / `banner-status.py`).

    Output is a single fixed-format JSON object on stdout:

    ```json
    {
      "queue_length": 0,
      "in_flight": [],
      "last_merged_sha": null,
      "last_tagged_version": null,
      "consecutive_failures": 0,
      "markers_present": [],
      "state_file": "absent"
    }
    ```

    - `queue_length` — integer length of the state `queue` array.
    - `in_flight` — the in-flight issue set. DERIVED (Inv 54) as a read-only
      projection of the `dispatch_journal` (the union of `dispatched` /
      `pr_open` issue numbers across tracked ticks, sorted), falling back to
      the literal state `in_flight` array when no journal is present — so the
      surface is unchanged for consumers now that `in_flight` is no longer a
      required field.
    - `last_merged_sha` / `last_tagged_version` — the state fields verbatim
      (string or null).
    - `consecutive_failures` — the state field (integer ≥ 0).
    - `markers_present` — the sorted subset of the five runtime-marker
      basenames that exist at the repo root (empty list when none).
    - `state_file` — one of `"present"` (parsed cleanly), `"absent"`
      (file missing), or `"malformed"` (file present but empty / unparsable);
      the last two both yield the default field values.

    Exit code is 0 on success (including every defaults path). A non-zero
    exit is reserved for genuine invocation errors (e.g. unwritable stdout);
    the verdict lives in the JSON, never in the exit code.

    The SKILL.md `status` subcommand body MUST invoke this script and MUST
    NOT LLM-assemble a bash pipeline or use bare `ls .rabbit-auto-evolve-*`
    / `cat .rabbit/auto-evolve-state.json` patterns — those drift and emit
    stderr noise on a fresh clone.

    Enforced by `test/test-status-report.py`:
    - Known-state fixture: a seeded `.rabbit/auto-evolve-state.json` with a
      non-empty queue, in-flight set, last-merged SHA, last-tagged version,
      and a non-zero failure count → the emitted JSON carries every field
      with the expected values; exit 0.
    - Missing state file (clean tempdir) → defaults emitted
      (`queue_length: 0`, `in_flight: []`, both `last_*` null,
      `consecutive_failures: 0`, `state_file: "absent"`); exit 0.
    - Malformed state file (non-JSON content) → defaults emitted,
      `state_file: "malformed"`, exit 0 (graceful — never crashes the
      read-only status surface).
    - Markers: with a subset of the five markers present, `markers_present`
      is exactly that subset, sorted; with none present it is `[]`.
    - `--help` smoke: exit 0 with recognizable usage text.
    - SKILL surface: the `status` section of both the source and deployed
      `SKILL.md` invokes
      `python3 .claude/features/rabbit-auto-evolve/scripts/status-report.py`
      and contains no bare `ls .rabbit-auto-evolve-*` pattern.

30. **`run-post-merge.py` deterministically runs phases 8–10.**
    Phases 8 (`release`), 9 (`cleanup`), 10 (`catch-up`) were LLM-walked prose
    in SKILL.md; after a large phase-7 (`merge`) batch the orchestrator ended
    the tick for context reasons, SILENTLY dropping them. Per spec-rules §1
    (`script > CLI > spec > prompt`) the sequencing moves into a deterministic,
    non-skippable script.

    ### `pending_post_merge` state field (schema 1.2.0)

    `pending_post_merge` (optional array of int) holds merged PR numbers owed
    post-merge processing; additive in schema 1.2.0 (a state WITHOUT it still
    validates), absent in pre-1.2.0 states. `start-loop.py`'s bootstrap default
    and `update-state.py`'s validator both recognize it. `merge-prs.py`'s
    `--record-pending` flag appends every `status == "merged"` PR number to the
    array in `<state_dir>/auto-evolve-state.json` (read-modify-write,
    de-duplicated, atomic temp+rename; state dir via
    `RABBIT_AUTO_EVOLVE_STATE_DIR`, `<cwd>/.rabbit` fallback). Without the flag
    `merge-prs.py` writes no state; the per-PR stdout result is unchanged.

    ### `scripts/run-post-merge.py`

    `python3 .claude/features/rabbit-auto-evolve/scripts/run-post-merge.py`

    1. Reads `pending_post_merge` from
       `<state_dir>/auto-evolve-state.json` (state dir resolved as above).
    2. If the array is empty, missing, or the state file is absent/malformed,
       it is a CLEAN NO-OP: emit `{"status": "noop", "pending": []}` on
       stdout and exit 0 (no phase script is invoked).
    3. Otherwise, in order:
       - **Phase 8 (release):** invoke `release-bump.py <pr#>` once per
         pending PR. Release success is keyed on `release-bump.py`'s stdout
         JSON `status` field — NOT its exit code (it exits 0 even when
         `status` is `"skipped"` or `"failed"`, so exit code alone cannot
         distinguish an owed-but-dropped release). A `status` other than
         `"released"` (including unparseable stdout) is a NON-success: the
         run does NOT proceed to cleanup/catch-up, sets the result `status`
         to `"failed"` with the offending release JSON, and exits non-zero
         leaving `pending_post_merge` INTACT for the next tick's drain.
       - **Phase 9 (cleanup):** invoke
         `cleanup-branches.py <comma-joined pr-list>` once for the whole set.
       - **Phase 10 (catch-up):** invoke
         `classify-merge-restart.py <pr#>` once per pending PR.
    4. On completion (all phase scripts exited 0), clear
       `pending_post_merge` from state by reading the current state,
       setting `pending_post_merge` to `[]`, and writing it back atomically.
    5. Emit a result JSON object on stdout recording the pending set and each
       phase's outcome.

    Sibling phase scripts (`release-bump.py`, `cleanup-branches.py`,
    `classify-merge-restart.py`) are resolved via the
    `RABBIT_AUTO_EVOLVE_SCRIPT_DIR` env var when set, else this script's own
    dirname.

    Exit code: 0 on success (including the no-op path). Non-zero on any phase
    failure — a phase script exiting non-zero, OR a release-bump `status`
    other than `"released"` (see Phase 8) — so the caller (`end-tick.py` /
    the SKILL schedule phase) sees a loud, locatable failure instead of a
    silently-dropped phase. A failure leaves `pending_post_merge` uncleared
    for the next tick's drain.

    ### SKILL invocation

    The SKILL replaces the prose descriptions of phases 8–10 with a single
    `python3 .claude/features/rabbit-auto-evolve/scripts/run-post-merge.py`
    invocation, called in TWO places:
    - After phase 7 (`merge`) when any PR merged (the merge phase records the
      merged PR numbers via `merge-prs.py --record-pending`).
    - At the START of the tick, between phase 1 (`restart-check`) and phase 3
      (`fetch`), to DRAIN any owed post-merge work from a previous truncated
      tick BEFORE fetching new work.

    Enforced by `test/test-run-post-merge.py`: non-empty `pending_post_merge`
    (e.g. `[10, 20]`) invokes the `release-bump.py`, `cleanup-branches.py`,
    `classify-merge-restart.py` shims IN ORDER (release+catch-up per pending PR; cleanup
    once with the comma-joined list, asserted via a shared ordered call log) and
    clears the field to `[]`, exit 0; empty/missing state is a clean no-op
    (`status: "noop"`, no shim invoked); a phase shim exiting non-zero or a
    `release-bump.py` `{"status": "skipped"}` (exit 0) makes `run-post-merge.py`
    exit non-zero WITHOUT clearing the field (skipped is owed, not success), and
    skipped stops before cleanup/catch-up; `--help` smoke. By
    `test/test-merge-prs.py` (extended): `--record-pending` appends merged PRs
    (de-duplicated), without it no state write. By
    `test/test-spec-post-merge-invariant.py` (e2e): the Inv 30 text is present
    AND both source and deployed SKILL.md invoke `run-post-merge.py` after merge
    AND at tick start.

31. **`check-auto-resume.py` owns mechanical restart-resume detection.**
    Convention-enforced restart recovery (human reads the SessionStart banner,
    Inv 22 `resume after restart` variant, and pastes `/rabbit-auto-evolve
    start`) silently stalls the loop on a missed read. Per spec-rules §1
    (`script > CLI > spec > prompt`) the resume decision moves into a
    deterministic script so the SessionStart hook self-resumes.

    The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/check-auto-resume.py`
    inspects rabbit-auto-evolve's runtime markers at the repo root and emits
    a JSON object on stdout describing whether the loop should auto-resume:

    ```json
    {"resume": true,  "action": "/rabbit-auto-evolve start"}
    {"resume": false, "action": null}
    ```

    **Auto-resume conditions (ALL three must hold for `resume: true`):**

    1. `.rabbit-auto-evolve-active` is present (mode is on), AND
    2. `.rabbit-auto-evolve-restart-needed` is present (a restart was
       needed), AND
    3. `.rabbit-auto-evolve-running` is NOT present (no tick is already
       running).

    When all three hold the script emits `{"resume": true, "action":
    "/rabbit-auto-evolve start"}`; else `{"resume": false, "action": null}`.
    `.rabbit-auto-evolve-aborted` is NOT consulted here — abort handling is the
    banner's responsibility (Inv 22); this script answers only "should we
    re-launch after a restart". Exit code is ALWAYS 0 (verdict in `resume`); it
    reads files only (`os.path.exists`), never `ls`/`test -f`. `<repo_root>`
    defaults to `os.getcwd()`, overridable via `RABBIT_AUTO_EVOLVE_REPO_ROOT`.

    **rabbit-cage integration (cross-scope INVOKE).** rabbit-cage's
    SessionStart hook (owned by rabbit-cage) INVOKEs this script and, when
    `resume` is true, surfaces the `action` — the contract-INVOKE pattern in
    this feature's `invokes` block. The hook wiring is a separate rabbit-cage
    touch filed as a discovered issue; this invariant fixes only the
    rabbit-auto-evolve side (the resume-detection script + documented
    conditions).

    Enforced by `test/test-check-auto-resume.py`:
    - All three conditions met (active + restart-needed, no running) →
      `resume: true`, `action: "/rabbit-auto-evolve start"`.
    - Active + restart-needed but `.rabbit-auto-evolve-running` present →
      `resume: false`, `action: null`.
    - Active present but `.rabbit-auto-evolve-restart-needed` absent →
      `resume: false`, `action: null`.
    - `.rabbit-auto-evolve-active` absent (mode off) → `resume: false`,
      `action: null`.
    - Exit code is 0 in all cases.
    - `--help` smoke: exit 0 with recognizable usage text.

32. **Tick scheduling is owned by the system cron WHERE AVAILABLE, with a
    durable `CronCreate` fallback where crontab is blocked; `ScheduleWakeup`
    and `/loop` are NEVER used in rabbit-auto-evolve.** Self-chaining ticks via
    `ScheduleWakeup` (Inv 29 / Inv 31) coupled cadence to an open session and
    could silently drop the next tick. The architecture replaces self-chaining
    with an EXTERNAL trigger: a single system `cron` entry is the SOLE tick
    scheduler. The two-tier model and CronCreate fallback REFINE this
    additively, without weakening observability.

    **Two-tier tick model** (different re-trigger ownership):

    - The **HOUSEKEEPING tick** (deterministic Claude-free phases 0–1, 2–4, 6,
      7–9, 10), implemented by `tick-headless.py`, NEVER self-chains — the
      external scheduler owns its cadence.
    - The **DEVELOPMENT tick** (phase 6, `dispatch`) needs a live Claude
      session, so the scheduler re-triggers it by firing `/rabbit-auto-evolve
      start` as a one-shot full in-session tick. NOT inline continuation: the
      turn ENDS; context is FRESH on the system-cron path, reused/accumulating
      on the fallback (Inv 33 / D1).

    **Scheduler mechanism + sanctioned fallback.** The default is the system
    `crontab`; where the `crontab` binary is administratively blocked, a durable
    `CronCreate` heartbeat is the SANCTIONED fallback. The forbidden/permitted
    set:

    - `ScheduleWakeup` FORBIDDEN (requires `/loop`, couples cadence to a
      session).
    - `/loop` FORBIDDEN anywhere in this feature.
    - `CronCreate` (the Claude-Code idle-REPL prompt scheduler — `durable`,
      persisting to `.claude/scheduled_tasks.json`; NOT `/loop`, NOT
      `ScheduleWakeup`) PERMITTED solely as the fallback trigger on
      crontab-restricted hosts AND the one-shot immediate-refire (Inv 33 / D1)
      there.

    **CronCreate is a Claude TOOL, not a Python call**, so the scripts own the
    DETERMINISTIC parts — scheduler detection (Inv 34 / D2), the running-guard
    (Inv 35 / D3), decision logging (Inv 36 / D4), the schedule DECISION — while
    the DISPATCHER calls `CronCreate(...)` with the emitted params, as phase 6
    dispatch is the irreducible-Claude action. Observability is upheld by Inv 35
    (stale markers cleared) and Inv 36 (every decision logged), NOT by
    forbidding the fallback.

    **The split between headless and session ticks.**

    - **Headless tick (cron-fired, no Claude session).** The cron entry runs
      `tick-headless.py`, walking the Claude-free phases: 0 (`stop-check`),
      1 (`restart-check`), 3–5 (`fetch | triage | plan`), 7 (`merge` of the
      state's transient `merge_ready` hint field, skipped when empty), 8–10
      (`run-post-merge.py` when `pending_post_merge` non-empty), 11 (`persist`).
      `merge_ready` is a transient hint NOT in the Inv 9 schema, so the headless
      tick drops it before `update-state.py` (validator rejects unknown keys).
      No phase 6 (`dispatch`); no schedule (phase 12 no-op; cron fires next). A
      pending `.rabbit-auto-evolve-stop-requested` or
      `.rabbit-auto-evolve-aborted` marker short-circuits it to a clean no-op.
    - **Session tick (Claude active).** The full SKILL.md 12-phase tick runs
      INCLUDING phase 6. Phase 12 (`schedule`) no longer calls `ScheduleWakeup`
      — it is a documented no-op because the cron owns scheduling.

    **Cron lifecycle (owned by `set-evolve-mode.py`).**

    - `scripts/install-cron.py` installs ONE crontab entry of the form
      `*/30 * * * * cd <repo_root> && python3
      .claude/features/rabbit-auto-evolve/scripts/tick-headless.py >>
      .rabbit/tick-headless.log 2>&1` via the `crontab -l` + append +
      `crontab -` pattern. It is IDEMPOTENT (an existing `tick-headless.py`
      entry yields a clean no-op; two runs leave exactly one entry). Exit 0.

      **Restricted-host CronCreate fallback.** When `crontab` is restricted,
      `install-cron.py` DETECTS it via the SAME permission-denial signal
      `detect-scheduler.py` uses (Inv 34 / D2) — a "not allowed" stderr on
      `crontab -l`, distinguished from the empty "no crontab for user" case —
      and FALLS BACK GRACEFULLY (exit 0), emitting (a) a JSON signal
      `{"scheduler":"croncreate","action":"dispatcher-must-create-heartbeat",
      "cron":"13,43 * * * *","prompt":"/rabbit-auto-evolve start",
      "durable":true}` naming the durable `CronCreate` heartbeat the DISPATCHER
      must create, and (b) a branded `rabbit_print` line (contract Inv 46)
      telling the user the heartbeat is set up on the next start. The heartbeat
      AVOIDS the `:00`/`:30` marks (`13,43 * * * *`, ~30-min). **Single cadence
      source:** codified ONCE in `install-cron.py` as `CADENCE_MINUTES`; both
      the system-cron `SCHEDULE` (`*/N * * * *`) and the heartbeat DERIVE from
      it (heartbeat = same cadence shifted off `:00`/`:30` by a fixed offset),
      so a change propagates to both. `test/test-cron-cadence-source.py` pins
      the source and every spec.md/SKILL.md cron literal.

      **Operational cadence config.** `CADENCE_MINUTES = 30` is the DEFAULT,
      not a floor — cadence is OPERATIONAL CONFIG tunable without editing
      source. `install-cron.py._configured_cadence()` resolves in precedence:
      (1) `RABBIT_AUTO_EVOLVE_CADENCE` env; (2) `cadence_minutes` in
      rabbit-auto-evolve's OWN `<state_dir>/auto-evolve-cadence-config.json`
      (state dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`; NOT
      rabbit-cage's `configuration` nor rabbit-config); (3) `CADENCE_MINUTES`.
      The value is VALIDATED as an integer in `1..59`; out-of-range REJECTED
      (default + branded warning, never a nonsense cron). Both paths read the
      SAME resolved cadence (cadence 15 → `*/15` cron AND a `13,28,43,58`
      heartbeat); default stays `*/30 * * * *` / `13,43 * * * *`. Enforced by
      `test/test-cron-cadence-config.py` (e2e). `RABBIT_CRONTAB_CMD` and
      `RABBIT_AUTO_EVOLVE_REPO_ROOT` overrides preserved.
    - `scripts/uninstall-cron.py` removes the entry via
      `crontab -l | grep -v tick-headless | crontab -`. It is IDEMPOTENT and
      safe when the entry (or any crontab) is absent. Exit 0 including the
      absent case.
    - `set-evolve-mode.py on` invokes `install-cron.py` after writing the
      activation markers; `off` invokes `uninstall-cron.py` before teardown.
      A cron install/uninstall failure is surfaced but does not by itself
      fail the mode flip (best-effort).

    Enforced by `test/test-cron-trigger.py` (e2e): `install-cron.py` installs
    exactly one entry and is idempotent; `uninstall-cron.py` removes it and is
    a safe no-op when absent; AND on a restricted-host `crontab` shim
    (permission denial on `-l`), `install-cron.py` exits 0 and emits the
    `CronCreate`-fallback JSON signal plus the branded heartbeat notice. By
    `test/test-tick-headless.py` (e2e): the headless tick runs phases 0–1,
    3–5 (plan only), 7, 8–10, and 11 without a Claude session, and
    short-circuits on a stop/abort marker. And by
    `test/test-spec-cron-invariant.py` (e2e): this invariant text is present
    AND `ScheduleWakeup` / `/loop` are absent from the spec and from BOTH
    `SKILL.md` copies; `CronCreate` is PRESENT in the SOURCE spec.md and
    SOURCE feature-dir `SKILL.md` as the documented fallback (the deployed
    copy lags and is NOT asserted for `CronCreate`), and both copies document
    the system cron and the headless tick.

33. **Immediate refire when DISPATCHABLE work remains (D1).** At the END of a tick (and equivalently when a heartbeat enters a
    tick), the loop decides whether to schedule the next tick based on
    DISPATCHABLE work — work phase 6 can actually dispatch THIS tick, NOT the
    raw count of open issues: **dispatchable plan non-empty → schedule the next
    tick to fire NEAR-IMMEDIATELY (~1 minute) as a one-shot, then END the turn**
    (do NOT continue inline); **no dispatchable work → schedule nothing; rely on
    the recurring heartbeat.** Dispatchability is the plan's `selection_order`
    from the `fetch-queue.py | triage-batch.py | plan-batch.py` pipe, which DROPS
    blocked/deferred items (open native `blocked_by` + blocked-origin
    `reason_code`, Inv 62), decomposition parents (Inv 58), and non-work verdicts.
    Keying refire off the RAW open count (the prior behaviour) spun the loop into
    a ~1-minute no-op refire storm whenever the only remaining open issues were
    human-gated/blocked — a non-empty open queue but an EMPTY dispatchable plan
    (#1004); the recurring heartbeat already backstops the eventual unblock, so an
    all-gated backlog goes `idle` and quiesces until the heartbeat or a human
    unblock. The refire is a near-immediate one-shot (each fired
    tick is a full in-session tick incl. phase 6 dispatch; the turn ends between
    ticks), NOT inline continuation. Context isolation is PATH-DEPENDENT: on the
    **system-cron / headless path** the refired tick is a brand-new Claude-free
    OS process, so its context starts FRESH; on the **CronCreate fallback path**
    the one-shot re-enters the SAME live session as a NEW TURN, so history is
    REUSED and ACCUMULATES across ticks, bounded by auto-compaction — NOT a fresh
    context. The fresh-context guarantee belongs to the system-cron path ONLY.
    The decision is computed by
    `scripts/schedule-decision.py`, which determines DISPATCHABLE-work presence
    AUTHORITATIVELY by reusing the EXISTING `fetch-queue.py | triage-batch.py |
    plan-batch.py` pipe (the same pipe phase 6 dispatches from) and counting the
    plan's `selection_order` — it neither re-derives the queue nor re-implements
    the blocked/parent/non-work filtering, so the refire count matches exactly
    what phase 6 can dispatch. It reads the scheduler mechanism from
    `detect-scheduler.py` (Inv 34), and emits JSON: dispatchable plan non-empty →
    `{"decision":"immediate-refire","scheduler":"crontab"|"croncreate",
    "prompt":"/rabbit-auto-evolve start","when":"~1min","croncreate":{...}}`;
    no dispatchable work → `{"decision":"idle","detail":"rely on heartbeat"}`. The
    decision is logged via `tick-log.py` (Inv 36). On the `croncreate` path
    the DISPATCHER reads this JSON at phase 12 and performs the actual
    one-shot `CronCreate(...)` (the irreducible Claude action); on the
    `crontab` path the emitted hint documents the transient/`at`-style
    one-shot for the dispatcher/SKILL.

    **Pinned-minute one-shot — benign failure mode.** The
    `croncreate` params MUST carry `recurring: false` AND `durable: false`, and
    the cron expression MUST be a PINNED specific near-future minute (computed
    as the current minute + 2 — a 2-minute buffer, see the arm-time-skid
    rationale below — emitted as a fixed `M H * * *` form), NEVER the
    fragile every-minute `*/1 * * * *`. Rationale: the catastrophic failure
    mode is the dispatcher dropping `recurring: false` (a CronCreate default is
    recurring). With `*/1 * * * *` that drop produces an every-MINUTE storm
    (back-to-back ticks, concurrent-tick state corruption); with a pinned
    `M H * * *` the same drop fires at most ONCE PER DAY at minute M — a benign
    blast radius. The pinned minute also AVOIDS the `:00` and `:30` marks per
    CronCreate guidance (when the buffered minute lands on 0 or 30, nudge to an
    adjacent minute). `schedule-decision.py` computes and emits this pinned
    expression in the `croncreate.cron` field (it MAY use the wall clock — it is
    an ordinary Python script, not a workflow-sandboxed one).

    **Arm-time minute-boundary skid — the 2-minute buffer.** The pinned
    minute carries a `+2` BUFFER rather than `+1` because the dispatcher does
    not arm the one-shot at decision time: it first runs the Inv 47 dedup
    round-trip (`CronList` → `CronDelete` prior refires → `CronCreate`), which
    eats several seconds. A decision landing in the final seconds of a
    wall-clock minute lets that round-trip CROSS the minute boundary, so a `+1`
    pinned minute becomes the CURRENT (already-started) minute; because the
    one-shot is pinned to a specific `M H * * *` minute (not `*/1`), cron's next
    match for that minute is ~24h later — the refire is effectively dropped
    (backstopped by the heartbeat, so a responsiveness, not a liveness, bug). A
    2-minute buffer keeps the pinned minute STRICTLY in the future even after
    the multi-second round-trip while staying "~1 min" responsive, and stays
    minutes-based (cron has no sub-minute granularity).

    **Faithful flag passing + idempotency.** The DISPATCHER MUST
    pass `recurring` and `durable` to `CronCreate` EXACTLY as emitted (both
    `false`) — never rely on tool defaults, never hand-translate-and-drop a
    field (the anti-pattern).

    **At-most-one immediate-refire one-shot — refire dedup with a labelled
    signature.** Nothing originally cancelled a prior pending refire, so
    overlapping/retried ticks PILED UP refires that fired together (an observed
    double-fire at a non-heartbeat minute). The refire-scheduling decision MUST
    enforce AT MOST ONE immediate-refire one-shot at a time: before a new refire
    is created, any prior pending refire is cancelled (a `CronDelete`), then
    EXACTLY ONE new refire is created. The dedup MUST target refire one-shots
    ONLY and MUST NEVER remove the recurring heartbeat (Inv 32/34).

    - **Refires are distinguishable from the heartbeat by a label signature.**
      The refire one-shot's prompt carries a recognizable refire marker
      (`/rabbit-auto-evolve tick #refire`); the recurring heartbeat's prompt is
      the bare `/rabbit-auto-evolve tick` (no marker) and is `recurring`/
      `durable`. `schedule-decision.py` exposes a PURE, unit-testable predicate
      `is_refire_oneshot(entry)` that returns True iff a `CronList` entry's
      prompt carries the refire marker AND the entry is non-recurring and
      non-durable — so the heartbeat (marker-absent, recurring, durable) is
      NEVER selected for removal.
    - **The decision JSON carries the explicit dispatcher instruction set.** The
      actual `CronList`/`CronDelete`/`CronCreate` calls are DISPATCHER (Claude)
      actions — a script cannot call them. So on the `immediate-refire` decision
      `schedule-decision.py` emits a `dispatcher_actions` block naming, from the
      injected `CronList` snapshot (env `RABBIT_AUTO_EVOLVE_CRON_LIST`, a JSON
      array; absent → treated as empty): the prior refire one-shots to
      `CronDelete` (`delete_refire_ids`), the heartbeat id(s) to PRESERVE
      (`preserve_heartbeat_ids`, never deleted), and the single refire to
      `CronCreate` (`create_refire`, prompt carrying the marker, `recurring` and
      `durable` both `false`, cron the pinned `M H * * *` form above). The
      dispatcher deletes every id in `delete_refire_ids`, leaves
      `preserve_heartbeat_ids` untouched, then creates the one `create_refire`.

    Enforced by `test/test-spec-cron-invariant.py` and
    `test/test-spec-refire-dedup-invariant.py` (spec text) and
    `test/test-schedule-decision.py` (e2e: a pipe whose `selection_order` is
    non-empty yields `immediate-refire` while an all-blocked/all-gated backlog
    whose `selection_order` is EMPTY — even with a non-empty raw open queue —
    yields `idle` (#1004); and a `fetch-queue.py` shim that
    emits a non-empty array yields `immediate-refire` with `croncreate.recurring ==
    false`, `croncreate.durable == false`, and a `croncreate.cron` that is a
    pinned `M H * * *` expression — NOT `*/1 * * * *` — whose minute field is
    neither `0` nor `30`; an empty array yields `idle`; a `CronList` snapshot
    holding a prior refire + the heartbeat → the prior refire id is in
    `delete_refire_ids`, the heartbeat id is in `preserve_heartbeat_ids` and NOT
    in `delete_refire_ids`, exactly one `create_refire` is emitted whose prompt
    carries the refire marker) plus unit tests over `is_refire_oneshot` (marker +
    non-recurring → True; the heartbeat → False).

34. **Scheduler detection: crontab where available, CronCreate where blocked
    (D2).** `scripts/detect-scheduler.py` probes whether the
    system `crontab` binary is usable by running `crontab -l` via the
    `RABBIT_CRONTAB_CMD` env override (so tests can inject a shim, the same
    pattern as `install-cron.py`). It distinguishes USABLE (the probe
    succeeds, OR the legitimate "no crontab for user" empty case — a
    non-permission non-zero exit) from RESTRICTED (a permission / "not
    allowed" failure). It emits JSON `{"scheduler":"crontab"|"croncreate",
    "reason":"..."}` on stdout and exits 0. `install-cron.py` and
    `schedule-decision.py` consult it to choose the mechanism: `crontab` →
    the existing system-cron behavior; `croncreate` → the durable
    `CronCreate` fallback (Inv 32 amendment). Enforced by
    `test/test-detect-scheduler.py` (e2e: a usable shim → `crontab`; the
    empty "no crontab" shim → `crontab`; a restricted shim → `croncreate`).

35. **Stale-marker running-guard (D3).** Before a session
    enters a tick (and at every heartbeat), `scripts/running-guard.py` inspects
    `.rabbit-auto-evolve-running` so a CRASHED tick never wedges the loop, while
    a genuinely ACTIVE tick is never cleared out from under itself. ABSENT →
    `{"action":"proceed","running":false}`. PRESENT and STALE → clear the
    marker, log `stale marker cleared` via `tick-log.py`, return
    `{"action":"proceed","running":true,"stale_cleared":true}`. PRESENT and
    FRESH (active) → `{"action":"skip","reason":"tick-running"}`.

    **Staleness MUST track the LIVE tick, not the marker's creation moment
   .** The v0.24.0-and-earlier rule — "stale when marker mtime >
    MAX_TICK_DURATION OR the recorded PID is dead" — was UNSOUND on two counts,
    both observed live: (1) `start-loop.py` stamped `os.getpid()`, the
    short-lived helper subprocess's PID, which dies seconds after the marker is
    written, so the "PID dead → stale" arm flagged EVERY tick stale almost
    immediately; and (2) the marker's mtime is frozen at creation, so a
    long-but-active tick (legitimately running > MAX_TICK_DURATION while
    dispatching subagents and updating `state.json`) tripped the age window and
    was falsely judged stale. A false-stale verdict clears an active tick's
    marker and lets a CONCURRENT tick start on top of it — corrupting the shared
    `state.json` / branches / PRs the guard exists to protect.

    The corrected staleness rule keys on ACTUAL activity and a DURABLE owner,
    and combines them CONSERVATIVELY:

    - **Activity signal (PRIMARY).** The tick is ACTIVE when
      `.rabbit/auto-evolve-state.json`'s mtime advanced within an IDLE_WINDOW
      (default 600 s / 10 min; overridable via
      `RABBIT_AUTO_EVOLVE_IDLE_SECS`). `state.json` mtime advances as the tick
      works (every `update-state.py` write), so it tracks liveness even for a
      multi-hour active tick. Total elapsed time since marker creation is NO
      LONGER a staleness signal on its own.
    - **Durable owner liveness (SECONDARY).** The marker records a DURABLE
      owner identifier — the long-lived session / tick-owner PID, sourced from
      the Claude session environment (e.g. `CLAUDE_SESSION_PID` / `PPID` chain)
      when available — in its content (built by `start-loop.py`'s
      `_marker_content`, imported by the shared phase-walk that writes the
      marker per Inv 42), NOT the writer's transient `os.getpid()`. When a
      durable owner PID is recorded AND that process is
      alive, the tick is ACTIVE regardless of the activity window. When no
      durable owner can be determined, the marker omits the PID and the guard
      relies on the activity signal alone (it MUST still function PID-free).
    - **Conservative AND-combine.** A marker is STALE only when BOTH hold: no
      live owner process (PID absent or dead) AND `state.json` is idle (mtime
      older than IDLE_WINDOW, or `state.json` absent). If EITHER the owner is
      alive OR activity is recent, the marker is FRESH and preserved. The guard
      prefers a false-NEGATIVE (wait one more heartbeat for a possibly-crashed
      tick) over a false-POSITIVE (clear an active tick → concurrent run).

    Existence-based readers (`status-report.py`, `end-tick.py`) are unaffected —
    they key on the filename, which is unchanged. The heartbeat path (the
    headless tick / scheduled refire's "is a tick running?" check) MUST invoke
    this staleness-aware guard, NOT a bare marker-presence test — otherwise a
    truly-crashed tick wedges the loop forever (the opposite failure). This
    realizes Inv 32's preserved observability goal: a wedged loop is cleared and
    logged, an active loop is never disrupted.

    **Guard BEFORE the marker write; the marker write is owned by ONE place for
    both paths.** The `.rabbit-auto-evolve-running` marker write lives in the
    shared scripted phase-walk (`run-tick-phases.py pre-dispatch`), AFTER its own
    running-guard returns `proceed` — never before the guard, and never written
    by the caller. Sequencing the guard BEFORE the marker write, in ONE place for
    BOTH the in-session and headless paths, is what prevents a path from
    false-skipping on a marker it itself wrote. The ordering is strict:

    1. **One guard, then mark.** `run-tick-phases.py pre-dispatch` runs the
       running-guard FIRST. ABSENT marker (or a stale one the guard cleared) →
       `proceed`; a FRESH marker from a DIFFERENT live tick that already exists
       BEFORE the walk starts → `skip` (concurrency protection preserved). ONLY
       after `proceed` does the walk write the `.rabbit-auto-evolve-running`
       marker (the durable owner-PID + ISO-8601 timestamp content for this
       guard). Because the marker is written AFTER the guard, the guard within
       the same call never trips on it.
    2. **`start-loop.py` does NOT write the running marker.** The explicit user
       `start` entry (`start-loop.py`, Inv 19) runs ONLY its cancel-stop +
       bootstrap self-heal and then the dispatcher invokes the shared walk; the
       walk owns the guard→mark sequence (not `start-loop.py`).
    3. **Start-vs-tick authority is preserved (Inv 41 / Inv 19).** The
       cancel-stop and state-bootstrap self-heal stay tied to the EXPLICIT USER
       `start` ONLY: the explicit `start` runs `start-loop.py` (cancel-stop +
       bootstrap) BEFORE invoking the walk; a MACHINE-fired `tick` invokes the
       walk DIRECTLY with NO cancel-stop. The shared walk writes ONLY the running
       marker (after the guard), never the stop-cancel — so a MACHINE `tick` can
       never inherit `start`'s stop-cancel and resurrect a halted loop.
    4. **`end-tick.py` still removes the running marker** on every exit path
       (Inv 20), the unchanged mirror of the walk's write.

    The marker CONTENT shape (durable owner PID + ISO-8601 timestamp) is defined
    in ONE place (`start-loop.py`'s `_marker_content`) and imported by the
    phase-walk, so both the content shape and the write live in single owners.
    Because the loop's scripts re-read from disk each tick, this is a
    re-read-from-disk self-modifying migration (Inv 39): no coexistence window,
    no restart marker — it takes effect on the next tick after merge + sync.

    Enforced by `test/test-running-guard.py` (e2e):
    - absent marker → proceed, `running:false`.
    - active tick — owner PID alive (a live sentinel process), any marker age →
      skip (NOT stale), marker preserved.
    - active tick — `state.json` mtime within IDLE_WINDOW, no live PID, marker
      age > MAX_TICK_DURATION → NOT stale (the long-active false-positive),
      marker preserved.
    - crashed tick — owner PID dead AND `state.json` idle beyond IDLE_WINDOW (or
      absent) → stale, marker cleared, `stale marker cleared` logged.
    - PID-free marker with idle `state.json` → stale and cleared (guard
      functions without a PID).
    - helper-PID regression — the PID recorded in the marker the shared
      phase-walk writes is the durable owner, NOT the transient subprocess PID
      (assert the recorded PID is not the walk's own short-lived PID). The
      marker-content shape lives in `start-loop.py`'s `_marker_content`, imported
      by the phase-walk.

    And by `test/test-guard-before-marker.py` (e2e: clean state → the walk runs
    the guard, writes the marker, returns `proceed` and is NOT a self-skip; the
    walk does NOT false-skip on the marker it itself wrote within the same call; a
    pre-existing FRESH marker from a different live tick still makes pre-dispatch
    skip; `start-loop.py` cancels a pending stop and bootstraps the state file but
    does NOT write the running marker) and `test/test-spec-guard-before-marker-invariant.py`
    (this ordering text is present in the spec and the SKILL.md documents the
    corrected ordering).

36. **Every heartbeat/guard/schedule decision is logged (D4).**
    `scripts/tick-log.py` is an append-only, structured (JSON-per-line)
    logger to `.rabbit/tick.log` (state dir resolved via
    `RABBIT_AUTO_EVOLVE_STATE_DIR` when set, else `<cwd>/.rabbit`, matching
    `update-state.py`). It exposes one append entry point that writes
    `{ts, decision, detail}`; it is used by `running-guard.py` (D3) and the
    heartbeat/schedule flow (`schedule-decision.py`, D1). The heartbeat/guard
    decisions that MUST be logged are: `entering` (a tick is entered),
    `skipped: tick already running`, `idle: no work`, and `stale marker
    cleared`. This is the MINIMAL logger — full configurable on/off +
    verbosity is the scope of Inv 37 and is NOT implemented here.
    Enforced by `test/test-tick-log.py` (e2e: an append writes one JSON line
    carrying `ts`, `decision`, and `detail` to `.rabbit/tick.log` under the
    state-dir override).

37. **`log-tick.py` full per-tick observability log.** A
    persistent, append-only, machine-readable (JSON-lines) per-tick log
    written by every auto-evolve tick, for two consumers: (1) the user, to
    debug what the loop did / when it last ran / why it stalled; and (2)
    other Claude sessions, which can `tail`/grep the file to answer "is the
    loop alive?" / "what phase did it last reach?" without round-tripping to
    the running session.

    **Relationship to Inv 36.** This is DISTINCT from the minimal Inv 36
    `tick-log.py`, which logs heartbeat/guard/schedule DECISIONS (`entering`,
    `skipped`, `idle`, `stale marker cleared`) to `.rabbit/tick.log`. Inv 37's
    `log-tick.py` is the broader per-tick EXECUTION trace at
    `.rabbit/auto-evolve.log`. The two logs COEXIST (different files, different
    purposes); Inv 37 does NOT modify `tick-log.py` or Inv 36. (The two
    script names — `tick-log.py` vs `log-tick.py` — are deliberately distinct;
    an implementer who judges the proximity error-prone MAY rename Inv 37's
    script under the "or equivalent" latitude, provided every SKILL.md / test
    reference is updated in lockstep.)

    **(a) Writer + record shape.** The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/log-tick.py` owns ALL
    writes to `<state_dir>/auto-evolve.log` (state dir resolved via
    `RABBIT_AUTO_EVOLVE_STATE_DIR` when set, else `<cwd>/.rabbit`, matching
    `update-state.py` / `tick-log.py`). It takes structured kwargs and emits
    EXACTLY ONE JSON line per call. The per-tick record carries at minimum the
    keys: `ts` (ISO 8601 UTC), `tick` (int), `session_id` (short Claude
    session id or pid), `phase_reached`, `phase_result`, `in_flight` (array),
    `queue_head` (array), `queue_len` (int), `merged_this_tick` (array),
    `blockers` (array), `next_action`. Each line is capped at 2 KB hard — the
    writer summarizes/truncates to stay under the cap rather than emit an
    oversized line. `tick` and `session_id` MUST carry real attribution, never
    stub `0` / `''` — their derivation is governed by Inv 50.

    **(b) Verbosity (three strictly-additive levels).** `quiet` = tick
    start/end only (one line per tick); `normal` (DEFAULT) = tick boundaries +
    phase results + blockers; `debug` = every phase transition with timestamps
    plus payload sizes/counts. Each level includes everything the lighter level
    emits. A record below the active level is DROPPED (no file growth).

    **(c) Enable flag + config storage.** An on/off enable flag (DEFAULT on)
    and the verbosity level are stored in rabbit-auto-evolve's OWN config —
    NOT in rabbit-cage's `configuration` array. When the enable flag is off,
    `log-tick.py` writes nothing (zero file growth) — a hard requirement.

    **(d) Rotation.** Rotation runs at TICK START (phase 0), not on every
    write, to keep the hot path cheap. When `auto-evolve.log` exceeds 5 MB,
    rotate `.log` → `.log.1` → `.log.2` → `.log.3`, dropping the oldest; AT
    MOST 3 rotated files are kept (≤ 4 files total).

    **(e) `log-path.py`.** The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/log-path.py` prints
    the absolute log-file path on stdout, so a daemon session can
    `tail -f $(python3 …/log-path.py)`.

    **(f) CLI surface.** A new `log` subcommand group on the
    `/rabbit-auto-evolve` SKILL: `log on` / `log off` (toggle the enable
    flag), `log level <quiet|normal|debug>` (set verbosity), `log path` (print
    path via `log-path.py`), `log tail [N]` (print the last N lines, default
    20), `log clear` (truncate, with confirmation). These mirror the existing
    `on`/`off`/`status`/`start`/`stop` subcommand conventions and are owned
    entirely WITHIN rabbit-auto-evolve.

    **(g) Tick-driver integration.** The SKILL.md tick pipeline calls
    `log-tick.py` at tick start, at tick end, and at every phase boundary as
    the active verbosity level dictates. It MUST NOT pass stub `--tick 0` /
    `--session-id ''`; omitting the flags (the documented default) yields the
    derived attribution below.

    **(h) Attribution — `tick` and `session_id` carry real, deterministic
    values, never the stub `0` / `''`** (the cross-session attribution depends
    on it). Both derive from DETERMINISTIC, testable sources:

    - **Single source of truth — the running marker**
      (`<repo_root>/.rabbit-auto-evolve-running`, content `pid=<n> ts=<iso>
      session` built by `start-loop.py._marker_content`), a stable per-session
      anchor. Path via `RABBIT_AUTO_EVOLVE_RUNNING_MARKER`, else
      `<repo_root>/.rabbit-auto-evolve-running` (`<repo_root>` via
      `RABBIT_AUTO_EVOLVE_REPO_ROOT`, else cwd) — injectable for tests.
    - **`session_id`** (when `--session-id` omitted): `pid<n>-<ts>` when a
      `pid=<n>` is recorded, else `ts-<ts>` (PID-free markers valid), stable
      across the session; absent marker → `pid<getpid>`, never the empty stub.
    - **`tick`** (when `--tick` omitted): a monotonic per-session counter in
      `<state_dir>/auto-evolve-log-tick.json` (`{"session_id":…, "tick":…}`). A
      `tick-start` INCREMENTS (resetting to 1 on a new session_id) and persists;
      other record-kinds REUSE the current value (default 1). A pure function of
      on-disk state, deterministic under test.
    - **Explicit override.** A passed `--tick` / `--session-id` is honored
      verbatim (derivation fills the gap only when the flag is omitted).

    Enforced by `test/test-log-tick.py`:
    - Writes 100 ticks at each verbosity (`quiet`/`normal`/`debug`) and
      asserts the per-level line counts match expectations.
    - Writes past the 5 MB cap and asserts rotation fires and the file count
      stays ≤ 4.
    - `log off` (enable flag false): no file growth across repeated calls.
    - Each emitted line is < 2 KB.
    - `log-path.py` prints the resolved `.rabbit/auto-evolve.log` path.
    - `--help` smoke for both scripts: exit 0 with recognizable usage text.
    - Attribution (h): scenario H — with NO `--session-id`/`--tick` and an
      injected marker, a tick's records carry a non-empty stable `session_id`
      and a non-zero `tick`, and a second tick advances the monotonic counter
      while the `session_id` stays stable; scenario I — explicit
      `--tick`/`--session-id` override the derived values.

    And by `test/test-spec-tick-log-invariant.py` (e2e): asserts this
    invariant text is present in the spec AND that both the source and deployed
    `SKILL.md` document the `log on|off|level|path|tail|clear` subcommands, and
    that the spec documents the attribution derivation from the running marker,
    the injectable `RABBIT_AUTO_EVOLVE_RUNNING_MARKER` source, and the no-stub
    guarantee.

38. **Tick-start working-tree self-sync via `git pull --ff-only`.**
    The loop runs its phase scripts from its LOCAL checkout. After it merges PRs
    to `origin/dev`, local `dev` falls behind and subsequent ticks run STALE
    script versions until a human fast-forwards — undercutting autonomy. The
    loop MUST self-sync at tick start.

    **Mechanism (`scripts/sync-tree.py`).**
    `python3 .claude/features/rabbit-auto-evolve/scripts/sync-tree.py` performs
    the deterministic sync:

    1. Verify the working tree is clean of uncommitted TRACKED changes (the
       same condition as `safety-check.py` Invariant 5 — `git diff --quiet`
       AND `git diff --cached --quiet`; untracked files are ignored). A dirty
       tree → exit non-zero, fail loudly (do NOT sync over local edits).
    2. Run `git pull --ff-only origin dev`. On a non-fast-forwardable
       divergence `--ff-only` fails loudly (exit non-zero); the loop surfaces
       it and does NOT fall back to a non-ff merge.
    3. On success, emit a result line and log the sync outcome via
       `tick-log.py`.

    **`git pull`, never `git merge` (the binding constraint).** `settings.json`
    declares `deny: ["Bash(git merge *)"]` — a permissions `deny` (NOT
    scope-guard), and `deny` is absolute: it beats any `allow` and even
    `permissions.defaultMode: bypassPermissions`. So `git merge --ff-only
    origin/dev` is permission-denied and an `allow` in `settings.local.json`
    cannot override it. `git pull` is NOT in the deny list and runs cleanly
    (verified: `git pull --ff-only origin dev` fetches + fast-forwards and
    updates `.claude/` files without scope-guard intervention). `sync-tree.py`
    therefore uses `git pull --ff-only origin dev` exclusively. The `git merge`
    deny is an intentional guardrail (the loop merges via `gh pr merge`, never
    a local merge) and MUST NOT be narrowed/removed in `settings.json`.

    **When it runs.** Sync happens at TICK START (before any phase script runs
    this tick) so the whole tick executes one consistent script version,
    avoiding mid-tick self-modification (the concern). Both the in-session
    tick (SKILL.md phase 0 / tick-start) and the headless tick
    (`tick-headless.py`) run `sync-tree.py` before walking the deterministic
    phases. A sync failure (dirty/divergent tree) is surfaced and logged, never
    silently skipped or force-merged.


    Enforced by `test/test-sync-tree.py` (e2e, against a tmpdir git fixture
    with a local `origin` remote): a clean tree behind origin fast-forwards via
    `git pull --ff-only origin dev` and exits 0; a dirty tracked-file tree
    exits non-zero WITHOUT pulling; a divergent (non-ff) local history exits
    non-zero loudly; the script NEVER invokes `git merge` (assert via a `git`
    shim call-log). And by `test/test-spec-worktree-sync-invariant.py`:
    asserts this invariant text is present in the spec AND that both the source
    and deployed `SKILL.md` document the tick-start `sync-tree.py` step using
    `git pull --ff-only` (and contain no `git merge` sync instruction).

39. **Self-modifying migrations execute via three safe-execution patterns;
    restart-required is signaled via the restart-needed marker, never a human
    stop.** A *self-modifying migration* is a work item that changes something
    the loop itself depends on at runtime: a marker the tick driver reads, an
    agent type the loop dispatches, a path its scripts resolve, or a schema /
    config key it loads. The loop NEVER stops to ask a human (no a/b/c
    question) for a self-modifying migration; it executes one of three
    deterministic safe-execution patterns chosen by the **consumption-based
    decision rule** — HOW the loop consumes the migrated state:

    | Consumption | Pattern | Restart? |
    |---|---|---|
    | re-read from disk each tick | coexistence-window (additive-then-remove; honor BOTH old and new during the transition, then drop old) | No |
    | self-contained (risk is later steps in the same tick tripping on half-migrated state) | last-tick-action (do all other work first; migrate as the final action; the tick boundary is the firewall) | No |
    | held in session memory (loaded at session start) | restart-safe (land the change to take effect NEXT session; set `.rabbit-auto-evolve-restart-needed`; end the tick cleanly) | Yes |

    The consumption type of loop-critical runtime state is declared in the
    data-driven registry
    `scripts/schemas/self-modifying-migration-registry.json`, mapping known
    markers, resolved paths, agent types, config keys to a consumption type,
    with the fallback heuristic for unlisted state: marker files & resolved
    paths → disk-each-tick (coexistence-window); agent types & session config →
    memory-at-start (restart-safe). The Stage-2 classifier in `plan-batch.py`
    consumes the registry: per item it detects a self-modifying migration, tags
    the pattern in `self_modifying_migrations` (issue-number-string → pattern),
    and lists restart-safe items under `restart_needed`. `plan-batch.py` writes
    no marker; the tick driver sets `.rabbit-auto-evolve-restart-needed` for
    those items (via `mark-restart-needed.py`, Inv 17) and ends cleanly.

    The one yield point for a restart-required migration is the
    `.rabbit-auto-evolve-restart-needed` marker (consumed by the SessionStart
    banner, Inv 14, and the `classify-merge-restart.py` 3-rung ladder, Inv 8),
    never a free-form human stop.

    Enforced by `test/test-self-modifying-migration.py` (e2e: a disk-read
    marker rename → coexistence-window with no restart; a resolved-path move →
    last-tick-action / coexistence-window with no restart; an in-memory
    agent-type rename → restart-safe with the item listed in `restart_needed`;
    in all cases the planner emits no human a/b/c question and writes no
    marker), by `test/test-self-modifying-migration-registry.py` (the registry
    declares lifecycle metadata, the consumption→pattern mapping, entries
    covering both fallback classes, and the fallback heuristic), and by
    `test/test-spec-self-modifying-migration-invariant.py` (this invariant text
    is present in the spec).

40. **One shared scripted phase-walk; the in-session tick adds only Phase 6.**
    The deterministic tick phases live in ONE shared scripted implementation,
    `python3 .claude/features/rabbit-auto-evolve/scripts/run-tick-phases.py`,
    which BOTH the headless tick (`tick-headless.py`) and the in-session tick
    (SKILL.md `start`/`tick`) invoke. The walk runs in two segments around the
    single Claude-only phase:

    - `run-tick-phases.py pre-dispatch` — tick-start self-sync (Inv 38), phase
      0/1 stop/abort short-circuit, running-guard (Inv 35), phases 3-5
      (`fetch | triage | plan`, Inv 18). Emits `action` = `proceed` (continue to
      dispatch) or `skip` (a clean no-op short-circuit fired).
    - `run-tick-phases.py post-dispatch` — an Inv 55 add-on-entry reconcile at
      the START (before merge drains the live set), phase 7 (merge the
      `merge_ready` PRs), a post-merge re-sync (Inv 45), phases 8-10
      (`run-post-merge.py` drain), phase 11 (persist), an Inv 55 strip-on-exit
      reconcile, then the Inv 56 jitter-artifact refresh.

    The headless tick chains `pre-dispatch -> (skip dispatch) -> post-dispatch`;
    the in-session tick chains `pre-dispatch -> Phase 6 (dispatch) ->
    post-dispatch`. The in-session path differs ONLY by inserting Phase 6, which
    needs Claude. There is exactly ONE deterministic phase-walk; the dispatcher
    only adds dispatch.

    **Phase 11 persist is deterministic and never hand-assembled.** It re-reads
    the on-disk state (mutated on disk by `merge-prs.py` / `run-post-merge.py`),
    drops the transient `merge_ready` key (not in the Inv 9 schema), and pipes
    through `update-state.py`. The dispatcher NEVER reads `update-state.py`
    source or the schema to hand-assemble new-state JSON; every in-session
    handoff is script-to-script (pipes or on-disk state mutation), exactly as
    the headless tick chains them.

    Because the phase scripts re-read state from disk each tick, this is a
    re-read-from-disk self-modifying migration (Inv 39): no coexistence window,
    no restart; takes effect next tick after merge + sync.

    Enforced by `test/test-run-tick-phases.py` (e2e: each segment walks exactly
    its phases against stub phase scripts; `pre-dispatch` short-circuits on the
    stop marker and the running-guard skip verdict; `post-dispatch` merges
    ready PRs, drains post-merge, and persists through the REAL update-state.py
    dropping `merge_ready`; dispatch NEVER runs inside the walk), by
    `test/test-tick-persist-convergence.py` (the in-session path —
    `pre-dispatch` then `post-dispatch` with a no-state-mutation Phase 6 between
    — persists BYTE-IDENTICAL state to the headless tick for the same on-disk
    phase-script mutations), by `test/test-tick-headless.py` (the headless tick
    delegates to the shared walk), and by
    `test/test-spec-scripted-phase-walk-invariant.py` (this invariant text is
    present in the spec and the SKILL.md describes the in-session tick via the
    shared walk).

41. **A user stop HOLDS across heartbeats; only an explicit user `start`
    clears it.** A `stop` halts the loop and keeps it halted across every
    subsequent MACHINE wake-up until the user EXPLICITLY resumes. The separation
    of authority is strict:

    - **`stop`** writes `.rabbit-auto-evolve-stop-requested`; the next tick's
      phase 0 (`stop-check`) READS the marker, halts cleanly, and does NOT
      delete it.
    - **explicit user `start`** (`start-loop.py`, Inv 19) is the SOLE path that
      clears the stop marker and resumes the loop.
    - **`off`** performs the full teardown (cron removed) per Inv 1.

    **Every MACHINE wake-up fires the INTERNAL `tick`, NEVER the USER-intent
    `start`.** The recurring heartbeat (the crontab `tick-headless.py` entry, or
    the durable `CronCreate` heartbeat on restricted hosts) AND the
    immediate-refire one-shot (Inv 33) both fire `/rabbit-auto-evolve tick`.
    `tick` is the scripted phase-walk (`run-tick-phases.py`, Inv 40):
    pre-dispatch → dispatch → post-dispatch. Its phase-0 stop-check RESPECTS the
    stop marker and NEVER runs `start-loop.py`'s stop-cancel. A cron-fired
    wake-up therefore can NEVER cancel a human's explicit stop.

    The control-safety defect this closes: when a MACHINE (cron / heartbeat /
    immediate-refire) wake-up fired the USER-intent `start`, it inherited
    `start`'s Inv 19 stop-cancel semantics — `start-loop.py`'s first action
    deletes the stop marker and starts a fresh tick — so a user-halted loop
    silently resurrected on the next heartbeat. Routing every machine wake-up
    through `tick` (which respects but never deletes the marker) makes a stop
    hold until the user explicitly resumes.

    - `schedule-decision.py` emits `prompt: "/rabbit-auto-evolve tick"` for the
      immediate-refire decision AND `croncreate.prompt: "/rabbit-auto-evolve
      tick"` for the croncreate one-shot.
    - `install-cron.py`'s crontab entry already fires `tick-headless.py` (the
      headless `tick`); its restricted-host `CronCreate`-fallback signal emits
      `prompt: "/rabbit-auto-evolve tick"`.
    - The phase-0 stop-check (in `run-tick-phases.py` / `tick-headless.py`) only
      READS the stop marker and halts; it never deletes it.

    Enforced by `test/test-stop-holds.py` (e2e: a stop marker present + a
    cron-fired headless tick halts at phase 0 with the marker NOT deleted and no
    phase work done; an explicit user `start` clears the marker and resumes;
    across N simulated heartbeats with a pending stop, zero ticks perform work
    and the marker persists; `schedule-decision.py` and `install-cron.py` emit
    `/rabbit-auto-evolve tick`), and by `test/test-schedule-decision.py` and
    `test/test-cron-trigger.py` (the emitted refire / heartbeat prompts are
    `/rabbit-auto-evolve tick`).

42. **Deterministic pre-merge cleanup of known worktree-dispatch leaks; never
    discard unexpected dirt or un-pushed work.** Worktree-isolated Phase 6
    dispatches sometimes leave noise in the dispatcher's MAIN tree because a
    subagent's process cwd is occasionally the main/shared checkout (not its
    worktree) when it runs its LOCK / tdd-step bookkeeping or a `git checkout -B
    <branch> origin/dev` (a harness limitation the cwd-based `_repo_root` fix
    reduced but did not eliminate). There are THREE known leak classes:

    - a **leaked main-HEAD branch switch** — the subagent's `git checkout -B`
      ran in the MAIN checkout and switched the dispatcher's MAIN HEAD onto a
      feature branch, so safety-check Inv 1 ("branch is dev") fails and
      `merge-prs.py` SKIPS every PR with `safety-check-failed` (the tree is
      CLEAN, so it is NOT the file-leak path);
    - an untracked stray `.rabbit-scope-active-<feature>` marker at the repo
      root;
    - a TRACKED `<feature>/feature.json` whose diff vs HEAD touches ONLY
      loop-bookkeeping keys.

    The last two trip safety-check Inv 5 ("no uncommitted tracked-file
    modifications"), which likewise makes `merge-prs.py` skip every PR in the
    batch.

    `scripts/clean-dispatch-leaks.py` performs a deterministic, defense-in-depth
    cleanup of ONLY these known leak classes, and `run-tick-phases.py
    run_post_dispatch` invokes it as the FIRST action of Phase 7, BEFORE
    `merge-prs.py`. The cleanup operates on the repo's main working tree, in this
    order (branch restore FIRST so the file cleanup and the merge see the right
    branch):

    1. **Restore a leaked branch switch FIRST.** Read the main repo's HEAD
       branch. When it is NOT `dev`, the branch was leaked. Restore with
       `git checkout dev` ONLY when HEAD != `dev` AND the working tree is CLEAN
       (no uncommitted tracked changes) AND the branch has NO un-pushed unique
       commits (every local commit is present on its `origin/<branch>` remote) —
       safe because the feature work lives on its own pushed branch; the restore
       is logged via `tick-log.py` (Inv 36). If HEAD != `dev` AND the tree is
       DIRTY OR the branch has un-pushed unique commits (or a branch with no
       remote counterpart, treated conservatively as un-pushed), the cleanup
       exits non-zero and does NOT switch or discard anything, so the tick aborts
       (Inv 20) — never destroy un-pushed work. With HEAD already on `dev`, this
       step is a no-op.
    2. **Remove untracked stray markers.** Deletes any untracked
       `.rabbit-scope-active-*` file at the repo root.
    3. **Restore only bookkeeping-only `feature.json` leaks.** For a TRACKED
       modification, restores the file to HEAD ONLY when it is a
       `<feature>/feature.json` whose diff vs HEAD touches ONLY the
       loop-bookkeeping keys (`tdd_last_cycle_impl_commit`, `tdd_state`,
       `updated`, `spec_no_change_reason`, `_pre_touch_state`). A
       doc/spec/contract/CHANGELOG file is never in scope.
    4. **Fail loudly on unexpected dirt.** ANY tracked modification that does
       NOT match the known-leak signature is NEVER silently discarded: the
       cleanup reports it on stderr and exits non-zero, so the tick aborts
       (Inv 20) and a genuine uncommitted change is never destroyed. This is
       the critical safety property — clean ONLY known leak-class noise, never
       arbitrary changes.

    The cleanup logs what it removed/restored via `tick-log.py` (Inv 36) so it
    is observable. On a clean tree on `dev` the cleanup is a no-op (exit 0,
    nothing logged as cleaned).

    Enforced by `test/test-clean-dispatch-leaks.py` (e2e in a temp git repo
    wired to a bare origin: a clean, pushed leaked branch is restored to `dev`
    and logged; a dirty or un-pushed leaked branch makes the cleanup refuse
    non-zero without switching or discarding; HEAD already on `dev` is a no-op; a
    bookkeeping-only `feature.json` leak + a stray marker are cleaned to a clean
    tree; a leaked branch + a stray marker restores the branch then removes the
    marker; an unexpected `spec.md` edit makes the cleanup refuse non-zero and
    preserves the edit), by `test/test-run-tick-phases.py` (post-dispatch invokes
    the cleanup before the merge step), and by
    `test/test-spec-branch-switch-guard-invariant.py`.

43. **SKILL.md `description:` trigger enumeration covers common natural
    phrasings, including the unhyphenated "auto evolve" and "enter … mode"
    forms.** The `description:` frontmatter is the sole signal a
    fresh session uses to decide whether to invoke this skill directly versus
    doing the "let me look around" dance. The enumeration MUST therefore
    recognize the natural phrasings a user actually types, not only the
    canonical hyphenated commands. In addition to the existing canonical
    triggers ("start auto-evolve", "stop the loop", "auto-evolve status",
    "let rabbit run", "begin autonomous evolve", or any
    `/rabbit-auto-evolve <subcommand>` form), the `description:` MUST also
    enumerate at least:

    1. "enter auto evolve mode" / "enter auto-evolve mode" — the
       "enter … mode" framing, with the trailing word `mode`.
    2. The unhyphenated "auto evolve" spelling (a user who omits the hyphen
       must still trigger).
    3. An enable/turn-on phrasing for autonomous evolve (e.g. "turn on
       autonomous evolve" / "enable autonomous evolve").
    4. A resume phrasing (e.g. "resume the loop").

    The change is description-coverage ONLY — skill BEHAVIOR is unchanged. The
    `description:` MUST remain a single coherent sentence/paragraph per the
    SKILL.md authoring standard (spec-rules §4); it is not split into a list.

    Enforced by `test/test-skill-description-triggers.py` (asserts the SOURCE
    SKILL.md `description:` line contains the broadened phrasings — matching
    "enter auto", the unhyphenated "auto evolve", an enable/turn-on autonomous
    phrasing, and a resume phrasing — alongside the pre-existing canonical
    triggers).

44. **The loop computes its own priority score; the filer label is one
    input among several.** Stage-1 dispatch ordering is no
    longer keyed on the filer-set `priority:` label alone. `plan-batch.py`
    computes the loop's OWN priority signal — a deterministic, weighted
    blend of OBSERVABLE evidence — and that `computed_score` is the PRIMARY
    `selection_order` / `barrier_first` ordering key. The filer label is
    retained as ONE input among several (weight reduced), so a mislabeled or
    stale-priority issue is ordered sensibly and no filer can single-handedly
    jump an item ahead by labelling it `priority:high`.

    **(a) Observable signals (deterministic subset).** Each is computed in a
    script (script-tier, NEVER LLM inference) from data already flowing
    through the triage objects on `plan-batch.py` stdin — no `gh`, `git`, or
    filesystem reads. The score is a weighted sum normalized to `[0, 1]`:

    | Signal | How computed | Weight |
    |---|---|---|
    | Blocking-fanout | count of OTHER batch items whose `blocked_by` references this issue (saturates at 5) | 0.30 |
    | Filer-set label | the `priority` field: critical=1.0, high=0.75, medium=0.5, low=0.25, none=0.0 | 0.15 |
    | Scope size | `1 / len(features)` — a smaller item is a boost (quick wins compound) | 0.10 |
    | Bug vs. enhancement | `1.0` when `issue_type == "bug"`, else `0.0` | 0.05 |
    | Age | days since `created_at`, saturating at 30 | 0.05 |

    Blocking-fanout is the heaviest weight because it is the HARDEST signal
    for a filer to game (it requires OTHER issues to reference yours).
    Missing inputs contribute zero rather than crashing (an absent
    `created_at` / `issue_type` / `blocked_by` is tolerated). The two
    remaining proposed signals — recurrence-count and
    test-coverage-delta — are NOT deterministically computable in this pure
    JSON processor (they require fuzzy symptom matching and running each
    feature's test suite respectively) and are deferred to a follow-up;
    they are out of scope for this invariant.

    **`issue_type` and `created_at` are wired through triage so the bug and
    age signals are non-zero.** The bug-vs-enhancement and age signals read
    `item.issue_type` / `item.created_at` — fields `triage-issue.py` MUST emit
    on EVERY triage record (work, defer, close-not-planned, research), else
    both signals silently contribute `0.0`. `triage-issue.py` sets
    `issue_type` to `"bug"` when the fetched issue carries a GitHub `bug`
    label, `"enhancement"` for an `enhancement` label, else `null` (`bug` WINS
    when both are present — the higher-urgency signal); the value is read from
    the SAME `labels` array `gh issue view` already returns (no new `gh` call).
    `created_at` echoes the issue's ISO-8601 UTC `createdAt` (trailing-`Z`
    shape), added to the field list of that SAME single `gh issue view` call
    (again no extra `gh` call); a missing/unparseable `createdAt` yields
    `created_at: null`, which `plan-batch.py`'s `_age_days` tolerates as `0.0`
    (no crash). `plan-batch.py`'s bug signal fires `1.0` exactly when
    `issue_type == "bug"`, and the age signal saturates at 30 days.

    **(b) Ordering key.** The prior ordering key made the filer
    `priority:` label the PRIMARY composite-sort key with the contract-touch
    barrier as the SECONDARY tiebreak. This invariant REFINES that: the
    composite key is now `(computed_score desc, contract_touch desc, issue
    asc)`. The computed score is the PRIMARY key; the contract-touch barrier
    is PRESERVED as the SECONDARY tiebreak (it is a barrier/conflict property
    required for Inv 4 / Inv 26 grouping correctness, NOT a priority signal),
    and issue number remains the final stable tiebreak. The filer label is
    folded INTO the score as one weighted input, so it still influences
    ordering but no longer determines it alone. When all observable signals
    are equal the ordering falls back deterministically to the contract
    barrier then issue number (the filer label, being part of the score, has
    already been consulted) — the planner stays fully deterministic. The
    contract-touch barrier semantics of Inv 4 (`barrier_first` is the leading
    run of contract items in the sorted order) are unchanged; only the
    PRIMARY key changes from filer-label-rank to computed_score.

    **(c) Transparency.** `plan-batch.py` emits a `computed_scores` map
    (issue-number string → float in `[0, 1]`) covering every selected item,
    alongside the filer `priority` that triage already passes through, so the
    loop's judgment is OBSERVABLE — the filer label and the loop's computed
    score are visible side-by-side downstream (status surface, tick log).
    Without the emitted score the reordering would look arbitrary.

    **(d) Out of scope.** This invariant does NOT auto-relabel the issue on
    GitHub (the filer's label is the filer's input; the loop's score is its
    own thing), does NOT notify the filer, and does NOT read the issue body
    to subjectively decide importance — it sticks to objective, observable
    signals ("Out-of-scope").

    Enforced by `test/test-plan-batch.py` (two items with identical filer
    labels but different blocking-fanout → the higher-fanout item ranks
    first; a bug at `priority:medium` with high fanout outranks an
    enhancement at `priority:high`; all-signals-equal → deterministic
    fallback to filer label then issue #; `computed_scores` map present and
    normalized; the contract barrier is preserved within an equal score
    tier), `test/test-triage-rules.py` (a bug-labelled issue emits
    `issue_type: "bug"` and a non-null `created_at`; an enhancement-labelled
    issue emits `issue_type: "enhancement"`; a both-labelled issue emits
    `"bug"`; a no-type-label issue emits `issue_type: null`), and
    `test/test-spec-priority-score-invariant.py` (asserts this invariant text
    is present and reconciles with the ordering-key rule, and proves end-to-end
    through plan-batch that the bug + age signals are live, non-zero
    contributions — a `bug` with an old `created_at` scores STRICTLY higher
    than an `enhancement` with no `created_at`).

45. **Post-merge re-sync to origin/dev before the release drain.**
    Phase 7 (`merge-prs.py`) does a REMOTE squash-merge via `gh pr merge`,
    advancing `origin/dev` but NOT the loop's LOCAL `dev`. Phases 8-10
    (`run-post-merge.py` → `release-bump.py`) then run on the STALE local `dev`,
    so `release-bump.py`'s safety-check / next-tag computation SKIPS the release
    on the FIRST attempt; the next-tick retry mitigates the symptom, but the
    root cause is the stale tree.

    `run-tick-phases.py run_post_dispatch` therefore re-syncs the local tree to
    `origin/dev` AFTER the Phase-6 merge reports merged PRs and BEFORE the
    8-10 drain, so the FIRST in-loop release succeeds. It REUSES `sync-tree.py`
    (`git pull --ff-only origin dev` — NEVER `git merge`, permission-denied per
    Inv 38), inheriting Inv 38's dirty-tree and non-ff divergence refusals. The
    ordering is strict:

    1. **Gated on actual merges.** Runs ONLY when the merge step ran with ready
       PRs (`merge_ready` non-empty); zero merges → skipped no-op.
    2. **Ordered between merge and drain.** `sync-tree.py` runs AFTER
       `merge-prs.py` and BEFORE `run-post-merge.py`, so merged commits are
       local before release-bump computes its tag.
    3. **Fails loudly.** A non-ff (dirty/divergent) re-sync aborts
       `run_post_dispatch` non-zero BEFORE the drain — `release-bump.py` never
       runs on a tree that could not be brought current (Inv 5 / Inv 38).

    Enforced by `test/test-run-tick-phases.py` (e2e: merged PRs → re-sync
    between `merge-prs.py` and `run-post-merge.py`; zero merges → no re-sync,
    clean no-op; failing re-sync aborts non-zero before the drain) and by
    `test/test-spec-post-merge-resync-invariant.py` (this text present).

46. **`release-bump.py` reads the closing issue's priority when the PR has
    none.** The dispatch flow opens PRs WITHOUT copying the
    source issue's `priority:<level>` label, so `release-bump.py` (Inv 7)
    saw no priority on the PR and always patch-bumped — minor/major signals
    never reached the version stream. `release-bump.py` therefore resolves
    the priority used by the bump table in strict precedence:

    1. An explicit `priority:<level>` label ON the PR wins (unchanged); the
       closing issue is never consulted in this case.
    2. When the PR carries no priority label, resolve the closing issue from
       the PR body — the first `Fixes|Closes|Resolves #<N>` reference
       (case-insensitive) — and read that issue's `priority:<level>` label
       via `gh issue view <N> --json labels`. The issue's priority drives
       the bump as if it were on the PR.
    3. When neither the PR nor a resolvable closing issue has a priority
       label (no reference, unresolvable / missing issue, or an issue with
       no priority label), keep the existing default → `patch` /
       `priority-low-medium`.

    The lookup is bounded to a single `gh issue view <N> --json labels` and
    is skipped entirely when the PR already carries a priority label or a
    major trigger fires (the major rows are evaluated first and are
    unaffected). Resolution is deterministic (script-tier, no LLM
    inference). Enforced by `test/test-release-bump.py` (PR no-label +
    `Closes #N`(high) → minor; case-insensitive `resolves #N`; PR label
    beats closing issue with no `gh issue view` call; both unlabeled →
    patch; no closing reference → patch).

47. **The merge and release phase scripts persist `last_merged_sha` /
    `last_tagged_version` to on-disk state; phase 11 captures them via the
    re-read.** These two informational state fields
    (surfaced by `status-report.py`, NOT control-critical) lagged
    perpetually because NO phase script ever wrote them: once phase 11
    converged on the deterministic re-read-and-validate persist
    (Inv 40), `merge-prs.py` wrote only `pending_post_merge` and
    `release-bump.py` emitted its result to stdout only. So both fields
    stayed at whatever a long-ago hand-set value left them at even as PRs
    merged and releases cut.

    **The fix writes the fields at the source, never by dispatcher
    hand-set** (the anti-pattern Inv 40 forbids). When
    `merge-prs.py --record-pending` records a successful merge, it writes
    the merge commit SHA (the `mergeCommit.oid` it already fetches per
    Inv 6 close-after-merge) into `last_merged_sha` in the SAME
    read-modify-write of `<state_dir>/auto-evolve-state.json` that updates
    `pending_post_merge` (atomic temp+rename; best-effort — a state write
    error never fails the merge). When `release-bump.py` reaches the
    `released` status, it writes the cut `next_tag` into
    `last_tagged_version` via the identical read-modify-write pattern.
    Phase 11's deterministic re-read (`update-state.py`, Inv 40) then
    captures both off disk with no dispatcher inference.

    **A non-success leaves the field untouched.** A skipped/failed merge
    records no `last_merged_sha`; a `skipped` (safety-check) or `failed`
    (git tag/push/release) release-bump leaves `last_tagged_version` as it
    was — only a real merge / a real cut release advances its field.

    Enforced by `test/test-merge-prs.py` (e2e: after `--record-pending`
    processes a merged PR the state's `last_merged_sha` equals the merge
    commit SHA; a base-not-dev skip leaves a prior value intact) and
    `test/test-release-bump.py` (e2e: a `released` run sets
    `last_tagged_version` to `next_tag`; a safety-check skip and a git-tag
    failure both leave a prior value intact).

48. **Advisory-restart marker — a structured, persistently-surfaced restart
    signal that NEVER pauses the loop.** Distinct from the hard
    `.rabbit-auto-evolve-restart-needed` marker (Inv 8 / Inv 31), which the
    catch-up ladder writes when a merged change cannot take effect until the
    session is restarted and which gates auto-resume. This invariant adds a
    SEPARATE, ADVISORY signal: `.rabbit-auto-evolve-restart-advised`. It
    records that a restart WOULD unlock a capability (e.g. "activates
    skill-creator + code-review; enables worktree.baseRef for parallel
    dispatch"), but it does not block, pause, hold, or auto-resume the loop —
    the tick proceeds unchanged whether or not the marker is present.

    **(a) Writer — `scripts/advise-restart.py write "<reason>"`.** Writes
    `.rabbit-auto-evolve-restart-advised` at the repo root with the structured
    reason string as its content. Overwrites if present (latest reason wins),
    mirroring the established `mark-restart-needed.py` / `mark-aborted.py`
    writer pattern (Inv 17 — all runtime-marker writes go through scripts so
    scope-guard does not see a literal marker path in a Bash command string).
    A missing reason argument is an error (non-zero exit).

    **(b) Read/status surface — `scripts/advise-restart.py status`.** Emits a
    JSON object on stdout describing the marker's presence and reason, always
    exit 0 (the verdict is carried in the payload, never the exit code),
    exactly like `check-auto-resume.py` (Inv 31). When the marker is present:
    `{"advised": true, "reason": "<content>"}`. When absent (graceful):
    `{"advised": false}`. This is the CONTRACT INVOKE surface rabbit-cage's
    Stop/SessionStart dispatcher calls to surface the advisory line; the
    cross-feature use is declared in this feature's `contract.md` `provides`.

    **(c) Clear surface — `scripts/advise-restart.py clear`.** Removes the
    marker. Idempotent: a missing marker is a clean no-op (exit 0). This is
    the CONTRACT INVOKE surface rabbit-cage's SessionStart calls to clear the
    advisory after the advised restart has occurred.

    **(d) Strict separation from the hard marker.** The advisory path NEVER
    writes, reads, deletes, or otherwise affects
    `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`, or
    `.rabbit-auto-evolve-running`, and writing/clearing the advisory marker
    never pauses or short-circuits the tick. The two markers are independent:
    a repo may carry one, both, or neither.

    `<repo_root>` defaults to `os.getcwd()`; overridable via the
    `RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests. Enforced by
    `test/test-advise-restart.py` (write creates the marker with the reason;
    status reports `advised: true` + reason when present and `advised: false`
    when absent; clear removes it and is idempotent; the advisory path leaves
    `.rabbit-auto-evolve-restart-needed` untouched) and
    `test/test-spec-advise-restart-invariant.py` (the spec documents the
    advisory marker, its three subcommands, the JSON status shape, and the
    never-pauses / distinct-from-hard-marker contract).

49. **Tick-start orphan sweep (Inv 49) — leftover TDD dispatch worktrees and
    the prompt dir are bounded at tick start, before Phase 6 dispatch.**
    Parallel TDD dispatch (worktree isolation, Inv 28) creates one git
    worktree per subagent under `.claude/worktrees/agent-*`. The Agent tool
    auto-removes a dispatch worktree ONLY when it is unchanged on exit; a TDD
    worktree is always changed, so it is NEVER auto-removed and the `agent-*`
    worktrees accumulate (~9–14 MB each — 61 leftover / 577 MB observed). The
    `.rabbit/prompts/` dir likewise accumulated unbounded (264 files / 23 MB
    observed) because the prompt-cleanup API was never invoked on the tick
    path. This invariant bounds BOTH at tick start.

    **(a) Worktree sweep — `scripts/prune-worktrees.py`.** A deterministic
    sweep that, for every path `git worktree list --porcelain` reports whose
    basename matches `agent-*` AND that lies under
    `<repo_root>/.claude/worktrees/`, runs `git worktree remove --force
    <path>` then a single `git worktree prune`. It NEVER removes the main
    checkout, NEVER removes a non-`agent-*` path, and NEVER removes a path
    outside `.claude/worktrees/`. Emits a JSON summary on stdout
    (`{"removed": [...], "kept": [...], "status": "ok"}`); a failed `git
    worktree remove` on one path does not abort the sweep (it is recorded and
    the sweep continues), so a single stuck worktree never blocks the tick.
    `<repo_root>` defaults to `os.getcwd()`, overridable via
    `RABBIT_AUTO_EVOLVE_REPO_ROOT` for tests.

    **(b) Safety by sequencing — the sweep runs at TICK START, pre-dispatch.**
    The sweep is wired into `run-tick-phases.py`'s pre-dispatch segment,
    BEFORE Phase 6 dispatch begins. At tick start no dispatch is live, so
    every existing `agent-*` worktree is an orphan from a prior or interrupted
    tick and is safe to force-remove. The sweep is a clean no-op when there
    are no orphans, and never short-circuits or fails the tick on a sweep
    error (it logs and proceeds — disk hygiene must never block evolution).

    **(c) Prompt-dir bounding — invoke the contract cleanup API.** The same
    pre-dispatch path bounds `.rabbit/prompts/` by INVOKING the
    contract-owned `contract.lib.runtime.cleanup_old_prompts(max_age_days, *,
    repo_root)` API (a cross-scope INVOKE declared in this feature's
    `contract.md` `invokes.modules`; rabbit-auto-evolve does NOT edit the
    contract feature). The effective threshold is `max_age_days=7` so the
    prompt dir stays bounded across ticks. `prune-worktrees.py` owns the
    invocation so the bounding logic stays script-tier (Tool-Choice Tier).

    Enforced by `test/test-prune-worktrees.py` (a simulated leftover
    `agent-*` worktree in a temp git repo is pruned; the main worktree and a
    non-`agent-*` worktree are NEVER removed; the sweep is a clean no-op with
    no orphans; the prompt-dir bounding caps `.rabbit/prompts/`) and
    `test/test-spec-prune-worktrees-invariant.py` (the spec documents the
    sweep script, the tick-start pre-dispatch sequencing, the
    `agent-*`-only / under-`.claude/worktrees/`-only safety constraint, and
    the prompt-dir bounding via the contract cleanup invoke).

50. **Deployed-surface republish — after a version-bumping subagent returns,
    the dispatcher republishes the feature's deployed copies BEFORE opening
    the PR.** A version-bumping TDD subagent bumps a feature's SOURCE
    `SKILL.md` (required for four-way version equality across `feature.json`,
    `docs/`, the source skill, and the deployed skill) but CANNOT write the
    deployed `.claude/skills/<feature>/SKILL.md` copy — that path is outside
    the subagent's `.rabbit-scope-active-<feature>` scope, so the scope guard
    denies the write. The result is a RED
    `contract/test/test-deployed-skills-match-source.py` on every
    version-bumping feature touch until the deployed copy is republished from
    source. This invariant makes that republish a deterministic, repeatable
    DISPATCHER step rather than a hand-run manifest walk.

    **(a) Republish script — `scripts/republish-feature.py`.** Given a feature
    name (and optional `--repo-root`, defaulting to `os.getcwd()`), the script
    reads that feature's `feature.json` `manifest` and runs each deploy entry
    by INVOKING `contract.lib.publish.<api>(**args, feature_dir=...,
    repo_root=...)` for every `publish_skill` / `publish_hook` /
    `publish_file` / `publish_command` / `publish_*` entry — exactly what the
    dispatcher otherwise does by hand. It resolves `contract.lib.publish` by
    inserting the sibling `contract` feature dir onto `sys.path` and importing
    `from lib import publish` (the established cross-scope import pattern used
    by `prune-worktrees.py`). This is a cross-scope INVOKE of the
    contract-owned publish API declared in this feature's `contract.md`
    `invokes.modules`; rabbit-auto-evolve does NOT edit the contract feature.

    **(b) Idempotent, JSON-summarized, clean no-op on no manifest.** The
    contract publish APIs are idempotent (a deployed copy that already matches
    source by SHA-256 is a no-op), so re-running the script is safe. The script
    emits a single JSON object on stdout summarizing what was (re)published:
    `{"feature": <name>, "published": [{"api": ..., "message": ...,
    "changed": bool}], "status": "ok"}`. A feature with no `manifest` key, or a
    `manifest` with no publish entries, is a clean no-op (empty `published`
    list, `status: "ok"`). A missing/unparseable `feature.json` or a publish
    call that returns `passed=False` is reported with `status: "error"` and a
    non-zero exit so the dispatcher does not open a PR with a broken deploy.

    **(c) Dispatcher post-handoff sequencing.** After a version-bumping
    subagent returns (or ANY HANDOFF reporting a changed deployed surface —
    `SKILL.md`-changed, a hook/command/file change), the dispatcher runs
    `republish-feature.py <feature>` IN THE WORKTREE, BEFORE opening the PR, so
    the refreshed deployed copy is committed into the PR and
    `contract/test/test-deployed-skills-match-source.py` is green at merge
    time. The step is script-tier: SKILL.md invokes the script, it carries no
    inline python.

    Enforced by `test/test-republish-feature.py` (in a temp fixture repo: a
    feature whose source `SKILL.md` differs from its deployed copy is made to
    match and reported as changed; a feature whose copies already match is a
    no-op with `changed:false`; a feature with no manifest is a clean no-op)
    and `test/test-spec-republish-feature-invariant.py` (the spec carries
    Inv 50, contract.md `invokes.modules` declares the
    `contract.lib.publish` cross-scope invoke, and SKILL.md documents the
    pre-PR republish step invoking the script).

51. **Cross-scope detection routes body-spanning issues away from
    `parallel-per-feature`.** `triage-issue.py` assigns exactly ONE feature to
    each issue from its `feature:` label, and Stage-2 shaping (Inv 26) keys the
    shape off the distinct feature-dir count. But an issue whose BODY touches
    MULTIPLE feature directories (a repo-wide sweep, a cross-feature rename) is
    a cross-scope item: a single bounded per-feature TDD subagent (one
    `.rabbit-scope-active-<feature>`) cannot write outside its feature, so
    dispatching it as ordinary `parallel-per-feature` work aborts at the first
    cross-feature write. The fix is DETECTION + ROUTING; bounded scope itself
    is unchanged (Inv 26(d) — a hard constraint, not waivable).

    **(a) Triage emits a `cross_scope` signal.** `triage-issue.py` sets
    `cross_scope` (bool) on EVERY triage record. It is `true` when the issue
    body implicates more than one feature — either the EDIT-TARGET feature set
    spans 2 or more feature dirs (the label PLUS every distinct body
    `.claude/features/<name>/` PATH reference; bare-name mentions do NOT count,
    see (a.2)), OR the body/title carries an explicit cross-scope phrase
    (case-insensitive: `repo-wide`, `every feature`, `across all features`,
    `across every feature`, `all features`, `rename across`), OR the body/title
    carries an explicit cross-feature scope DECLARATION (case-insensitive:
    `Cross-feature (A + B)`, `Cross-feature: A, B`, `spans <feature> and
    <feature>`) outside any parent-reference line; else `false`.
    The record also carries `cross_scope_features` — the sorted distinct Inv 26
    feature set (same value as `features`) — so the dispatcher sees WHICH
    features the item spans. Both fields appear on every decision; a phrase-only
    signal with a sparse `features` set still yields `cross_scope: true`.

    **(a.1) Parent-reference lines are excluded from the cross-scope phrase
    signal.** A shape-3 DECOMPOSITION sub-issue scoped to ONE feature typically
    QUOTES its parent's framing (e.g. `Sub-issue of parent (retire B/B
    terminology repo-wide)`); that quoted phrase describes the PARENT's scope,
    not the sub-issue's, so it MUST NOT contribute to the sub-issue's
    `cross_scope` signal. A line is a PARENT-REFERENCE line when it matches a
    parent-pointer phrasing (case-insensitive: `sub-issue of`, `subissue of`,
    `part of #<n>`, `parent #<n>`, `parent issue #<n>`, `child of #<n>`,
    `decomposed from #<n>`, `split from #<n>`). The cross-scope PHRASE signal
    is computed over the body with parent-reference lines REMOVED. The
    distinct-feature-set signal is unchanged.

    **(a.2) The feature-set signal counts EDIT-PATH references, not bare
    name mentions.** A single-feature sub-issue's prose often names OTHER
    features without editing them (`replace with rabbit-issue vocabulary`,
    `mirrors what rabbit-spec does`); a bare feature-NAME token names a
    vocabulary or peer, not an EDIT TARGET, and MUST NOT inflate the
    cross-scope feature count. The feature-set signal (a) therefore counts
    ONLY EDIT-TARGET references: the `feature:` label PLUS every distinct
    `.claude/features/<name>/` PATH literally referenced in the body. Bare-name
    matches (Inv 26 method-(c)) are EXCLUDED here, though they remain in
    `features` / `cross_scope_features` for Stage-2 shaping. A
    `.claude/features/<name>/` PATH on a READ-ONLY line is ALSO EXCLUDED:
    a line carrying a read-only verb (case-insensitive: `verify against`,
    `confirm against`, `read-only`, `do not edit`, `don't edit`, `refer to`,
    `see`) names a CONFIRMATION target, not an EDIT target — e.g. `verify
    against .claude/features/contract/lib/runtime.py` — so it MUST NOT inflate
    the cross-scope EDIT-PATH count. So a one-feature sub-issue whose prose
    merely MENTIONS other feature NAMES, or merely verifies-against another
    feature's path, yields `cross_scope: false`; a body listing 2 or more
    distinct feature EDIT-PATHS still yields `cross_scope: true`.

    **(b) plan-batch routes on the EDIT-TARGET count, unioned with
    `cross_scope`.** `plan-batch.py` routes a work item to the
    barrier/decomposition lane on EITHER multi-feature signal, shaping
    `parallel-per-feature` only when BOTH say single-scope: (1) the EDIT-TARGET
    count `len(item["edit_features"]) > 1` — the item WRITES to >1 feature dir,
    so a bounded per-feature subagent cannot complete it; or (2) `cross_scope:
    true` — never `parallel-per-feature` even at edit-target count 1 (a
    phrase-only repo-wide sweep or cross-feature DECLARATION). Either way the
    item gets `decomposition` at/above `--decompose-threshold`, else
    `multi-subagent-barrier`. The count is `edit_features`, NOT the broader
    `features` mention set: an item that EDITS one feature but merely MENTIONS
    another (a bare-name in prose, or a read-only `verify against <path>`) has
    `len(edit_features) == 1` and shapes `parallel-per-feature` even though its
    `features` list is longer; a genuine multi-EDIT still shapes
    barrier/decomposition. **Conservative bias:** when edit-intent is AMBIGUOUS
    the broader routing (barrier) is SAFER — under-shaping a genuine multi-EDIT
    item FAILS dispatch at the first cross-feature write, over-shaping merely
    runs slower — so the `cross_scope: true` union is kept and the
    `edit_features` count falls back to `len(item["features"])` (then 1) when
    absent/empty rather than collapsing to 1 directly.

    **(c) Cross-scope items are surfaced distinctly.** `plan-batch.py` lists
    every item it shaped `multi-subagent-barrier` or `decomposition` under a
    `cross_scope_items` output key (sorted ascending; always present, empty when
    none), in lock-step with routing.

    Enforced by `test/test-cross-scope.py` (triage sets `cross_scope: true` for
    a body referencing 2 or more `.claude/features/<name>/` paths and for a
    `repo-wide` phrase; `false` for an ordinary single-feature body, a
    parent-reference-line quote (a.1), a bare-NAME mention (a.2), and a read-only
    `verify against <path>` mention (a.2); `true` for an explicit `Cross-feature
    (A + B)` / `spans X and Y` DECLARATION — and triage emits `edit_features`
    narrow to the labelled feature for the mention/read-only cases — and
    plan-batch routes on the EDIT-TARGET count unioned with `cross_scope` (b): an
    item that EDITS one feature but MENTIONS another (`edit_features` length 1)
    shapes `parallel-per-feature`, absent from `cross_scope_items`; a genuine
    multi-EDIT (`edit_features` length > 1) and a `cross_scope: true` item are
    barrier/decomposition + in `cross_scope_items`), `test/test-plan-batch.py`
    (`edit_features=["a","b"]` → barrier; `edit_features=["a"]` with
    `features=["a","b"]` → `parallel-per-feature`; `len(edit_features) >=
    --decompose-threshold` → `decomposition`), and `test-spec-cross-scope-invariant.py`.

52. **Proactive `.gitignore` seeding is the policy; reactive single-file
    additions are a fallback only.** The repo-root `.gitignore` MUST be
    proactively seeded with the full known set of runtime artifacts that
    the Claude Code platform and the rabbit workflow write into a checkout,
    so a newly-running loop or subagent never trips `safety-check.py`
    Invariant 5 ("working tree clean") on an artifact discovered the hard
    way. Discovering an untracked runtime file at merge time and filing an
    issue to add that one pattern is the FALLBACK posture, never the
    primary one: the primary posture is that the set is enumerated up front
    from its sources (the markers and runtime files declared across the
    feature specs and written by the hooks/scripts) and seeded in one
    sweep. Concretely, beyond the `.rabbit-auto-evolve-*` glob (Inv 23) and
    the `.claude/scheduled_tasks.{lock,json}` entries (Inv 24), the
    `.gitignore` MUST carry the per-feature scope-marker glob
    `.rabbit-scope-active-*` — the bare `.rabbit-scope-active` token alone
    does NOT match a per-feature `.rabbit-scope-active-<feature>` marker, so
    without the glob a stray per-feature marker can be committed. Seeded
    patterns MUST be grouped under comments naming their source (Claude
    Code platform vs. rabbit feature) so the provenance of each entry is
    auditable. Enforced by `test/test-gitignore-seeded-runtime-artifacts.py`,
    which copies the repo-root `.gitignore` into a tempdir initialized as a
    git repo, writes each artifact in the known seed set — including a
    per-feature `.rabbit-scope-active-<feature>` marker — runs
    `git status --porcelain`, and asserts none of them appear in the output.

53. **Decomposed-parent lifecycle closes deterministically off the
    GitHub-native sub-issue rollup; `decomposition_parents` is a deprecating
    machine mirror honored during coexistence.**
    When `plan-batch.py` shapes an item as `decomposition`
    (>= `--decompose-threshold` features) and the dispatcher files the N
    per-feature child sub-issues (a `rabbit-issue` contract INVOKE, not a
    cross-feature edit), it links each child to its parent as a GitHub-native
    sub-issue by filing it with
    `rabbit-issue/scripts/file-item.py --parent <parent#>`, and it records the
    parent->children linkage in machine-readable form by invoking
    `python3 .claude/features/rabbit-auto-evolve/scripts/record-decomposition.py
    <parent#> <child#> [<child#> ...]`, which persists the link under the
    state's `decomposition_parents` map (parent-issue-number string ->
    list of child issue numbers; schema 1.3.0). Both writes are machine-first:
    the GitHub-native sub-issue link is itself a machine source (GitHub exposes
    `sub_issues_summary{total, completed}` on the parent), and the state map
    mirrors it. The loop NEVER enumerates a parent's children from a prose
    comment table — that historical machine-first violation is what left
    decomposed parents lingering OPEN after every child closed.
    Each tick, the post-merge drain (`run-post-merge.py`, after the
    catch-up phase) runs
    `python3 .claude/features/rabbit-auto-evolve/scripts/close-decomposed-parents.py`,
    which for EVERY tracked parent reads the AUTHORITATIVE close-source — the
    GitHub-native sub-issue rollup on the parent
    (`gh api repos/{slug}/issues/<parent>` -> `sub_issues_summary`) — and,
    when the parent has sub-issues and ALL are complete
    (`total > 0 and completed == total`), closes the parent
    (`gh issue close <parent#> --reason completed` with a roll-up comment) and
    removes the parent key from `decomposition_parents`. COEXISTENCE: a parent
    that carries a `decomposition_parents` entry but has NO GitHub-native
    sub-issues yet (`total == 0`) falls back to the legacy hand-rolled check —
    its recorded children are queried individually via `gh issue view <child#>`
    and the parent is closed only when EVERY recorded child is CLOSED. A parent
    whose native rollup is incomplete, or whose legacy fallback finds any child
    still OPEN, is left untouched (the step is a no-op for it). The step is
    idempotent: a clean no-op when the map is empty/absent, and a parent already
    closed (key already removed) is never re-processed. The roll-up close is
    SCRIPT-BACKED (script > CLI > spec > prompt) — it is never a dispatcher
    judgment call.
    The `decomposition_parents` map is a deprecating mirror: it is honored
    during the coexistence window so the parents recorded before native linking
    shipped keep closing. Its deprecation criterion: drop the
    `decomposition_parents` schema field and the legacy hand-rolled fallback
    once no open parent carries a `decomposition_parents` entry.
    Enforced by `test/test-close-decomposed-parents.py` (native rollup
    completed==total>0 -> parent closed + key dropped; native rollup
    completed<total -> parent untouched; legacy-map coexistence with no native
    sub-issues -> recorded parent still closes off the hand-rolled check; empty
    map -> clean no-op) and `test/test-record-decomposition.py` (the linkage
    record round-trips through `decomposition_parents` and validates against
    schema 1.3.0), with the wiring asserted by `test/test-run-post-merge.py`.

54. **Per-tick dispatch journal — resume skips completed subagents and
    re-dispatches only the unfinished; it subsumes the vestigial `in_flight`
    field.** Phase 6 fans out N TDD subagents (Inv 28). A tick interrupted
    after K of N finish (context cutoff, scheduler kill, crash) must let the
    NEXT tick resume the remaining N-K without re-running the K completed and
    without racing a duplicate dispatch against an already-open PR. A
    rabbit-native, on-disk per-tick dispatch journal — owned by this feature's
    dispatch state, with NO dependency on native Workflow (the COEXIST verdict
    stands) — closes that gap.

    ### `dispatch_journal` state field (schema 1.4.0)

    The state schema gains an OPTIONAL `dispatch_journal` object (additive
    `schema_version` bump to `"1.4.0"`; absent pre-1.4.0 states behave exactly
    as today), keyed by tick-id string. Each value is
    `{started_at: ISO-8601 UTC, entries: [<entry>, ...]}`; each entry records
    one dispatched subagent. `issue` (int), `feature` (string), `shape`
    (string), and `status` are REQUIRED; `branch`/`worktree`/`pr` are nullable
    (a dispatch is recorded before its branch/PR exist). The `status` enum is
    exactly `{dispatched, pr_open, completed, aborted}`: `dispatched` (Agent
    issued, no result), `pr_open` (PR returned, not merged), `completed` (PR
    merged / issue closed), `aborted` (subagent aborted). `update-state.py`'s
    validator recognizes the field; the additive-migration ladder seeds a
    pre-1.4.0 state's `dispatch_journal` to `{}`.

    ### `record-dispatch.py` — the script-owned WRITE point

    `record-dispatch.py --tick-id <id> --issue <N> --feature <name>
    --shape <shape> [--status <status>] [--branch <b>] [--worktree <w>]
    [--pr <N>]` performs an atomic read-modify-write of the journal entry for
    `<issue>` under tick `<id>` in `<state_dir>/auto-evolve-state.json` (state
    dir via `RABBIT_AUTO_EVOLVE_STATE_DIR`, else `<cwd>/.rabbit`). The
    dispatcher invokes it at Phase 6: one append per Agent call at dispatch
    time (`status: dispatched`), and one UPDATE when each HANDOFF returns
    (`pr_open`/`aborted`, recording branch/PR). A repeated call for the same
    `(tick-id, issue)` UPDATES the existing entry in place (never duplicates),
    seeding `started_at` once per tick. The write is SCRIPT-OWNED so the
    SKILL.md Phase 6 body carries no computed-value bash (Script-Backed
    Orchestration). Emits the entry as JSON; exit non-zero (loud, locatable —
    never a silent drop) on a missing state file or invalid args.

    ### `resume-dispatch.py` — the script-owned READ/RESUME point

    `cat plan.json | resume-dispatch.py --tick-id <id>` reads the active
    tick's journal and partitions the planned `selection_order` (stdin) into a
    `dispatch` set (re-enter Phase 6) and a `skip` set, emitting
    `{"dispatch": [...], "skip": [...]}`. Per journal status: `completed` and
    `pr_open` -> SKIP (the open PR drains through the merge path, Phase 7 —
    never a second dispatch); `dispatched` with no PR, `aborted`, or an issue
    ABSENT from the journal -> RE-dispatch. This converts whole-tick
    re-derivation into per-subagent resume; a missing/empty journal yields
    every planned issue in `dispatch` (the no-regression base).

    ### `completed` transition and journal lifecycle

    `merge-prs.py --record-pending` marks an issue's journal entry `completed`
    (recording its `pr`) in the SAME read-modify-write that appends to
    `pending_post_merge` (Inv 30): every issue a merged PR closes (the parsed
    `Closes/Fixes/Resolves #N` set) whose journal entry exists is promoted — no
    new write site. `run-post-merge.py` prunes the journal where it clears
    `pending_post_merge` (a tick whose entries are all `completed`/`aborted` has
    its key dropped, bounding on-disk growth).

    ### `in_flight` subsumption and off-ramp

    The vestigial `in_flight` field — declared/validated but NEVER populated by
    any phase script nor consulted by `fetch-queue.py` — is dropped from the
    schema's REQUIRED set (still OPTIONAL for backward compat). The journal's
    `dispatched`/`pr_open` entries are the real in-flight set; `status-report.py`
    DERIVES its `in_flight` output as a read-only projection of the journal,
    falling back to a literal `in_flight` array when no journal is present — so
    the `status` surface is unchanged. The block is additive: to roll back, make
    `record-dispatch.py` a no-op and drop the `resume-dispatch.py` consult; the
    loop reverts to re-fetch-each-tick with GitHub open-state as the de-facto
    journal (`pending_post_merge` + `clean-dispatch-leaks.py` UNCHANGED).

    Enforced by `test/test-record-dispatch.py` (append + update-in-place +
    `started_at`-once + missing-state error), `test/test-resume-dispatch.py`
    (completed/pr_open SKIP; dispatched-no-PR/aborted/absent re-dispatch; empty
    journal = no-regression base), `test/test-merge-prs.py` (merge marks the
    entry `completed`), `test/test-run-post-merge.py` (drained tick pruned on
    clear), `test/test-status-report.py` (`in_flight` derived), and
    `test/test-state-persistence.py` (schema 1.4.0 accepts `dispatch_journal`,
    `in_flight` not required, 1.3.0 -> 1.4.0 migration seeds it `{}`).

55. **Per-tick `in-progress` label reconcile mirrors the live dispatch set
    onto the GitHub `in-progress` label, self-healingly.** The dispatch journal
    (Inv 54) is the authoritative in-flight set but lives only on disk;
    `reconcile-labels.py` reflects it onto the sanctioned `in-progress` category
    label so GitHub stays truthful. It computes the LIVE set by REUSING
    `status-report.py`'s live-set logic (the `dispatched`/`pr_open` union — never
    forked), then reconciles: ADD the label to live OPEN issues lacking it; STRIP
    it from OPEN issues carrying it but no longer live, so a crashed tick's stale
    label self-heals next tick. It is idempotent. The label is ensured to exist
    first via the rabbit-issue `ensure_labels` mechanism (a cross-scope INVOKE of
    `rabbit-issue/scripts/_gh.ensure_labels`, declared in `contract.md`
    `invokes.modules` — never a cross-feature edit). `gh`/network failure is
    logged and the reconcile continues, NEVER crashing the tick (label hygiene
    must not block evolution, like the Inv 49 sweep). The reconcile fires at
    THREE touchpoints, each a SCRIPTED invocation of `reconcile-labels.py` — the
    logic stays in the script; a caller only triggers it, per the
    script-backed-orchestration standard (the SKILL invokes the script, never
    hand-assembling label logic): (a) **phase-6 in-session add** — the
    live-session dispatcher runs it at the END of phase 6, AFTER recording all
    `dispatched` journal entries and BEFORE firing the Agent calls, so
    `in-progress` is stamped on the just-dispatched set and stays visible for the
    FULL minutes-to-hours TDD subagent execution window users observe; (b)
    **post-dispatch add-on-entry** — `run-tick-phases.py`'s `post-dispatch`
    segment runs it at the START, BEFORE any merge drains the live set, so even a
    single-tick item is labelled before merge AND the HEADLESS path (which skips
    phase 6) still gets the add; (c) **post-persist strip-on-exit** — the same
    segment runs it AFTER phase 11 (persist) to STRIP the label from issues that
    have left the live set. The (b)/(c) calls are script-owned and identical on
    both paths; (a) is a dispatcher-triggered SCRIPTED invocation, NOT a
    hand-assembled label step. Any call failing is recorded but never fails the
    tick. Enforced by `test-reconcile-labels.py` (add/strip; idempotent;
    self-heal; graceful `gh` failure; empty-journal no-op),
    `test-run-tick-phases.py` (before merge AND after persist), and
    `test-tick-skill.py` (phase-6 record-all → reconcile → Agent order).

56. **The empirical CronCreate jitter offset is owned, computed, and
    persisted by this feature.** CronCreate applies a DETERMINISTIC
    per-job jitter to recurring tasks: a recurring job fires up to 10% of its
    period late, capped at 15 min (CronCreate's own documented bound). On an
    idle session this is a stable constant, not a range and not idle-gating —
    the `13,43 * * * *` 30-min-period heartbeat fired a constant `+13` min late
    every time (ETA 21:43 fired 21:56, 22:13 fired 22:26, 22:43 fired 22:56).
    `scripts/tick-jitter.py` owns this value. It computes the offset as the
    median of `actual_fire_time − nearest_prior_cron_boundary` over the recent
    recorded fires in `.rabbit/tick.log` (Inv 36; each line carries an
    ISO-8601 UTC `ts`), and persists it to the rabbit-auto-evolve-owned state
    artifact `.rabbit/auto-evolve-tick-jitter.json` so other features (e.g.
    `contract`'s Stop line) can READ the value WITHOUT importing this feature.
    The artifact schema is
    `{schema_version, observed_jitter_minutes (int ≥ 0), period_minutes,
    sample_count, cold_start (bool), computed_at, owner,
    deprecation_criterion}`. When there is NO recorded fire history yet,
    `observed_jitter_minutes` falls back to the documented cold-start bound
    `min(15, ceil(period_minutes * 0.10))` and `cold_start` is set true; this
    is clearly a fallback, NOT the empirical value. The `compute` that WRITES the
    artifact is wired into the shared phase-walk (`run-tick-phases.py
    post-dispatch`, Inv 40) as a both-paths hygiene step. The CronCreate constraint
    that jobs fire only while the REPL is idle (never mid-query) means a
    boundary missed mid-query is DELIVERED at the next idle moment, not
    silently skipped — but on an idle session every boundary is delivered
    on time-plus-jitter, which is why the offset is a stable constant. The
    state-dir resolution honors `RABBIT_AUTO_EVOLVE_STATE_DIR` (matching
    `tick-log.py` / `update-state.py`), and the wall-clock is overridable via
    `RABBIT_AUTO_EVOLVE_NOW` (ISO-8601) for deterministic tests. Enforced by
    `test/test-tick-jitter.py` (median over a `+13` fire history; cold-start
    fallback; log degradation; persisted schema), the `test-banner-status.py`
    boundary-plus-offset assertions, and `test/test-tick-jitter-compute-wired.py`
    (the post-dispatch compute wiring: the banner reads the empirical ETA).

57. **The live release track is the `vX.Y.Z` git tags + per-feature
    changelogs — NOT the dead-track root `CHANGELOG.md`.** The canonical,
    machine-truth record of what this feature ships at each release is the
    annotated `vX.Y.Z` git tag cut by `release-bump.py` (Inv 7) — now at
    the `v9.x` line — together with each touched feature's own
    `docs/CHANGELOG.md` entry written by its version-bumping subagent. The
    repo-root `CHANGELOG.md` is a SEPARATE, now-dead versioning track: it
    is owned by `rabbit-cage` and maintained under the legacy `release/1.x`
    install-branch protocol, frozen at `release/1.12.0` (`rabbit-cage`'s
    install spec names "the dead `release/*` branch channel (frozen at
    1.12.0)" against "the live dev-tag release channel"). Root
    `CHANGELOG.md` therefore does NOT track the `v9.x` tags and is NOT this
    feature's authority. It is also OUT of this feature's writable scope —
    `rabbit-cage`'s scope-guard `RABBIT_CAGE_OWNED_ROOT` does not include
    `CHANGELOG.md`, and no rabbit-auto-evolve scope marker authorizes a
    repo-root write — so `release-bump.py` MUST NOT write root
    `CHANGELOG.md`. Any consumer needing the live release history (e.g. the
    `rabbit-update install` post-update changelog summary) MUST source it
    from the git tags plus per-feature changelogs, never from the
    dead-track root `CHANGELOG.md`; re-sourcing that summary is a
    `rabbit-cage` concern (the install post-update summary is
    rabbit-cage-owned) and is filed as a discovered issue, not edited here
    (bounded scope). Enforced by `test/test-release-track-source.py` (an
    invariant records both the live track — git tags via `release-bump.py`
    plus per-feature changelogs — and the dead/out-of-scope root
    `CHANGELOG.md` `release/1.x` track).

58. **A decomposition parent is excluded from the dispatchable plan; it
    converges via child rollup, not dispatch.** A decomposition parent — an
    OPEN issue that HAS children — carries no own code change: its work landed
    across N per-feature child sub-issues, and it is closed deterministically
    off the GitHub-native sub-issue rollup once every child closes (Inv 53). It
    must therefore NEVER be dispatched to a TDD subagent. `triage-issue.py`
    detects a parent and emits `decomposition_parent: true` on the triage
    object, aligning with the authoritative source: PRIMARY, the GitHub-native
    sub-issue rollup shows the issue HAS children
    (`gh api repos/{slug}/issues/<n>` -> `sub_issues_summary.total > 0`);
    COEXISTENCE fallback, the issue is a key in the `decomposition_parents`
    state map (read via the `RABBIT_AUTO_EVOLVE_STATE_DIR` state-access path the
    sibling phase scripts share). The native-rollup read reuses the same
    `sub_issues_summary` access `close-decomposed-parents.py` uses. A still-OPEN
    issue flagged `decomposition_parent: true` is FILTERED out of the plan by
    `plan-batch.py`: it is neither selected (`selection_order`) nor shaped
    (`dispatch_shapes`) nor listed in `cross_scope_items`, while remaining OPEN
    and tracked. This does NOT violate the convergence guarantee (Inv 25): the
    parent is tracked-by-decomposition, an existing non-work tracked outcome
    that converges via child rollup rather than dispatch. A child sub-issue (it
    has a PARENT link but no children of its own, so its rollup total is 0 and
    it is not a map key) is NOT a parent and is selected and shaped normally;
    an ordinary single-feature issue is unaffected. The
    `decomposition_parents` map-based fallback is a deprecating mirror honored
    during the same coexistence window Inv 53 established; its deprecation
    criterion: drop the map-based fallback once no open parent carries a
    `decomposition_parents` entry. Enforced by
    `test/test-exclude-decomposition-parents.py` (the full triage -> plan pipe:
    a native-rollup parent and a state-map-only parent are both excluded from
    `selection_order` / `dispatch_shapes` / `cross_scope_items`, while a child
    with a parent link and an ordinary issue are still selected and shaped) and
    by `test/test-plan-batch.py` (a `decomposition_parent: true` item is dropped
    from the plan while co-batched ordinary items remain).

59. **The GitHub-native dependency relationship is the authoritative source of
    an issue's blocked state; the body `blocked-by:` text is a deprecating
    coexistence mirror.** `triage-issue.py` rule 5 reads the AUTHORITATIVE
    source — `gh api repos/{slug}/issues/<n>/dependencies/blocked_by`, an array
    of blocker issues each carrying `{number, state, title}` — and defers
    `blocked` (with the open blocker numbers in `blocked_by`) when any listed
    blocker's `state` is `open`. An issue whose native blockers are all CLOSED,
    or which has no native blocker, is not blocked by this source. The read
    reuses the `gh api repos/{slug}/issues/...` pattern Inv 53/58 use; a
    transient read failure yields no native blocker (the body mirror is then
    consulted), so a flaky `gh` call never strands an issue. The body
    `blocked-by: #N` text declaration is a deprecating coexistence mirror,
    consulted ONLY when the native source reports no open blocker so an
    in-flight issue that pre-dates a native dependency link is honored; the
    mirror keeps the STRUCTURAL, never-substring detection (a prose mention of
    the `blocked-by:` token is NOT a declaration and passes through). The
    dispatch path that records a discovered blocker prefers creating the native
    relationship (`gh api --method POST
    repos/{slug}/issues/<n>/dependencies/blocked_by -F issue_id=<blocker-id>`);
    the label/body marker is a deprecating fallback. Deprecation criterion:
    drop the `blocked-by: #N` body parser and the legacy `blocked-by:` label
    once no open issue carries a `blocked-by:` body marker or label and native
    dependencies are the sole expressed ordering source. Enforced by
    `test/test-triage-rules.py` (the `gh` shim serves
    `gh api .../dependencies/blocked_by`: an OPEN native blocker defers
    `blocked`; all-CLOSED native blockers are actionable; no native blocker but
    a structural `blocked-by: #N` to an open issue still defers via the mirror;
    a prose-only `blocked-by:` mention passes through as `work`).

60. **The GitHub-native duplicate state is the authoritative resolution of a
    detected duplicate; the reinvented `duplicate` label is a deprecating
    coexistence mirror.** DETECTION is unchanged: `triage-issue.py` rule 3
    flags a duplicate by the case-folded title-substring match against
    closed-in-last-30-days issues; that confidence gate is preserved exactly,
    and the rule still emits `decision=close-not-planned`,
    `reason_code=duplicate`, now also echoing the matched closed issue's number
    in `duplicate_of` (null when no match). RESOLUTION is recorded natively:
    `scripts/resolve-duplicate.py resolve <dup> <canonical>` closes the
    duplicate with `gh api --method PATCH repos/{slug}/issues/<dup> -f
    state=closed -f state_reason=duplicate` — the authoritative native marker —
    and posts one cross-reference comment naming the canonical issue. The close
    is a TERMINAL convergence (consistent with Inv 25): a native
    close-as-duplicate is a CLOSE, never a label-strip-while-open de-queue, and
    fires only on a heuristic-confirmed match (gate never loosened). The
    reinvented `duplicate` label is honored ONLY on read (`resolve-duplicate.py
    status <n>` reports a legacy label-stamped duplicate as recognized); a new
    resolution NEVER stamps the label, only the native state. The read reuses
    the `gh api repos/{slug}/issues/...` pattern Inv 53/58/59 use; a transient
    gh failure is reported as an error, never silently stripping a label or
    leaving the issue open-but-untracked. Deprecation criterion: drop the
    `duplicate` label read once no open or recently-closed issue carries the
    label and native `state_reason=duplicate` is the sole expressed duplicate
    marker. Enforced by `test/test-resolve-duplicate.py` (the `gh` shim serves
    the native PATCH and a `gh issue view` read) and by
    `test/test-triage-rules.py` (rule 3 still emits
    `close-not-planned`/`duplicate` AND echoes `duplicate_of`).

61. **The loop integrates merged work into a single resolved integration
    target, with a `dev`<->`main` coexistence window.** The loop's merge,
    safety, and release phase scripts integrate into ONE resolved "integration
    target" branch rather than a hard-coded `dev`. The target is resolved by
    `scripts/integration_target.py`: the `RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET`
    env var when set, else the default `dev`. The module exposes
    `resolve_target()`, `accepted_targets()` (the coexistence set `{dev,
    main}`), and `is_default_branch(t)` (true iff `t` is the default branch
    `main`); the sibling phase scripts import it relative to their own file (not
    via `RABBIT_AUTO_EVOLVE_SCRIPT_DIR`, which tests repoint at a shim dir). An
    override outside the accepted set is an error.

    During the coexistence window BOTH branches are honored so the running loop
    keeps operating before the admin cutover (the `dev`→`main` merge plus branch
    protection) flips the default. Concretely:

    1. `merge-prs.py` ACCEPTS a PR whose base is EITHER `dev` or `main`
       (`accepted_targets()`); a base that is neither is refused with
       `reason: "base-not-accepted"` and `gh pr merge` is never invoked
       (defense-in-depth above `safety-check.py`).
    2. `safety-check.py` Inv 1 asserts the current branch IS the resolved
       target; Inv 2 accepts any base in the coexistence set. The
       defense-in-depth intent is preserved — a branch/base outside the
       accepted set is refused.
    3. `release-bump.py` cuts the `gh release` against the resolved integration
       target (`--target <target>`) rather than a hard-coded `dev`.
    4. The manual close-after-merge in `merge-prs.py` (Inv 6 step 4) runs ONLY
       when the PR's base — the branch it merged INTO — is NOT the default
       branch. GitHub's native `Fixes/Closes/Resolves` keyword auto-close fires
       on a merge to the default branch (`main`) but not on a non-default
       branch (`dev`); keying the decision on the merged-into base is the
       precise condition (it coincides with the resolved target in the normal
       flow, where work targets the resolved branch). So the loop performs the
       explicit close for a `dev`-base merge and skips it for a `main`-base
       merge because the native close fires. The merge SHA is still recorded as
       `last_merged_sha` under either base.
    5. The merge invocation keys on the SAME default-branch axis: `merge-prs.py`
       adds `--admin` to `gh pr merge <#> --squash` when the base IS the default
       branch (`main`, branch-protected with a required review the loop cannot
       satisfy on its own PR) to override ONLY that structural required-review
       (`enforce_admins: false` permits it; the real quality gate, the contract
       repo-gate run pre-merge, is unchanged); a `dev`-base merge keeps the plain
       `--squash` with NO `--admin`. Same axis as item 4's manual-close skip
       (`main` ⇒ `--admin` AND skip manual close; `dev` ⇒ neither).

    Deprecation criterion: when `main` is the sole integration target after the
    cutover, drop the coexistence accepted-set and the
    `RABBIT_AUTO_EVOLVE_INTEGRATION_TARGET` override (the resolved target
    becomes a constant `main`) and remove the manual close-after-merge path
    (native keyword auto-close is then the only close path).

    Enforced by `test/test-integration-target.py` (default resolves to `dev`;
    env override resolves to `main`; an unrecognized override is rejected; the
    accepted set is exactly `{dev, main}`; `is_default_branch` recognizes
    `main` not `dev`; CLI surface), `test/test-merge-prs.py` and
    `test/test-safety-check.py` (the coexistence acceptance + conditional
    close + the `--admin`-on-default-branch / no-`--admin`-on-`dev` merge cases
    + refusal cases above), `test/test-release-bump.py` (the
    `gh release create --target` follows the resolved target), and
    `test/test-spec-integration-target-invariant.py` (this text present).

62. **The dispatchable plan contains ONLY dispatchable `work` items.**
    `plan-batch.py`'s single up-front filter (the same point that drops a
    `decomposition_parent`, Inv 58) admits an item into ALL plan outputs
    (`selection_order`, `dispatch_shapes`, `cross_scope_items`) ONLY when it is
    genuinely dispatchable. An item is excluded when ANY holds: (1) its
    `decision` is neither `work` nor `research`; (2) it is a
    `decomposition_parent: true` (Inv 58); OR (3) it is still NATIVELY BLOCKED —
    a non-empty `blocked_by` of OPEN blocker numbers (Inv 59) TOGETHER WITH a
    blocked-origin `reason_code` (`blocked`, or `defer-limit-reached` after a
    force-promotion). Clause 3 closes the leak: `triage-batch.py`'s
    anti-infinite-defer counter (Inv 18) FORCES a repeatedly-deferred blocked
    item to `decision=work` (`reason_code=defer-limit-reached`), lifting the
    defer verdict but NOT clearing the open blocker, so the decision-only drop
    would let it reach a TDD subagent it cannot land. The reason_code gate spares
    a `blocked_by` carried purely as a blocking-fanout signal (Inv 44). No Inv 25
    violation: a blocked item stays OPEN and tracked-by-dependency and re-enters
    the plan once its blocker closes. An unblocked `work` item, a `research`
    item, and a `cross_scope` work item are unaffected. Enforced by
    `test/test-plan-batch.py` (a `defer`/`blocked` item, a
    `close-not-planned`/`duplicate` item, and a force-promoted-but-still-blocked
    `work` item all ABSENT from the plan; a plain `work` and a `cross_scope` work
    item retained).

63. **The merge phase runs an isolated pre-merge install + update smoke that
    BLOCKS the merge on install/closure breakage.** `safety-check.py --phase
    merge` runs the sibling `install-smoke.py` (bottom-line check 6) before any
    `gh pr merge`, so install/closure breakage — fresh-install
    `publish_file ... source not found` aborts, `--update` closure-shrink
    failures — is caught BEFORE a PR merges, not after it lands on dev.
    `install-smoke.py` runs, inside a `tempfile.TemporaryDirectory()` (cleaned
    up on exit), a fresh install (`install.py --src <repo-root> --target
    <tmp>/fresh`) plus an `--update` against that same target, asserting exit 0
    AND no install-failure signature (`source not found`, `publish failure`,
    closure/dangling wording) in the combined output of either invocation. Both
    invocations pass `--src <repo-root>` so the smoke is fully offline;
    install.py is invoked as a BLACK BOX subprocess — a contract INVOKE of
    rabbit-cage, never an edit. The repo root defaults to the script's inferred
    repo (overridable via `--repo-root` / `RABBIT_AUTO_EVOLVE_REPO_ROOT`);
    install.py resolves at `<repo-root>/.claude/features/rabbit-cage/install.py`
    (overridable via `RABBIT_AUTO_EVOLVE_INSTALL_PY`); the sibling
    `install-smoke.py` is overridable for safety-check tests via
    `RABBIT_AUTO_EVOLVE_INSTALL_SMOKE`. A non-zero smoke exit fails the merge
    phase, so `merge-prs.py` records the PR `skipped`/`safety-check-failed` and
    the batch does NOT merge (the smoke never silently passes). It is
    merge-only (release and cleanup never run it). Resilient SKIP (exit 0): when
    install.py is absent (a degenerate self-build / isolated git tempdir) the
    smoke skips gracefully, matching the contract Inv 64/65 resilient-skip
    pattern. Runtime is one fresh install + one `--update` to tmp (sub-second on
    a warm tree). Enforced by `test/test-install-smoke.py` (PASS on the real
    tree; FAIL on a shim install.py exiting non-zero, on a `source not found`
    signature at exit 0, and on an `--update` failure; SKIP when install.py is
    absent), `test/test-safety-check.py` (merge blocks on a failing smoke shim,
    passes on a passing one, release/cleanup never run it), and
    `test/test-spec-install-smoke-invariant.py` (this text + the contract
    install.py INVOKE + the merge-phase check-6 wiring).

64. **Version narration is grounded in the AUTHORITATIVE current version,
    surfaced FRESH each tick — never a value carried in accumulated session
    context.** On the CronCreate session-reuse path the dispatcher
    session is REUSED across ticks and context ACCUMULATES (Inv 33), so the
    evolver can narrate a STALE version anchored in old context — citing
    an old `vX.Y.Z` even though the authoritative state
    (`auto-evolve-state.json` `last_tagged_version`) and `git describe --tags`
    were current. The stale string lived ONLY in accumulated session context;
    no persistent artifact carried it. To eliminate the failure mode, the loop
    SURFACES the authoritative current version each tick so any narrator reads
    it fresh: `schedule-decision.py` (the tick-exit / heartbeat schedule
    output) emits an `authoritative_version` field on EVERY decision (both
    `immediate-refire` and `idle`), resolved THIS TICK from `git describe
    --tags --abbrev=0` (the live repo tag, authoritative), falling back to the
    state `last_tagged_version`, falling back to null (honest absence, never a
    fabricated string). The git-describe value WINS over the state value so a
    stale cached `last_tagged_version` can never shadow the live tag. The
    loop's version narration / banner MUST cite this authoritative value — the
    git-describe / state `last_tagged_version` source — and MUST NOT cite a
    version carried in accumulated session context: this is the machine-first
    grounding (a fresh authoritative number every tick for the dispatcher to
    cite). The git invocation is overridable via
    `RABBIT_AUTO_EVOLVE_GIT_DESCRIBE_CMD` and the state dir via
    `RABBIT_AUTO_EVOLVE_STATE_DIR` for deterministic tests. The pure resolver
    is exposed as `resolve_authoritative_version()`. Enforced by
    `test/test-authoritative-version.py` (the fresh value on both decision
    paths; the git-describe value overriding a stale cached state value; the
    state fallback when git-describe is unavailable; null when neither
    resolves).

## Known gaps

- All implementation phases complete. The activation surface lives on
  `/rabbit-auto-evolve on|off` (Inv 11). The Phase F manual smoke test (`on`,
  restart Claude, observe banner, `start`, observe tick, `stop`, `off`) remains
  pending — it needs user-driven restart and observation, not a TDD cycle.

## What this feature does NOT define

- The `contract.lib.runtime` APIs `emit_auto_evolve_banner`,
  `emit_auto_evolve_stop_line`, and the suppression hook in
  `iterate_configurables_alerts` / `_banner` — owned by the `contract` feature.
- The `tdd-step.py abort` subcommand and the HANDOFF JSON fields
  `discovered_issues` / `aborted_reason` — owned by the `tdd-subagent` feature.
- The `human-approval` and `bypass-permissions` configurables themselves —
  owned by the `rabbit-cage` feature. This feature only flips them during
  `set-evolve-mode.py`.
- The TDD cycle itself — owned by `tdd-subagent`, orchestrated by
  `rabbit-feature-touch`. This feature consumes them.
- The `gh` CLI wrapper for issues — owned by `rabbit-issue`, consumed here.
