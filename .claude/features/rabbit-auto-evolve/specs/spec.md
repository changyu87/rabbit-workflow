---
feature: rabbit-auto-evolve
version: 0.22.0
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
> Phase A prerequisites landed in commits `7b4e4b4` (PR #330 — #327),
> `5a6d195` (PR #331 — #328), `73d1217` (PR #332 — #329).

## Purpose

A self-driving rabbit loop that continuously fetches open `rabbit-managed`
GitHub issues, triages each one, dispatches TDD subagents to implement
actionable work, merges approved PRs into `dev`, tags versioned releases,
and is fired on a fixed cadence by a system cron (the sole tick scheduler;
see Inv 32) until the user issues an explicit stop — all without requiring
human approval at each step. (Pre-Inv 32 the loop self-chained via
`ScheduleWakeup`; that mechanism was removed in issue #414.)

## Paths governed

- (none — standalone feature)

This feature's own spec and contract live under `specs/` (`specs/spec.md`,
`specs/contract.md`) per the issue #399 migration of `docs/spec/` → `specs/`.
The sibling `docs/bugs/` directory is retained. Any tooling this feature owns
that resolves a feature's spec/contract path (e.g. `scripts/triage-issue.py`)
MUST prefer the `specs/` layout and accept the legacy `docs/spec/` layout as a
fallback during the coexistence window.

## Public surface

The `scripts/` directory is currently empty. The following scripts are the
planned surface; all are added during Phase C of
`docs/superpowers/plans/2026-06-01-rabbit-auto-evolve.md`.

**Configuration entry (via `/rabbit-config`)** — declared in `feature.json`:

- `auto-evolve on` / `auto-evolve off` — compound activation mutator; both
  values dispatch via `run_feature_script → scripts/set-evolve-mode.py
  {on|off}`; `restart_required: true`.

**Skill: `rabbit-auto-evolve`** (to be declared in `feature.json.surface.skills`;
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

**Scripts (Phase C — none on disk yet):**

| Script | Kind | Description |
|---|---|---|
| `scripts/set-evolve-mode.py` | CLI | Compound mutator: `on` flips `human-approval=false`, `bypass-permissions=true`, writes `.rabbit-auto-evolve-active` in order with rollback on failure; `off` reverses in inverse order |
| `scripts/fetch-queue.py` | CLI | Lists open `rabbit-managed` issues via `gh`, sorts by priority then `createdAt`, emits JSON array |
| `scripts/triage-issue.py` | CLI | Per-issue classifier; reads issue metadata and the named feature's spec front matter; emits a triage JSON object with `decision`, `reason_code`, `rationale`, `feature`, `contract_touch`, `blocked_by` |
| `scripts/plan-batch.py` | CLI | Reads a work-set JSON from stdin; partitions contract-touch issues into `barrier_first`; greedy graph-colors the rest by feature-conflict into `groups`; applies `max_parallel` cap |
| `scripts/safety-check.py` | CLI | Validates five bottom-line invariants (branch is `dev`, PR base is `dev`, head branch matches `^feat/.+`, tag does not already exist, no uncommitted modifications to tracked files); exits non-zero on any violation |
| `scripts/merge-prs.py` | CLI | Calls `safety-check.py --phase merge` then `gh pr merge --squash` (direct merge, NOT `--auto`) for each PR; refuses any PR whose base is not `dev` |
| `scripts/release-bump.py` | CLI | Reads merged PR priority label and diff scope; applies patch/minor/major semver bump per design table; creates annotated git tag and `gh release` targeting `dev` |
| `scripts/cleanup-branches.py` | CLI | Derives head branch from each merged PR; calls `safety-check.py --phase cleanup`; deletes branch locally and on origin; refuses to delete anything not matching `^feat/.+` |
| `scripts/classify-merge-restart.py` | CLI | Reads merged PR file list; classifies into `no-op`, `refresh`, or `restart` based on which path patterns appear; emits a single string on stdout |
| `scripts/update-state.py` | CLI | Reads JSON from stdin; validates against `schemas/auto-evolve-state.schema.json`; atomically writes `.rabbit/auto-evolve-state.json` via temp+rename |
| `scripts/status-report.py` | CLI | Read-only `status` backing script: reads `.rabbit/auto-evolve-state.json` (defaults on missing/empty/malformed) and the five runtime markers; emits a fixed-format status JSON on stdout |
| `scripts/run-post-merge.py` | CLI | Deterministic non-skippable runner for tick phases 7–9 (release → cleanup → catch-up): reads `pending_post_merge` from state, invokes `release-bump.py` / `cleanup-branches.py` / `classify-merge-restart.py` in order, then clears the field; clean no-op when empty (issue #499, Inv 30) |
| `scripts/install-cron.py` | CLI | Idempotently installs the `*/30` system-cron entry that fires `tick-headless.py` (the sole tick scheduler); invoked by `set-evolve-mode.py on` (issue #414, Inv 32) |
| `scripts/uninstall-cron.py` | CLI | Idempotently removes the system-cron entry; safe no-op when absent; invoked by `set-evolve-mode.py off` (issue #414, Inv 32) |
| `scripts/tick-headless.py` | CLI | The Claude-free headless tick fired by the system cron: walks phases 0–1, 2–4, 6, 7–9, 10; skips phase 5 (dispatch needs Claude); phase 11 is a no-op (issue #414, Inv 32) |

**State file (runtime artifact):**

- `.rabbit/auto-evolve-state.json` — schema version `1.0.0`; fields:
  `schema_version`, `updated_at`, `queue`, `in_flight`, `last_merged_sha`,
  `last_tagged_version`, `consecutive_failures`, `stop_requested`,
  `restart_needed`.

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

## Current behaviour

The feature directory was scaffolded in Phase B of the plan. No scripts,
no SKILL.md, and no tests exist yet. The following bullets describe the
behaviour as designed — they become verifiable once Phase C through
Phase E merges complete.

- Entering the mode via `/rabbit-config auto-evolve on` performs three
  mutations in order (flip `human-approval=false`, flip
  `bypass-permissions=true`, write `.rabbit-auto-evolve-active`) and
  requires a Claude restart before the loop can start. (design doc §2)
- After restart, the SessionStart banner emits exactly two composite lines
  replacing the individual `human-approval` and `bypass-permissions`
  alerts: a red "AUTONOMOUS-EVOLVE MODE ACTIVE" line and a yellow line
  with the literal start command to paste. (design doc §8)
- `/rabbit-auto-evolve start` verifies all three preconditions before
  launching; if any fail it refuses and explains which condition is not
  met. (design doc §3)
- Each tick walks twelve phases in sequence (stop-check, restart-check,
  fetch, triage, plan, dispatch, merge, release, cleanup, catch-up,
  persist, schedule); any phase can abort the tick without affecting the
  next tick's ability to pick up. (design doc §4)
- Triage classifies each issue using a seven-rule decision table
  (top-down, first match wins); any ambiguous case defaults to
  `defer/needs-judgment` rather than silently to `work`. (design doc §5)
- Priority is the PRIMARY dispatch-ordering key; the contract-touch
  barrier is a SECONDARY tiebreak (issue #479). Contract-touch issues
  (`feature:contract` label or body paths under
  `.claude/features/contract/`) lead the `barrier_first` queue only when
  they sort ahead of every non-contract item on priority — a critical
  non-contract item is dispatched before a low-priority contract item.
  Within a priority tier, contract-touch items precede non-contract items
  and run one at a time before that tier's parallel group. (design doc §6)
- Parallelism is bounded by `max_parallel` (default 4); same-feature
  issues are never dispatched in parallel (conflict edge = shared
  `feature:<name>` label). (design doc §6)
- When a TDD subagent's HANDOFF carries `discovered_issues`, the loop
  files each via `rabbit-issue`; when `aborted_reason` is set, the loop
  adds a `blocked-by:#N` label to the original issue and leaves it open
  for the next tick. (design doc §6)
- Merges target `dev` exclusively; `safety-check.py` aborts the merge
  phase if the current branch or PR base is not `dev`. (design doc §9)
- Each merged PR triggers a deterministic semver bump: `low`/`medium`
  priority → patch; `high`/`critical` → minor; `bump:major` directive,
  ≥ 3 features touched, or `contract/schemas` touched → major. (design
  doc §9)
- A safety violation writes `.rabbit-auto-evolve-aborted`, emits a red
  alert, and does not reschedule; the loop remains halted until the user
  clears the marker. (design doc §9)
- The catch-up phase classifies each merged PR into one of three rungs
  (no-op, `/rabbit-refresh`, restart-required); the loop handles the
  rung automatically without user intervention for the first two rungs.
  (design doc §7)
- Loop state is persisted to `.rabbit/auto-evolve-state.json` on every
  tick; a Claude restart followed by `/rabbit-auto-evolve start` resumes
  from the last persisted state without replaying completed work.
  (design doc §7)
- `/rabbit-auto-evolve stop` writes the stop marker; the loop observes it
  at the next tick's stop-check phase, posts a run summary, and does not
  call `ScheduleWakeup`. (design doc §3)
- Exiting the mode via `/rabbit-config auto-evolve off` reverses the
  three mutations in inverse order and requires another restart. (design
  doc §2)

## Invariants

1. **`set-evolve-mode.py {on|off}` compound mutator.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py
   {on|off}` performs the three mutations that compose the auto-evolve
   activation/deactivation.

   On `on`, three deterministic mutations execute in order:
   1. Write `<repo_root>/.rabbit-human-approval-bypass` (content
      `"session"`) via `contract.lib.mutation.write_marker` — flips
      `human-approval` configurable to `false`.
   2. Set `permissions.defaultMode: "bypassPermissions"` in
      `<repo_root>/.claude/settings.local.json` via
      `contract.lib.mutation.set_json_key` — flips `bypass-permissions`
      configurable to `true`.
   3. Write `<repo_root>/.rabbit-auto-evolve-active` via
      `contract.lib.mutation.write_marker` — signals auto-evolve mode
      is active (consumed by `contract.lib.runtime` Inv 64 suppression
      hook and by the runtime banner APIs in Inv 65).

   On `off`, the script performs a FULL teardown — innermost
   runtime markers first, then the three activation mutations in
   inverse order:

   1. Delete any of the four loop-runtime markers if present
      (`.rabbit-auto-evolve-running`,
      `.rabbit-auto-evolve-stop-requested`,
      `.rabbit-auto-evolve-restart-needed`,
      `.rabbit-auto-evolve-aborted`) via
      `contract.lib.mutation.delete_marker`. Idempotent
      (delete-if-exists; missing markers are no-ops). Doing this
      first means a subsequent `on` lands in a clean state.
   2. Delete `.rabbit-auto-evolve-active`.
   3. Delete the `permissions.defaultMode` key via
      `contract.lib.mutation.delete_json_key`.
   4. Delete `.rabbit-human-approval-bypass` via
      `contract.lib.mutation.delete_marker`.

   This extension was introduced by issue #371 in v0.7.1: in v0.7.0
   `off` only deleted `.rabbit-auto-evolve-active`, leaving the four
   loop-runtime markers behind for the user to clean up manually
   (which scope-guard then denied because literal `rm`/`touch` of
   non-allowlisted markers is blocked).

   Failure handling: abort on first error and roll back any prior steps
   best-effort (delete a just-written marker; restore the prior
   `permissions.defaultMode` value if step 2 had succeeded). Report the
   failed step and the rollback outcome on stderr. Exit code: 0 on full
   success; non-zero on any step failure (after rollback attempt).

   Idempotency: both `on` and `off` are clean no-ops when invoked in the
   already-target steady state (the mutation APIs in
   `contract.lib.mutation` are already idempotent for marker writes and
   JSON key sets/deletes; the script's role is only ordering and
   rollback coordination).

   **Branded confirmation on success** (per contract Inv 48 — brand
   prefix is owned by `rabbit_print`). On `on` full success, the script
   emits two lines to stdout via
   `contract.lib.runtime.rabbit_print`:

   - Line 1 — red — `🚀 AUTONOMOUS-EVOLVE MODE CONFIGURED — restart Claude Code to activate`
   - Line 2 — yellow — `👉 After restart, run: /rabbit-auto-evolve start`

   On `off` full success, the script emits a single line to stdout
   via `rabbit_print`:

   - green — `✅ Autonomous-evolve mode deactivated — full teardown complete`

   SKILL.md's `on` / `off` subcommand bodies surface the script's
   stdout verbatim to the user (no skill-generated paraphrase) — the
   message text lives in the script so it stays centralized.

   This branded confirmation was introduced by issue #377 in v0.7.4:
   in v0.7.3 the script printed a flat `set-evolve-mode: on OK` line
   and the skill paraphrased it, producing a muted message that
   didn't match the visual weight of the rest of the rabbit surface.

   Enforced by `test/test-set-evolve-mode.py` using
   `tempfile.TemporaryDirectory()` fixtures (per rabbit-config Inv 17
   isolation pattern):
   - `on` from clean state — all three side effects appear (both
     markers exist; settings.local.json has
     `permissions.defaultMode == "bypassPermissions"`).
   - `off` from on state — all three side effects revert cleanly.
   - Failure simulation at step 2 — monkey-patch
     `contract.lib.mutation.set_json_key` (or import-time inject) to
     raise; assert step 1's marker is removed during rollback; assert
     exit non-zero; assert stderr names the failed step.
   - Idempotency — `on`-from-`on` and `off`-from-`off` are clean no-ops
     (no errors, exit 0, state unchanged).
   - Branded confirmation on `on` success — stdout contains the
     literal substrings `[🐇 rabbit 🐇]`, `AUTONOMOUS-EVOLVE MODE
     CONFIGURED`, `restart Claude`, AND `/rabbit-auto-evolve start`.
   - Branded confirmation on `off` success — stdout contains the
     literal substrings `[🐇 rabbit 🐇]` AND `deactivated`.

2. **`fetch-queue.py` deterministic queue emission.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/fetch-queue.py`
   emits a deterministic JSON array on stdout, sorted by priority
   (`critical` > `high` > `medium` > `low`; issues missing a priority
   label sort to the END) then `createdAt` ascending (oldest first
   within the same priority bucket). Only issues carrying the
   `rabbit-managed` label appear (this is what gates rabbit's
   automation from human-filed issues).

   The script invokes `gh issue list --repo <repo> --state open
   --label rabbit-managed --json number,title,labels,body,createdAt
   --limit 500`, where `<repo>` is resolved via
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
     `gh` shim on `$PATH` that emits a fixture JSON list of issues
     mixing all four priorities plus a no-priority issue, with
     non-monotonic `createdAt` values inside each priority bucket.
     Invoke the script and assert: priority order
     (critical → high → medium → low → no-priority) and ascending
     `createdAt` inside each bucket.
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
     "blocked_by": [124],
     "planning_note": "<non-empty string for defer/research, else null>"
   }
   ```

   The `priority` field (issue #484) is the value of the issue's
   `priority:<level>` label (`"priority:high"` → `"high"`), or `null` when
   no `priority:` label is present. It is the PRIMARY ordering key
   `plan-batch.py` consumes for Stage-1 selection (Inv 4 / issue #479): a
   triage object that omits `priority` makes every item sort at the
   no-priority rank, silently collapsing the priority-primary ordering back
   to the contract-touch-only tiebreak. Triage therefore MUST emit
   `priority` on every record.

   The `features` field (Inv 26 / issue #435, #443) is the sorted, distinct
   set of feature directories the item touches: the union of THREE detection
   methods —
   (a) the `feature:<name>` label;
   (b) every `.claude/features/<name>/` path literally referenced in the
   issue body; and
   (c) every canonical feature name (discovered by listing
   `.claude/features/` at triage time) that appears as a whole word
   (word-boundary `\b<name>\b` match) in the issue body OR title. Method (c)
   (issue #443) catches issues that name features in prose or a markdown
   table without the full path — e.g. a body that says "touches
   rabbit-auto-evolve, rabbit-issue, rabbit-meta" yields a 3-feature set even
   though no `.claude/features/<name>/` path is written. Without (c) such an
   issue was mis-seen as single-feature and got the wrong dispatch shape.
   It is the basis `plan-batch.py` uses to choose a per-item dispatch shape
   (Stage 2). A malformed-labels issue with no body paths and no bare
   feature-name mention carries `features: []`.

   The decision set is EXACTLY `{work, defer, close-not-planned, research}`
   (issue #423 Part A; `research` added by issue #478). `close-completed`
   is NEVER emittable from triage — a
   completed closure can only be claimed once work has actually landed,
   which is the merge phase's job (Inv 6 step 4 via `item-status.py close
   --reason completed --commit-sha`), never triage's. Every `defer` and
   every `research` decision MUST carry a non-empty `planning_note`
   describing what analysis would unblock dispatch (for `defer`) or what
   should be investigated and reported (for `research`); the `work` and
   `close-not-planned` decisions carry `planning_note: null`.

   ### Research/investigation classification (issue #478)

   A research/spike/investigation item ("study X", "evaluate Y", "survey
   Z", "assess the tradeoffs", "recommend an approach", "compare A and B",
   "explore N") asks for FINDINGS or a RECOMMENDATION, not a behavior
   change. The loop's only code-producing execution shape is a TDD-cycle
   PR; before issue #478 such items had no home, so they were wrongly
   closed `not-planned` — a valid issue silently dropped, in violation of
   Inv 25 (convergence). Triage now classifies them as
   `decision=research` so the loop can route them to the research dispatch
   shape (Inv 27) instead.

   Research classification runs AFTER rule 7 would otherwise return `work`
   (alongside the #463 reconciliation) — it NEVER overrides a
   `close-not-planned` / `blocked` / `malformed-labels` verdict (those are
   structural facts, not intent wording). Detection signals (ALL of the
   following must hold, so a normal "implement X" item is never
   misrouted):

   1. **Research verb present.** The title OR body contains a
      research/investigation verb (case-insensitive whole-word match):
      `study`, `evaluate`, `investigate`, `survey`, `assess`,
      `recommend`, `compare`, `explore`.
   2. **No concrete code-change target.** The body declares no concrete
      code-change target — no `.claude/features/<name>/` path reference
      beyond the labelled feature dir, and no imperative implement/fix/add
      phrasing pointing at a behavior change.
   3. **Findings/recommendation requested.** The body asks for a
      recommendation, findings, a report, an analysis, or an evaluation
      rather than a behavior change.

   When all three hold, triage emits `decision=research`,
   `reason_code=research`, and a non-empty `planning_note` summarizing what
   to investigate. A research item is NEVER `close-not-planned` (it is a
   valid issue) and NEVER `work`/`dispatch` (it produces findings, not
   code).

   The script reads only:
   - Issue metadata (title, body, labels, state, state reason, and the
     full comment thread) via `gh issue view <N> --repo <repo> --json
     number,title,body,labels,state,stateReason,comments`. The `comments`
     array (`[{body, createdAt, author}, …]`, chronological order, oldest
     first) and `stateReason` (e.g. `"reopened"`) are read so triage can
     reconcile a correction comment that supersedes the original body
     (see "Comment-thread reconciliation" below).
   - The named feature's spec head matter (YAML frontmatter and the
     first markdown section only) — for rule 6. The path is resolved
     dual-read (issue #399): the new `specs/spec.md` layout is preferred,
     with the legacy `docs/spec/spec.md` accepted as a fallback during the
     coexistence window.
   - The named feature's `feature.json` (for rule 4 — `status` field).
   - The list of closed issues in the last 30 days (for rule 3) via
     `gh issue list --state closed --search "closed:>=<date>"`.

   It MUST NOT read the codebase at large; it MUST NOT read any spec
   file outside the named feature's head matter.

   Repo discovery uses `rabbit_issue._gh.repo_slug` (same pattern as
   `fetch-queue.py`). No filesystem mutations.

   Decision rules (evaluated top-down, first match wins):

   | Rule | Condition | decision | reason_code |
   |---|---|---|---|
   | 1 | Issue lacks `feature:<name>` OR `priority:<level>` label | `defer` | `malformed-labels` |
   | 2 | Feature named by label does not exist at `.claude/features/<name>/` | `close-not-planned` | `unknown-feature` |
   | 3 | Issue title is a case-folded substring match of a closed-in-last-30-days issue's title | `close-not-planned` | `duplicate` |
   | 4 | Feature's `feature.json.status == "retired"` | `close-not-planned` | `feature-retired` |
   | 5 | Issue body declares `blocked-by: #N` AND any cited `#N` is still open | `defer` (set `blocked_by`) | `blocked` |
   | 6 | Feature's spec head matter already documents the requested behavior verbatim (case-folded substring match of the issue title's content-word tail) | `close-not-planned` | `already-spec'd` |
   | 7 | Otherwise actionable; refined by research classification (issue #478) and #463 comment-thread reconciliation | `work` / `research` / `defer` | `actionable` / `research` / `needs-judgment` |

   `contract_touch` is `true` iff the issue carries a
   `feature:contract` label OR the body literally declares any path
   under `.claude/features/contract/`.

   **Ambiguity default:** Any case the seven rules cannot resolve
   (e.g. malformed `blocked-by` syntax, unparsable spec head matter,
   `gh` returning a payload missing expected fields) defaults to
   `decision=defer`, `reason_code=needs-judgment`. The triage MUST
   NEVER fall through silently to `work`; the loop under-dispatches
   rather than over-dispatches.

   ### Comment-thread reconciliation (issue #463)

   Triage MUST read the FULL comment thread, not just the issue body. An
   issue's body is frozen at filing time; a maintainer who later realizes
   the original framing was wrong corrects it in a comment (and often
   reopens or retitles the issue). Reading only the body makes the loop
   implement the stale original design — the canonical incident is #399,
   where the body said "rename `docs/spec/` → `specs/`" but a later
   correction comment and a retitle said the correct target was `docs/`
   with a CHANGELOG; the loop read only the body and shipped 13 PRs of
   wrong work.

   Reconciliation runs AFTER rule 7 would otherwise return `work` — it
   never overrides a `close-not-planned` / `blocked` / `malformed-labels`
   verdict (those are determined by structural facts, not by intent
   wording). It refines an actionable issue's verdict between `work` and
   `defer`:

   1. **Detection signals** (any one triggers reconciliation analysis):
      - The issue carries at least one comment AND
        `stateReason == "reopened"` (case-insensitive) — a STRONG signal;
        always reconcile.
      - Any comment body contains supersession language
        (case-insensitive substring match against: `supersedes`,
        `correction`, `corrected proposal`, `ignore the original`,
        `revised scope`, `original body was wrong`) — treat that comment
        as an authoritative correction.
      - The title and body describe DIFFERENT targets — detected as a
        conflict when the title contains a path/target token (e.g. a
        `docs/...` or `specs/...` path, or text after a `→`/`->` arrow)
        that does NOT appear in the body, while the body declares its own
        distinct path/target token. This is a title-vs-body conflict.

   2. **Resolution:**
      - When a correction comment (supersession language) is present and
        its corrected intent is coherent, treat the MOST RECENT coherent
        intent as authoritative: emit `decision=work`,
        `reason_code=actionable`, and the `rationale` MUST note that a
        correction was applied (literal substring `correction` in the
        rationale) and name the superseding source.
      - When the title and body conflict on the target and the latest
        signal (title or correction comment) yields a single coherent
        target, the latest/title wins: emit `decision=work` with the
        `rationale` noting the conflict and which side won.
      - When body and comments (or title and body) conflict and the
        correct target is genuinely AMBIGUOUS (no single coherent latest
        intent), emit `decision=defer`, `reason_code=needs-judgment`,
        with `planning_note` of the form `"Body and correction comment
        conflict on target [X vs Y]; need maintainer clarification before
        dispatch."` (the bracketed `[X vs Y]` names the two conflicting
        targets).

   3. **No-signal pass-through:** an actionable issue with no comments and
      no title/body conflict reconciles to exactly the pre-#463 behavior —
      `decision=work`, `reason_code=actionable`, no correction noted. This
      is a strict no-regression requirement.

   Exit code: 0 on successful classification (any decision); non-zero
   on `gh` failure or other unexpected error (stderr passthrough).

   Enforced by `test/test-triage-rules.py`:
   - One unit test per row of the decision table (7 rules), each
     using a fixture JSON payload under
     `test/fixtures/triage/` that captures the `gh issue view --json`
     output for the scenario.
   - A `gh` shim on `$PATH` under `tempfile.TemporaryDirectory()`
     serves fixture responses for both `gh issue view` and
     `gh issue list` (rule 3 lookup); no live network.
   - An additional `needs-judgment` test exercising an ambiguity case
     (e.g. body declares `blocked-by:` without an integer reference).
   - Comment-thread reconciliation (issue #463), each via a `gh` shim
     whose `gh issue view` payload carries a populated `comments` array
     and `stateReason`:
     - Correction comment present (supersession language) → `decision=work`,
       `reason_code=actionable`, and the `rationale` notes a correction
       was applied (substring `correction`).
     - Reopened issue (`stateReason == "reopened"`) whose retitle conflicts
       with the body on the target, ambiguous → `decision=defer`,
       `reason_code=needs-judgment`, `planning_note` names both conflicting
       targets.
     - No comments and no title/body conflict → unchanged pre-#463
       behavior (`decision=work`, `reason_code=actionable`, no correction
       noted) — the no-regression guard.
   - Research classification (issue #478):
     - A "study X" / "evaluate Y" issue body asking for findings, with no
       concrete code-change target → `decision=research`,
       `reason_code=research`, non-empty `planning_note`, and NEVER
       `close-not-planned`.
     - A normal "implement X" actionable issue (no research verb) →
       unchanged `decision=work` (the research path must not over-trigger).
   - Smoke test: invoke with `--help`; assert exit 0 and recognizable
     usage text.

4. **`plan-batch.py` conflict-graph + barrier dispatch planner.** The CLI
   `cat triage.json | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py [--max-parallel N]`
   reads a JSON array of triage objects on stdin and emits a
   deterministic dispatch plan to stdout. Items whose `decision` is
   neither `"work"` nor `"research"` are silently dropped
   (`close-not-planned`, `defer`, etc.) — the caller MAY pass a
   pre-filtered work-only array OR the full unfiltered triage output of
   `triage-batch.py` (per Inv 18 the standard pipe is
   `fetch-queue | triage-batch | plan-batch`). `research` items (issue
   #478) are retained: they appear in `selection_order` and carry a
   `dispatch_shapes` entry of `"research"`, and their issue numbers are
   listed under the `research_items` key — but they NEVER enter
   `barrier_first` or `groups` (they produce findings, not code, so the
   conflict-graph parallel-dispatch grouping does not apply to them).

   ```json
   {
     "selection_order": [124, 125, 123, 130],
     "dispatch_shapes": {"124": "parallel-per-feature", "125": "multi-subagent-barrier", "123": "decomposition", "130": "research"},
     "barrier_first": [123, 124],
     "groups": [[125, 126], [127]],
     "research_items": [130]
   }
   ```

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

   `--max-parallel N` (positional flag, default 4) is the canonical
   surface for the cap (resolved Open Question 1). The flag MUST be
   integer-valued and ≥ 1; non-integer or `< 1` exits non-zero with
   argparse error.

   Algorithm (priority-primary, barrier-secondary; issue #479):

   **Priority is the PRIMARY ordering key; the contract-touch barrier is
   the SECONDARY tiebreak, never a global override of priority.** A
   critical non-contract item is dispatched BEFORE a low-priority
   contract-touch item; the barrier only sequences contract-touch items
   ahead of non-contract items _within the same priority tier_.

   1. **Sort ALL work items by the composite key**
      `(priority_rank, contract_touch_rank, issue)`:
      - `priority_rank`: critical=0, high=1, medium=2, low=3,
        missing/unrecognized=4 (lower rank = higher priority).
      - `contract_touch_rank`: `True`->0, `False`->1 (contract-touch
        items lead within the same priority tier).
      - `issue` ascending (stable final tiebreak).
   2. **`barrier_first` is the leading run of contract-touch items** in
      that sorted order — i.e. the contract-touch items that appear
      before the first non-contract item. If the highest-priority item is
      a non-contract item, `barrier_first` is EMPTY. The remainder
      (everything from the first non-contract item onward, in the same
      sorted order) feeds the conflict-graph grouping.
   3. **Build a conflict graph on the remainder.** Nodes are issues; an
      edge exists between A and B iff `A.feature == B.feature`.
   4. **Greedy graph coloring.** Walk the remainder in the composite-key
      order and assign each issue the lowest-numbered color (group index)
      that has no neighbor already in it. `groups` is the color
      partition, in color order.
   5. **Apply `--max-parallel` cap.** Any group whose size exceeds the
      cap is split into sub-groups of size ≤ cap. Sub-groups appear as
      separate consecutive entries in the output `groups` list
      (parallel-safe within each sub-group; the loop processes
      sub-groups sequentially).

   `selection_order` (Stage 1) and `barrier_first` (Stage 2) agree on
   ordering: both are derived from priority-desc ranking, so a
   contract-touch item never leads `barrier_first` unless it also leads
   `selection_order`.

   **Research items (issue #478).** A `decision == "research"` item is the
   4th dispatch shape. It is included in `selection_order` (sorted by the
   same composite key) and gets a `dispatch_shapes[issue] = "research"`
   entry, and its issue number is listed under `research_items` (sorted
   ascending). It is EXCLUDED from `barrier_first` and from the
   conflict-graph `groups` partition: research produces findings, not code,
   so the same-feature conflict edges and the contract-touch barrier do not
   apply. The output always carries a `research_items` key (an empty list
   when no research items are present).

   Exit code: 0 on success; non-zero on malformed stdin JSON or
   invalid `--max-parallel` value.

   Enforced by `test/test-plan-batch.py`:
   - Contract-only set (3 items, all `contract_touch: true`,
     non-monotonic priorities) → all in `barrier_first`, sorted
     correctly; `groups == []`.
   - Same-feature set (3 items, same `feature`, no contract) → exactly
     3 groups, each containing one item (graph coloring forces no
     sharing).
   - Mixed-feature set (3 items, all distinct features, no contract)
     → exactly 1 group containing all 3.
   - Over-cap set (8 distinct-feature non-contract items with
     `--max-parallel 3`) → split into sub-groups of size ≤ 3 (e.g.
     `[3, 3, 2]`).
   - Priority-over-barrier (issue #479): a `critical` non-contract item
     plus a `low` contract-touch item → the critical item leads
     `selection_order`; `barrier_first` is EMPTY (the low contract item
     does NOT jump ahead of the critical item).
   - Same-tier barrier tiebreak: a contract-touch item and a
     non-contract item both at `high` priority → the contract item
     precedes the non-contract item; `barrier_first` holds the contract
     item.
   - Research item (issue #478): a batch with a `decision: "research"`
     item plus a `decision: "work"` item → the research issue appears in
     `selection_order` with `dispatch_shapes[N] == "research"` and `N` in
     `research_items`, and is absent from `barrier_first` and `groups`; the
     work item is unaffected (its shape + grouping unchanged).
   - `--help` smoke: exit 0 with recognizable usage text.

5. **`safety-check.py` five bottom-line invariants.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/safety-check.py <pr#> --phase {merge|release|cleanup} [--next-tag vX.Y.Z]`
   enforces the bottom-line safety invariants from design doc §9
   before any merge / release / cleanup action runs.

   **Per resolved Open Question 2: the next tag is passed via the
   `--next-tag vX.Y.Z` flag, NOT via env var.** The flag is REQUIRED
   iff `--phase release` and FORBIDDEN for `--phase merge|cleanup`.

   Five invariants (numbered for stable cross-reference):

   | # | Invariant | Enforced in phases |
   |---|---|---|
   | 1 | Current git branch is `dev` (never `main`) | all |
   | 2 | PR base branch (via `gh pr view <#> --json baseRefName`) is `dev` | merge, release |
   | 3 | PR head branch (via `gh pr view <#> --json headRefName`) matches `^feat/.+` AND is not `dev`, `main`, or `release/...` | cleanup |
   | 4 | The tag passed via `--next-tag vX.Y.Z` does not already exist (`git rev-parse <tag>^{}` exits non-zero) | release |
   | 5 | No uncommitted modifications to tracked files — both `git diff --quiet` (unstaged) and `git diff --cached --quiet` (staged) exit 0. Untracked files (`??`) are intentionally ignored: they cannot affect a merge, and counting them deadlocked the loop whenever a new runtime artifact appeared (issue #397). | all |

   Phase-specific gating:
   - `merge` enforces invariants 1, 2, 5.
   - `release` enforces invariants 1, 2, 4, 5.
   - `cleanup` enforces invariants 1, 3, 5.

   Exit code: 0 on pass; non-zero on any violation. On violation, the
   stderr line names the violated invariant (`Invariant N (<short>)
   failed: <detail>`); the script never auto-fixes.

   The script reads `gh` and `git` state only — no filesystem mutations.

   Enforced by `test/test-safety-check.py` under
   `tempfile.TemporaryDirectory()` fixtures:
   - One negative test per invariant: violate each in isolation
     (wrong branch / wrong PR base / non-feat head / pre-existing
     tag / tracked-file modification) under the appropriate phase →
     non-zero exit; stderr names the violated invariant.
   - Inv 5 tracked-vs-untracked discrimination (issue #397): an
     untracked file in the working tree PASSES Inv 5; a tracked file
     with an unstaged modification FAILS; a tracked file with a
     staged modification FAILS; a clean tree PASSES.
   - One positive test per phase: all required invariants satisfied
     → exit 0.
   - `--next-tag` required-when-release: omitting it under
     `--phase release` → argparse error, non-zero.
   - `--next-tag` forbidden-elsewhere: passing it under
     `--phase merge` (or `cleanup`) → non-zero error.
   - `--help` smoke: exit 0 with recognizable usage text.
   - Test fixtures use a real `git init` in a tempdir plus a `gh`
     shim on `$PATH` to serve PR base/head responses; no live network.

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
      If base ≠ `dev` → record
      `{pr: N, status: "skipped", reason: "base-not-dev"}` and continue.
   2. Invoke `safety-check.py <pr#> --phase merge`. If non-zero exit →
      record `{pr: N, status: "skipped", reason: "safety-check-failed"}`.
   3. Otherwise call `gh pr merge <#> --squash` — a DIRECT squash merge,
      NOT `--auto`. The `--auto` flag requires the repo to have auto-merge
      enabled (`enablePullRequestAutoMerge`); on a repo without it,
      `gh pr merge --auto` fails for any PR that is not immediately
      mergeable with `Auto merge is not allowed for this repository`
      (issue #429). Mergeability is already gated by the base==dev refusal
      (step 1) plus `safety-check.py` (step 2), so a direct merge is
      correct and never depends on the repo's auto-merge setting. On
      success → `{pr: N, status: "merged"}`; on failure →
      `{pr: N, status: "failed", reason: "gh-merge-failed: <stderr>"}`.
   4. After a successful merge, parse the merged PR body
      (`gh pr view <#> --json body -q .body`) for closing-keyword
      references — `Fixes #N` / `Closes #N` / `Resolves #N` and their
      common variants (`Fixed`, `Closed`, `Resolved`, `Close`, `Fix`,
      `Resolve`), case-insensitive. For each distinct referenced issue,
      fetch the merge SHA (`gh pr view <#> --json mergeCommit
      -q .mergeCommit.oid`) and invoke
      `item-status.py close <N> --reason completed --commit-sha <sha>
      --comment "TDD cycle complete in <sha>"`. The `--commit-sha` flag is
      REQUIRED by `item-status.py` for a `completed` closure (issue #423
      Part C) — a completed closure must point at the real merge commit
      that landed the work. This is required because
      GitHub's native `Fixes/Closes/Resolves` auto-close fires ONLY when
      a PR merges to the repo's default branch (`main`); auto-evolve PRs
      always target `dev`, so without this explicit step referenced
      issues would stay open indefinitely. `item-status.py close` is
      idempotent against already-closed issues, so it is called
      unconditionally. Successfully-closed issue numbers are added to the
      result row under `closed_issues` (sorted); issues whose close
      command exited non-zero are recorded under `close_failed` and a
      warning is written to stderr. A close failure NEVER fails the
      merge — the result still reports `status: "merged"`
      (backward-compatible). `item-status.py` is resolved via the
      `RABBIT_ISSUE_SCRIPT_DIR` env var when set, else relative to the
      repo's `.claude/features/rabbit-issue/scripts/`.

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

   `merge-prs.py` will NEVER call `gh pr merge` on a PR whose base is
   not `dev`. `cleanup-branches.py` will NEVER call any deletion
   command for a branch not matching `^feat/.+`. These refusals are
   defense-in-depth above `safety-check.py` — even if `safety-check.py`
   were skipped or compromised, the local refusal check still gates
   destructive actions.

   ### Tests

   `test/test-merge-prs.py`:
   - Smoke: `--help` exits 0 with recognizable usage text.
   - Skip-on-non-dev-base: gh shim returns `baseRefName=main` →
     `status: "skipped"`, `reason: "base-not-dev"`; `gh pr merge` is
     NEVER called (verifiable via shim call log).
   - Skip-on-safety-fail: gh shim returns `dev` for base, safety-check
     shim exits non-zero → `status: "skipped"`,
     `reason: "safety-check-failed"`; `gh pr merge` NEVER called.
   - Happy path: shims pass → `status: "merged"`; exit 0.
   - No-`--auto` regression (issue #429): on the happy path, the recorded
     `gh pr merge` invocation MUST NOT contain `--auto` (it still uses
     `--squash`). Guards against the auto-merge-not-enabled failure.
   - Close-after-merge (issue #392 + #423): PR body references issues via
     `Fixes`/`Closes`/`Resolves` (case-insensitive) → after a successful
     merge, the item-status.py shim is invoked once per distinct issue
     with `close <N> --reason completed --commit-sha <merge-sha>
     --comment "...<sha>..."`; the
     result row carries `closed_issues`. No refs → item-status.py NOT
     invoked, `closed_issues == []`. item-status.py failure → merge still
     `status: "merged"`, failed issue under `close_failed`, stderr
     warning emitted. Skipped/non-merged PRs NEVER invoke item-status.py.

   `test/test-cleanup-branches.py`:
   - Smoke: `--help` exits 0 with recognizable usage text.
   - Skip-on-non-feat-branch: gh shim returns `headRefName=main` →
     `status: "skipped"`, `reason: "non-feat-branch"`; stderr warning
     emitted; deletion commands NEVER called.
   - Happy path: shims return `feat/xyz`, safety-check passes →
     `status: "deleted"`; exit 0.

   Both test suites use `tempfile.TemporaryDirectory()` + `git init`
   + a combined `gh`/`safety-check.py` shim on `$PATH` to dispatch on
   subcommand+args; no live network.

7. **`release-bump.py` priority-to-semver bumper.** The CLI
   `python3 .claude/features/rabbit-auto-evolve/scripts/release-bump.py <pr#> [--features-threshold N]`
   reads the merged PR's labels, body, and changed-file list, applies
   the design-doc §9 bump table, runs `safety-check.py` under
   `--phase release --next-tag vX.Y.Z` BEFORE any git operation (per
   resolved Open Question 2), then creates and pushes the annotated
   tag and a GitHub release targeting `dev`.

   `--features-threshold N` (default 3) configures the
   distinct-features-touched threshold for the major-bump rule.

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

   Execution order:
   1. `gh pr view <#> --json number,title,labels,body,files` → fetch
      metadata + changed-file list.
   2. Apply bump table → determine the bump kind.
   3. `git describe --tags --abbrev=0` → `prior_tag`. When the repository
      has zero tags (the first-release case) `git describe` exits
      non-zero; this is NOT an error. In that case `prior_tag` is `null`
      and `next_tag` is the fixed first-release version `v1.0.0`
      regardless of the bump kind (the bump table only governs how an
      EXISTING version is incremented). When a `prior_tag` exists,
      compute `next_tag = vX.Y.Z` by applying the bump kind to it.
   4. `safety-check.py <pr#> --phase release --next-tag <next_tag>`.
      Non-zero → emit `{status: "skipped", reason: "safety-check-failed"}`
      and stop (no git mutation, exit 0).
   5. `git tag -a <next_tag> -m "<auto-evolve> #<pr> <title>"`.
   6. `git push origin <next_tag>`.
   7. `gh release create <next_tag> --notes-from-tag --target dev`.

   First release (zero prior tags): `prior_tag` is `null`, `next_tag` is
   `v1.0.0`. This is what lets the auto-evolve loop cut its very first
   release after a successful Phase 6 merge instead of crashing on a
   tag-free `git describe` (issue #400).

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

   Enforced by `test/test-release-bump.py`:
   - One test per bump-table row (5 cases): each fixture exercises
     exactly one trigger; assert `bump` and `trigger` fields match.
   - Safety-check fail: shim safety-check exits non-zero → result
     `{status: "skipped", reason: "safety-check-failed"}`; verify NO
     `git tag` invocation occurred (via shim call log).
   - `--features-threshold 5` override: 4 distinct features touched
     (no other major trigger) → bumps minor, not major.
   - First release (zero prior tags, issue #400): the `git` shim makes
     `git describe --tags --abbrev=0` exit non-zero (tag-free repo). The
     script must NOT crash; it emits `prior_tag: null`, `next_tag:
     "v1.0.0"`, `status: "released"`, and invokes `git tag` for
     `v1.0.0`. Covered for `priority:high` (would-be minor),
     `priority:critical` (would-be major), and `priority:low` (would-be
     patch) — in every case the first tag is `v1.0.0`.
   - `--help` smoke: exit 0 with recognizable usage text.

   Tests use the same `tempfile.TemporaryDirectory()` + `git init` +
   combined `gh`/`git`/`safety-check.py` shim pattern as
   `test-merge-prs.py` and `test-cleanup-branches.py`.

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
   | `restart` | (a) any path containing `settings.json`, OR (b) a brand-new file under `.claude/skills/*/SKILL.md` (additions > 0 AND deletions == 0 — i.e. pure-add), OR (c) any path matching `.claude/hooks/*.py` |
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

   Enforced by `test/test-classify-merge-restart.py`:
   - `restart` from a `settings.json` touch.
   - `restart` from a brand-new `.claude/skills/foo/SKILL.md` add.
   - `restart` from a `.claude/hooks/bar.py` modification.
   - `refresh` from `.claude/features/policy/coding-rules.md`.
   - `refresh` from `CLAUDE.md` touch.
   - `no-op` from an arbitrary
     `.claude/features/<other-feature>/scripts/x.py` touch.
   - Precedence: `settings.json` + a policy file change → `restart`
     (not `refresh`).
   - `--help` smoke: exit 0 with recognizable usage text.

   Tests use `tempfile.TemporaryDirectory()` + a `gh` shim on
   `$PATH` that serves fixture file-list JSON; no live network.

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
   | `schema_version` | string | Literal `"1.2.0"` |
   | `updated_at` | string | ISO 8601 UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ` |
   | `queue` | array of objects | each `{issue: int, decision: string, feature: string}` |
   | `in_flight` | array of int | currently-dispatched issue numbers |
   | `last_merged_sha` | string \| null | last PR merge commit SHA |
   | `last_tagged_version` | string \| null | last release tag (e.g. `"v0.5.3"`) |
   | `consecutive_failures` | int | ≥ 0 |
   | `stop_requested` | bool | stop marker observed |
   | `restart_needed` | string \| null | reason string when set, else null (resolved Open Question 3 — NOT a pure boolean) |
   | `defer_counts` | object (optional) | per-issue consecutive-defer counter (issue #423 Part B), keyed by issue-number string → non-negative int. Additive in schema 1.1.0; absent in pre-1.1.0 states |
   | `pending_post_merge` | array of int (optional) | merged PR numbers owed post-merge processing (phases 7–9, issue #499). Additive in schema 1.2.0; absent in pre-1.2.0 states. See Inv 30 |

   The schema file itself carries top-level `schema_version`, `owner`,
   and `deprecation_criterion` keys per spec-rules §3. Schema 1.1.0 added
   the optional `defer_counts` field (issue #423 Part B) — a backward-
   compatible additive change: states written without `defer_counts` still
   validate. Schema 1.2.0 adds the optional `pending_post_merge` field
   (issue #499) — likewise backward-compatible additive: states written
   without it still validate.

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

   ### `restart_needed` typing rule (resolved Open Question 3)

   `restart_needed` is `string | null`. The string carries the
   restart reason (e.g. `"settings.json change"`, `"new skill: foo"`).
   Pure boolean is REJECTED by the schema — booleans get type-error
   responses. `null` indicates no restart is needed.

   Enforced by `test/test-state-persistence.py`:
   - Round-trip: pipe a fully-populated valid state object →
     update-state.py → read back the written file → assert
     field-by-field equality.
   - Missing-required-field: for each required field, omit it and
     assert non-zero exit + stderr names the field; assert the file
     was NOT created.
   - `restart_needed` typing: accept `null`, accept
     `"some reason"`; reject `true` (boolean), reject `42` (int) —
     each rejection non-zero with type-mismatch detail in stderr.
   - Atomicity: pre-create a stale
     `.rabbit/auto-evolve-state.json`; update with new content; read
     back; assert content equals new (no partial write, no merge).
   - `--help` smoke: exit 0 with recognizable usage text.

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

      The auto-on routing on fresh state was introduced by issue
      #386 in v0.7.7: in v0.7.6 the skill fragmented a single user
      intent ("enter auto-evolve mode") into a two-step manual flow
      by surfacing the precondition checklist verbatim.
    - `stop` — invokes `scripts/stop-loop.py` (which writes
      `.rabbit-auto-evolve-stop-requested`); the next tick observes
      and does NOT call `ScheduleWakeup`.
    - `status` — read-only: queue length, in-flight set, last-merged
      PR, last-tagged version, consecutive-failure count, restart
      marker (if any).
    - `tick` — internal subcommand; walks the 12 phases (0–11) from
      design doc §4 in order, naming every script invoked
      (`set-evolve-mode.py`, `fetch-queue.py`, `triage-issue.py`,
      `plan-batch.py`, `safety-check.py`, `merge-prs.py`,
      `release-bump.py`, `cleanup-branches.py`,
      `classify-merge-restart.py`, `update-state.py`) and the
      disk-state path (`.rabbit/auto-evolve-state.json`).
    - `off` — invokes `scripts/set-evolve-mode.py off` to reverse
      the three mutations cleanly (delete
      `.rabbit-auto-evolve-active`, delete `permissions.defaultMode`,
      delete `.rabbit-human-approval-bypass`).

    The SKILL.md also describes the in-loop discovery handling per
    design §6: when a TDD subagent's HANDOFF carries
    `discovered_issues`, file each via `rabbit-issue`; when
    `aborted_reason` is set, label `blocked-by:#N` on the original
    issue and leave it open.

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
    `prompt-injection failures: <feature>` line. This was bug #364
    in v0.5.1; fixed in v0.5.2.

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

13. **In-loop AskUserQuestion ban (Red Flag — per issue #337).**
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
    real `contract.lib.runtime` APIs (which landed in PR #332 /
    contract Inv 65) by importing them as a module — no shell
    invocations of the dispatchers.

    **Ownership migration (in progress).** Inv 22 (added v0.7.5)
    introduces `scripts/banner-status.py` which owns the line-2 text
    variants going forward — including the new `running` variant
    that this invariant does NOT yet cover. The user-visible banner
    behavior remains governed by this invariant (3 variants) until
    a follow-up cycle against the `contract` feature refactors
    `emit_auto_evolve_banner` to call `banner-status.py`. After that
    contract cycle merges, this invariant will be revised to defer
    line-2 ownership to Inv 22.

15. **Feature-shape compliance.** All four version fields agree:
    `feature.json.version` == spec.md frontmatter `version` ==
    contract.md frontmatter `version` == SKILL.md frontmatter
    `version`. The current target is `0.4.0` (set during Phase E
    Task 14; bumped on every subsequent compliance landing).

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

    This invariant was introduced by issue #362: in v0.5.0 the
    `on`/`off` sections used bare `scripts/set-evolve-mode.py`,
    causing file-not-found errors on first user invocation. v0.5.1
    fixes every reference to use the full feature-relative path.

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

    SKILL.md MUST NOT instruct Claude to literally `touch` or
    `echo > <marker>`. Scope-guard inspects the Bash command string
    and would deny such writes because the markers are not on its
    allowlist. Routing through a `python3 <script>.py` invocation
    hides the marker write inside the Python process, which
    scope-guard cannot inspect — this is the same pattern that
    `set-evolve-mode.py` already uses for `.rabbit-auto-evolve-active`.

    This invariant was introduced by issue #367: in v0.5.2 the
    `start` subcommand's SKILL.md text included a literal
    `touch .rabbit-auto-evolve-running` Bash example, which
    scope-guard correctly denied on first invocation. v0.6.0 adds
    the four wrapping scripts (`start-loop.py`, `stop-loop.py`,
    `mark-restart-needed.py`, `mark-aborted.py`) and updates
    SKILL.md to invoke them.

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

    Failure semantics: if any per-issue `triage-issue.py` invocation
    exits non-zero, the failed issue gets a synthesized triage object
    `{issue: N, decision: "defer", reason_code: "triage-failed",
    rationale: "<stderr snippet>", feature: null, contract_touch: false,
    blocked_by: []}` and the batch CONTINUES processing remaining
    issues. The script never aborts mid-batch on a single-issue
    failure — graceful degradation matters for tick liveness.

    Exit code: 0 on success (including with per-issue failures
    handled as defer entries); non-zero on malformed stdin JSON.

    `triage-batch.py` uses the same `RABBIT_AUTO_EVOLVE_SCRIPT_DIR`
    env override pattern as the marker scripts to locate
    `triage-issue.py` (test seam).

    **Anti-infinite-defer counter (issue #423 Part B).**
    `triage-batch.py` owns a per-issue consecutive-defer counter
    persisted in `.rabbit/auto-evolve-state.json` under the
    `defer_counts` map (keyed by issue-number string; state dir
    resolved via `RABBIT_AUTO_EVOLVE_STATE_DIR`, matching
    `update-state.py`). For each triaged issue:

    - a `defer` decision INCREMENTS the issue's counter; if the
      counter was already ≥ 3 (this would be the 4th consecutive
      defer), the decision is FORCED to `work` with `reason_code:
      defer-limit-reached`, the accumulated planning-note history is
      surfaced in `planning_note`, and the counter resets to 0 —
      dispatch is mandatory after 3 consecutive deferrals.
    - any non-`defer` decision RESETS the issue's counter to 0 (the
      counter tracks CONSECUTIVE defers, not lifetime).

    The updated `defer_counts` map is written back via an atomic
    temp+rename (read-modify-write, preserving every other state
    key). Persistence is best-effort: if no state file exists or it
    fails to parse, counts default to empty and decisions pass
    through unchanged — tick liveness must never depend on the state
    file already existing. This enforces the convergence guarantee in
    Inv 25.

    The canonical tick pipe in SKILL.md phases 2–4:

    ```
    python3 .claude/features/rabbit-auto-evolve/scripts/fetch-queue.py \
      | python3 .claude/features/rabbit-auto-evolve/scripts/triage-batch.py \
      | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py --max-parallel 4
    ```

    `plan-batch.py` silently drops items with `decision != "work"`
    (per Inv 4 update) so the unfiltered triage array passes through
    cleanly.

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
    - Defer counter (issue #423 Part B): a shim that always defers
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

19. **`start-loop.py` self-healing.** Before writing the
    `.rabbit-auto-evolve-running` marker, `start-loop.py` performs
    two self-healing steps:

    1. **Cancel any pending stop.** If
       `.rabbit-auto-evolve-stop-requested` exists at the repo
       root, delete it. Rationale: invoking `start` is an explicit
       "I want this to run" signal — it cancels any pending stop
       (typical scenario: previous session was killed mid-tick,
       leaving the stop marker behind from a `stop` invocation that
       was never observed by a subsequent tick).
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

    This invariant was introduced by issue #373 in v0.7.2: in v0.7.1
    `start-loop.py` only wrote the running marker; the tick then
    aborted at phase 0 because of a stale stop marker, and the
    state-read crashed with a parse error on the missing file.

    Enforced by `test/test-loop-markers.py`:
    - Pre-seed `.rabbit-auto-evolve-stop-requested`, invoke
      `start-loop.py`, assert: running marker exists AND
      stop-requested marker is gone.
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

    `end-tick.py` deletes `.rabbit-auto-evolve-running` (mirror of
    `start-loop.py`'s write). Idempotent: missing marker is a
    no-op. Without this, the running marker leaks across sessions
    and the user has to `rm -f` it manually — which scope-guard
    correctly denies.

    SKILL.md's tick documentation MUST show the `end-tick.py`
    invocation in EVERY documented exit path, not only the
    happy-path final phase.

    This invariant was introduced by issue #373 in v0.7.2.

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

    This invariant was introduced by issue #375 in v0.7.3.

    The three check IDs are stable identifiers (`active-marker`,
    `approval-bypass`, `bypass-permissions`). Callers may rely on
    their presence and order in the `checks` array.

    **Dual-read of the bypass marker (issue #336 Phase 1
    coexistence window).** The `approval-bypass` check is satisfied
    when EITHER the legacy `.rabbit-human-approval-bypass` OR the
    new `.rabbit-tdd-autonomous` marker is present at the repo root
    (OR logic — if either exists the check passes). Issue #336
    renames the `human-approval` configurable to `tdd-autonomous`
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
    | none | `paste: /rabbit-auto-evolve start` | ▶ | yellow |

    Marker contents (for aborted/restart-needed) MAY be concatenated
    into the text for surfacing the reason, but the substring listed
    above is always present.

    The script reads markers via `os.path.exists` only — no other
    filesystem access, no git, no `gh`. Repo root resolution uses
    the `RABBIT_AUTO_EVOLVE_REPO_ROOT` env override fallback to
    `os.getcwd()` (matching the marker-write scripts).

    **Ownership migration:** As of v0.7.5 the line-2 text variants
    are owned by this script. The current `contract.lib.runtime`
    `emit_auto_evolve_banner` implementation still inlines the
    three pre-existing variants (aborted / restart-needed / default)
    and does NOT yet call this script — a follow-up cycle against
    the `contract` feature will refactor it to invoke
    `banner-status.py` instead. Until that follow-up lands, the
    `running` variant exists in this script but is NOT surfaced at
    SessionStart. Inv 14 remains the source of truth for the
    user-visible banner's current 3-variant behaviour until the
    contract refactor merges.

    Enforced by `test/test-banner-status.py`:
    - Active marker absent → `{active: false, line1: null, line2: null}`.
    - Active only → `line2.text` contains `paste: /rabbit-auto-evolve start`.
    - Active + running → `line2.text` contains `loop in progress`.
    - Active + restart-needed → `line2.text` contains `resume after restart`.
    - Active + aborted → `line2.text` contains `loop aborted on safety violation`.
    - Precedence: active + running + restart-needed → restart-needed wins.
    - Precedence: active + running + aborted → aborted wins.
    - Precedence: active + restart-needed + aborted → aborted wins.
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

25. **Triage convergence guarantee (issue #423 Part E).** The triage
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

    Enforced by `test/test-spec-convergence-invariant.py` (asserts the
    invariant text is present in this spec), `test/test-triage-rules.py`
    (asserts `close-completed` is never emitted and every defer carries a
    planning_note), and `test/test-triage-batch.py` (asserts the 4th
    consecutive defer is forced to `work`).

26. **Work-selection / dispatch-shape decoupling (issue #435).** The loop
    makes two SEPARATE decisions, in order, and never lets the second
    contaminate the first.

    **(a) Stage 1 work selection is dispatch-shape blind.** The next item(s)
    to work are selected purely by priority label (`critical` > `high` >
    `medium` > `low`; no-priority last), logical readiness (barriers cleared,
    dependencies merged, no open blocking sub-issue), and issue age / queue
    position. Stage 1 MUST NOT consider dispatch shape, feature count, or
    whether the loop "knows how" to do the item. `plan-batch.py` emits the
    Stage-1 result as `selection_order`, ordered by the composite key
    `(priority desc, contract_touch desc, issue asc)` over work-only items
    (issue #479): priority is PRIMARY, the contract-touch barrier is the
    SECONDARY tiebreak (contract items lead WITHIN a priority tier, never
    across tiers), and issue number is the final stable tiebreak. Because
    `barrier_first` (Inv 4) is derived from the same composite key,
    `selection_order` and `barrier_first` always agree on ordering. The
    `contract_touch` flag is a barrier/conflict property, NOT a dispatch
    shape, so consulting it does not violate shape-blindness. A
    high-priority cross-feature item is therefore
    selected BEFORE a low-priority single-feature item, even though the
    latter is the loop's performance preference.

    **(b) Stage 2 picks among exactly THREE shapes in preference order.** For
    each selected work item, `plan-batch.py` emits `dispatch_shapes`
    (issue-number-string → shape), choosing the FIRST fitting shape. The
    item's distinct feature-dir count is `len(item["features"])` (from
    triage), or 1 when `features` is absent.

    | Rank | Shape key | When it fits | Mechanics |
    |---|---|---|---|
    | 1 (perf preference) | `parallel-per-feature` | item edits exactly one feature dir | one full single-feature TDD touch, its own `.rabbit-scope-active-<feature>` marker; multiple such items dispatch in parallel |
    | 2 | `multi-subagent-barrier` | item edits >1 feature dir, below `--decompose-threshold` (default 10) | per-feature subagents land SERIALLY on ONE shared branch; the serialization contract is: subagent k+1 fetches subagent k's pushed commit before starting; each piece is a full single-feature touch with its own scope marker; one PR closes the item |
    | 3 | `decomposition` | item edits ≥ `--decompose-threshold` feature dirs | file N per-feature sub-issues via the contract INVOKE `rabbit-issue/scripts/file-item.py` (NOT a cross-feature edit — do not edit rabbit-issue files), each labelled `rabbit-managed` + the right `feature:<name>` label; the parent stays OPEN and the sub-issues are queued, re-entering Stage 1/Stage 2 on the next tick |

    Every shape uses a full per-feature touch gated by
    `.rabbit-scope-active-<feature>`. The dispatcher MUST NOT skip, defer
    indefinitely, escalate to human, or file a meta-issue as a substitute for
    a valid item merely because it does not fit shape 1 — shapes 2 and 3
    handle cross-feature and very-large items.

    **(c) parallel-per-feature is a performance preference, not a correctness
    requirement.** It is the fastest-throughput shape, but items that do not
    fit it still get done via shapes 2 and 3, just slower.

    **(d) The session-override shape is forbidden — and why.** The original
    issue #435 proposed a Stage-2 shape 2 — "sequential single-subagent with
    scope override" — claiming "in autonomous mode the human-gating rule does
    not apply." That shape is STRUCK and MUST NOT be implemented. Per the
    maintainer's binding policy (issue #435 comment, 2026-06-03):
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

27. **Research/Investigation shape — the 4th dispatch shape (issue #478).**
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

    **(d) Deliverable + close path.** Findings are committed as a document
    under `docs/findings/<issue-N>-<slug>.md` in the named feature's scope
    (e.g. `.claude/features/<feature>/docs/findings/478-research-path.md`).
    No PR is required — a direct commit of the findings doc to the feature's
    `docs/findings/` subdirectory is sufficient and provides the commit SHA.
    The item is then closed `completed` referencing that findings commit SHA
    (via `item-status.py close --reason completed --commit-sha <sha>`, the
    existing `completed` gate). A valid research item is NEVER closed
    `not-planned`.

    A future enhancement (DISCOVERED ISSUE, rabbit-issue scope) would let
    `item-status.py close --reason completed` accept a
    `--findings-comment-url <url>` alternative to `--commit-sha` so a
    comment-only findings deliverable needs no committed doc. Until that
    lands, the committed-doc path above is the canonical research close path
    and reuses the existing `--commit-sha` gate. `item-status.py` is owned by
    `rabbit-issue` and is NOT edited by this feature.

    Enforced by `test/test-triage-rules.py` (a "study X" findings issue →
    `decision=research`, never `not-planned`; a normal "implement X" issue
    stays `work` — the over-trigger guard), `test/test-plan-batch.py` (a
    research item → `dispatch_shapes[N] == "research"`, `N` in
    `research_items`, absent from `barrier_first`/`groups`; a co-batched work
    item unaffected), and `test/test-spec-research-shape-invariant.py`
    (asserts this invariant text is present in the spec).

28. **Parallel TDD dispatches MUST use isolated git worktrees (issue
    #430).** Phase 5 (`dispatch`) dispatches each selected work item via the
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

    This invariant FORMALIZES an already-manual practice: the maintainer
    has been passing `isolation: "worktree"` on every TDD dispatch by hand;
    issue #430 elevates it to a binding invariant so it can never be
    silently dropped.

    Enforced by `test/test-spec-dispatch-worktree-isolation-invariant.py`,
    which asserts this invariant text is present in the spec AND that both
    the source and deployed `SKILL.md` document the
    `isolation: "worktree"` dispatch requirement.

29. **[SUPERSEDED by Inv 32 — issue #414.]** This invariant required phase 11
    (`schedule`) to call `ScheduleWakeup` with valid parameters. The entire
    `ScheduleWakeup` mechanism was REMOVED in issue #414; tick scheduling is
    now owned by the system cron (Inv 32). The original text is retained
    below for historical context only — `schedule-check.py` and the
    `test/test-schedule-check.py` / `test/test-spec-schedule-invariant.py`
    tests were deleted.

    Phase 11 (`schedule`) MUST call `ScheduleWakeup` with valid
    parameters (issue #409). The auto-evolve loop silently stopped
    scheduling: tick 6 ended and five subsequent hourly ticks
    (`ScheduleWakeup` at :17 past each hour) never fired across a 5h+
    window, with NO error, NO log line, and NO halt — the session was
    alive (it answered `/status` interactively). The root cause was an
    under-specified `schedule` phase: the phase-11 row documented only the
    bare string "`ScheduleWakeup` (unless stop-check matched)" and never
    pinned the three call parameters, so the dispatcher had no
    deterministic instruction on what delay to use or which prompt
    re-enters the tick. An under-specified call can silently emit nothing,
    a 0/out-of-range delay the harness ignores, or a prompt that never
    re-invokes the tick — every one of which produces exactly the observed
    silent stall.

    The `schedule` phase MUST call `ScheduleWakeup` with:

    - `delaySeconds` an integer in the inclusive band
      `60 <= delaySeconds <= 3600`. The harness ignores a 0/negative delay
      and an over-long delay is indistinguishable from a hang; the
      auto-evolve cadence is hourly, so the canonical value is `3600`.
    - `prompt` a non-empty string that RE-INVOKES the tick: it MUST
      contain the literal substring `/rabbit-auto-evolve tick`. A prompt
      that does not re-enter the tick breaks the self-chaining loop.
    - `reason` a non-empty human-readable string describing the wakeup.

    Before emitting the call, the phase MUST run
    `python3 .claude/features/rabbit-auto-evolve/scripts/schedule-check.py
    --delay-seconds <N> --prompt "<prompt>" --reason "<reason>"`, which
    validates the three parameters against the rules above and exits
    non-zero (with a `{"ok": false, "errors": [...]}` JSON payload) on any
    violation. A non-zero `schedule-check.py` exit is an error-abort path
    (Inv 20): run `end-tick.py` and surface the failure rather than
    emitting a bad — silently-dropped — wakeup. This converts the
    silent-stop failure mode into a loud, locatable one.

    `schedule-check.py` does NOT call `ScheduleWakeup` itself
    (`ScheduleWakeup` is a Claude Code harness feature, not a Python
    function); it validates the LOGIC that determines the call's
    parameters. Exit 0 + `{"ok": true, ...}` on valid params; exit 1 +
    `{"ok": false, "errors": [...]}` on any violation; `--help` exits 0.

    Enforced by `test/test-schedule-check.py` (the CLI param-validation
    unit tests: in-range happy path, the 0/59/3601 out-of-range rejections,
    the inclusive 60/3600 boundaries, empty/non-re-invoking prompt
    rejection, empty-reason rejection, and the error-payload shape) and
    the end-to-end `test/test-spec-schedule-invariant.py` (asserts this
    invariant text is present in the spec AND that both the source and
    deployed `SKILL.md` phase-11 documentation pin a concrete in-range
    `delaySeconds`, the `/rabbit-auto-evolve tick` re-invoke prompt, a
    `reason`, and the `schedule-check.py` pre-call validation).
29. **`status-report.py` owns the `status` subcommand output (issue
    #405).** The CLI
    `python3 .claude/features/rabbit-auto-evolve/scripts/status-report.py`
    is the deterministic backing script for the read-only `status`
    subcommand. Before this invariant the `status` section described its
    output in prose and the dispatcher LLM-assembled an ad-hoc bash
    pipeline (an `ls`/`cat`/`jq` improvisation) on each invocation — a
    non-deterministic, untestable surface that drifts and emits ugly
    `ls: cannot access ...` stderr noise on a fresh clone where the state
    file and markers do not yet exist. Per spec-rules §1
    (`script > CLI > spec > prompt`) this is replaced by a script.

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

    It performs NO mutations, NO `gh`, and NO `git` shellouts. Repo root
    resolution uses the `RABBIT_AUTO_EVOLVE_REPO_ROOT` env override with a
    fallback to `os.getcwd()` (matching `check-preconditions.py` and
    `banner-status.py`).

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
    - `in_flight` — the state `in_flight` array (issue numbers).
    - `last_merged_sha` / `last_tagged_version` — the state fields verbatim
      (string or null).
    - `consecutive_failures` — the state field (integer ≥ 0).
    - `markers_present` — the sorted subset of the five runtime-marker
      basenames that exist at the repo root (empty list when none).
    - `state_file` — one of `"present"` (parsed cleanly), `"absent"`
      (file missing), or `"malformed"` (file present but empty / unparsable);
      the last two both yield the default field values.

    Exit code is 0 on success (including every defaults path — missing,
    empty, or malformed state file). A non-zero exit is reserved for
    genuine invocation errors (e.g. an unwritable stdout). The verdict
    lives in the JSON, never in the exit code.

    The SKILL.md `status` subcommand body MUST invoke this script and MUST
    NOT LLM-assemble a bash pipeline or use bare `ls .rabbit-auto-evolve-*`
    / `cat .rabbit/auto-evolve-state.json` patterns — those drift and emit
    stderr noise on a fresh clone.

    This invariant was introduced by issue #405 in v0.17.0.

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

30. **`run-post-merge.py` deterministically runs phases 7–9 (issue #499).**
    Phases 7 (`release`), 8 (`cleanup`), and 9 (`catch-up`) were prose in
    SKILL.md walked by the LLM orchestrator. After phase 6 (`merge`) lands a
    large batch of PRs, the orchestrator ended the tick for scale/context
    reasons and phases 7–9 were SILENTLY dropped — the same class of failure
    as the LLM-walked-prose skips in #405 / #409 / #439. Per spec-rules §1
    (`script > CLI > spec > prompt`) the phase-7-through-9 sequencing is moved
    out of prose and into a deterministic, non-skippable script.

    ### `pending_post_merge` state field (schema 1.2.0)

    The state schema gains a new field:

    | Field | Type | Notes |
    |---|---|---|
    | `pending_post_merge` | array of int (optional) | merged PR numbers owed post-merge processing (phases 7–9). Additive in schema 1.2.0; absent in pre-1.2.0 states |

    `schema_version` is bumped to `"1.2.0"`. The change is backward-compatible
    additive: a state written WITHOUT `pending_post_merge` still validates.
    `start-loop.py`'s bootstrap default and `update-state.py`'s validator both
    recognize the field. `merge-prs.py` gains a `--record-pending` flag: after
    processing the PR list, when the flag is present it appends every
    successfully-merged PR number (the `status == "merged"` rows) to the
    `pending_post_merge` array in `<state_dir>/auto-evolve-state.json`
    (read-modify-write, de-duplicated, atomic via temp+rename; the state dir
    resolves via `RABBIT_AUTO_EVOLVE_STATE_DIR` with the
    `<cwd>/.rabbit` fallback, matching `update-state.py`). Without
    `--record-pending`, `merge-prs.py` behaves exactly as before (no state
    write). The per-PR result array on stdout is unchanged in both modes.

    ### `scripts/run-post-merge.py`

    `python3 .claude/features/rabbit-auto-evolve/scripts/run-post-merge.py`

    1. Reads `pending_post_merge` from
       `<state_dir>/auto-evolve-state.json` (state dir resolved as above).
    2. If the array is empty, missing, or the state file is absent/malformed,
       it is a CLEAN NO-OP: emit `{"status": "noop", "pending": []}` on
       stdout and exit 0 (no phase script is invoked).
    3. Otherwise, in order:
       - **Phase 7 (release):** invoke
         `release-bump.py <pr#>` once per PR in `pending_post_merge`.
         Release success is keyed on `release-bump.py`'s stdout JSON
         `status` field — NOT merely on its exit code. `release-bump.py`
         exits 0 even when its `status` is `"skipped"` (e.g.
         safety-check-failed: no git mutation) or `"failed"`, so a
         non-zero exit alone cannot distinguish an owed-but-dropped
         release from a real one (observed live on PR #510, issue #512).
         A release whose `status` is anything other than `"released"`
         (including unparseable stdout) is treated as a NON-success: the
         run does NOT proceed to cleanup/catch-up, the result `status` is
         set to `"failed"` with the offending release JSON included, and
         the run exits non-zero leaving `pending_post_merge` INTACT so the
         next tick's tick-start drain retries the owed work.
       - **Phase 8 (cleanup):** invoke
         `cleanup-branches.py <comma-joined pr-list>` once for the whole set.
       - **Phase 9 (catch-up):** invoke
         `classify-merge-restart.py <pr#>` once per PR in
         `pending_post_merge`.
    4. On completion (all phase scripts exited 0), clear
       `pending_post_merge` from state by reading the current state,
       setting `pending_post_merge` to `[]`, and writing it back atomically.
    5. Emit a result JSON object on stdout recording the pending set and each
       phase's outcome.

    Sibling phase scripts (`release-bump.py`, `cleanup-branches.py`,
    `classify-merge-restart.py`) are resolved via the
    `RABBIT_AUTO_EVOLVE_SCRIPT_DIR` env var when set, else this script's own
    dirname (matching `merge-prs.py` / `release-bump.py` /
    `cleanup-branches.py`).

    Exit code: 0 on success (including the no-op path). Non-zero on any phase
    failure — either a phase script exiting non-zero, OR a release-bump
    `status` other than `"released"` (see Phase 7) — so the caller
    (`end-tick.py` / the SKILL schedule phase) sees a loud, locatable
    failure instead of a silently-dropped phase. On a phase failure
    `pending_post_merge` is NOT cleared, so the next tick's tick-start drain
    retries the owed work.

    ### SKILL invocation

    The SKILL replaces the prose descriptions of phases 7–9 with a single
    `python3 .claude/features/rabbit-auto-evolve/scripts/run-post-merge.py`
    invocation, called in TWO places:
    - After phase 6 (`merge`) when any PR merged (the merge phase records the
      merged PR numbers via `merge-prs.py --record-pending`).
    - At the START of the tick, between phase 1 (`restart-check`) and phase 2
      (`fetch`), to DRAIN any owed post-merge work from a previous truncated
      tick BEFORE fetching new work.

    This invariant was introduced by issue #499 in v0.18.0.

    Enforced by `test/test-run-post-merge.py`:
    - Non-empty `pending_post_merge` (e.g. `[10, 20]`): the
      `release-bump.py`, `cleanup-branches.py`, and `classify-merge-restart.py`
      shims are each invoked (release + catch-up once per PR; cleanup once
      with the comma-joined list), IN ORDER (release before cleanup before
      catch-up, asserted via a shared ordered call log); `pending_post_merge`
      is cleared to `[]` in the written state; exit 0.
    - Empty `pending_post_merge` (and missing state file): clean no-op —
      no phase shim is invoked; exit 0; `status: "noop"`.
    - A phase shim exiting non-zero: `run-post-merge.py` exits non-zero and
      does NOT clear `pending_post_merge` (owed work survives for the next
      tick's drain).
    - A `release-bump.py` shim emitting `{"status": "skipped", ...}` with
      exit 0: `run-post-merge.py` exits non-zero, does NOT invoke
      cleanup/catch-up, and does NOT clear `pending_post_merge` (issue
      #512 — a skipped release is an owed release, not a success).
    - `--help` smoke: exit 0 with recognizable usage text.

    And by `test/test-merge-prs.py` (extended): with `--record-pending`, the
    merged PR numbers are appended (de-duplicated) to `pending_post_merge` in
    the state file; without it, no state write occurs.

    And by `test/test-spec-post-merge-invariant.py` (e2e): asserts the Inv 30
    text is present in the spec AND that both the source and deployed SKILL.md
    invoke `run-post-merge.py` after the merge phase AND at tick start.

31. **[SUPERSEDED by Inv 32 — issue #414.]** This invariant tuned the
    `ScheduleWakeup` delay by queue emptiness. The `ScheduleWakeup`
    mechanism was REMOVED in issue #414; the system cron fires on a fixed
    cadence (Inv 32) regardless of queue emptiness. Original text retained
    for context only.

    Phase 11 (`schedule`) refires immediately when the queue is
    non-empty (issue #412). Before this invariant the `schedule` phase
    always used the canonical hourly delay (`delaySeconds=3600`, Inv 29).
    That fixed delay means a tick that just dispatched work — or that
    found items still waiting in `state.queue` / `state.in_flight` — sits
    idle for the full hour before the loop looks again, even though there
    is actionable work it could pick up right now. The loop's throughput
    is then capped at roughly one batch per hour regardless of how much
    work is queued.

    The `schedule` phase MUST therefore choose `delaySeconds` based on
    queue emptiness, read from `<state_dir>/auto-evolve-state.json`:

    - When `len(state.queue) > 0 OR len(state.in_flight) > 0` (work
      remains), use `delaySeconds=60` — the harness minimum (Inv 29
      floor), i.e. refire immediately — with
      `reason="queue non-empty, refiring immediately"`.
    - When BOTH `state.queue` AND `state.in_flight` are empty (no work
      remains), use `delaySeconds=3600` — the hourly idle check (Inv 29
      canonical value) — with `reason="queue empty, waiting for new
      issues"`.

    Both `60` and `3600` are inside the Inv 29 inclusive band
    `60 <= delaySeconds <= 3600`, so `schedule-check.py` accepts either;
    this invariant REPLACES the single fixed `3600` delay with the
    two-delay rule. The `prompt` is unchanged (`/rabbit-auto-evolve
    tick`), and the pre-call `schedule-check.py` validation (Inv 29)
    still runs with whichever delay/reason pair was selected.

    A missing, empty, or malformed state file is treated as queue-empty
    (the long hourly delay) — the conservative idle case.

    This invariant was introduced by issue #412.

    Enforced by `test/test-schedule-check.py` (extended): asserts both
    `delaySeconds=60` and `delaySeconds=3600` are accepted by the
    validator (both inside the Inv 29 band), so neither delay is silently
    dropped. And by the end-to-end
    `test/test-spec-schedule-invariant.py` (extended): asserts this
    invariant text is present in the spec AND that both the source and
    deployed `SKILL.md` phase-11 documentation pin BOTH the `60`
    (queue-non-empty refire) and `3600` (queue-empty idle) cases together
    with the queue-emptiness branch that selects between them.
31. **`check-auto-resume.py` owns mechanical restart-resume detection
    (issue #424).** Today's restart recovery is convention-enforced: after a
    `restart-needed` tick the human must read the SessionStart banner (Inv 22
    line-2 `resume after restart` variant) and manually paste
    `/rabbit-auto-evolve start`. A missed read silently stalls the loop. Per
    spec-rules §1 (`script > CLI > spec > prompt`) the resume decision is
    moved out of human convention and into a deterministic script so the
    SessionStart hook can mechanically self-resume.

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
    "/rabbit-auto-evolve start"}`; otherwise it emits `{"resume": false,
    "action": null}`. The `.rabbit-auto-evolve-aborted` marker is NOT
    consulted here — abort handling is the banner's responsibility (Inv 22);
    this script answers only the narrow "should we mechanically re-launch the
    loop after a restart" question.

    Exit code is ALWAYS 0 — the verdict is carried in `resume`, not in the
    exit code. The script reads files only (`os.path.exists`) and never
    invokes `ls`, `test -f`, or any command that would exit non-zero on the
    expected "not active" path. `<repo_root>` defaults to `os.getcwd()`;
    overridable via the `RABBIT_AUTO_EVOLVE_REPO_ROOT` env var for tests.

    **rabbit-cage integration (cross-scope INVOKE, NOT a feature edit).** The
    SessionStart hook is owned by rabbit-cage. The CORRECT cross-scope
    mechanism is for rabbit-cage's SessionStart hook to INVOKE this
    rabbit-auto-evolve script and, when `resume` is true, surface the `action`
    so the loop auto-resumes — exactly the contract-INVOKE pattern already
    used elsewhere (this feature's `invokes` block). The actual hook wiring is
    a SEPARATE rabbit-cage touch filed as a discovered issue; it is out of
    this feature's scope. This invariant fixes only the rabbit-auto-evolve
    side: the deterministic resume-detection script plus the documented
    conditions the hook consumes.

    This invariant was introduced by issue #424 in v0.19.0.

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

32. **Tick scheduling is owned by the system cron; `ScheduleWakeup` and
    `CronCreate` are NEVER used in rabbit-auto-evolve (issue #414).** The
    prior architecture self-chained ticks from inside a live Claude session
    via `ScheduleWakeup` (Inv 29 / Inv 31). That coupled the loop's cadence
    to an open session and made the next tick a Claude-harness side effect
    that could silently drop (the issue #409 incident). Issue #414 replaces
    self-chaining with an EXTERNAL trigger: a single system `cron` entry is
    the SOLE tick scheduler. `ScheduleWakeup` and `CronCreate` are removed
    entirely; neither appears anywhere in this feature's scripts or SKILL.md.

    **The split between headless and session ticks.**

    - **Headless tick (cron-fired, no Claude session).** The cron entry runs
      `python3 .claude/features/rabbit-auto-evolve/scripts/tick-headless.py`.
      It walks the deterministic, Claude-free phases:
      phase 0 (`stop-check`), phase 1 (`restart-check`),
      phases 2–4 (`fetch | triage | plan`),
      phase 6 (`merge` of the PRs listed in the state's transient
      `merge_ready` hint field, skipped when empty),
      phases 7–9 (`run-post-merge.py` when `pending_post_merge` non-empty),
      phase 10 (`persist`). `merge_ready` is a transient per-tick hint, NOT
      part of the canonical Inv 9 state schema, so the headless tick drops it
      before handing the state object to `update-state.py` (whose validator
      rejects unknown keys). It does NOT run phase 5 (`dispatch`) — that
      requires a Claude session — and it does NOT schedule anything (phase 11
      is a no-op; the cron fires the next tick). A pending stop
      (`.rabbit-auto-evolve-stop-requested`) or abort
      (`.rabbit-auto-evolve-aborted`) marker short-circuits the headless tick
      to a clean no-op.
    - **Session tick (Claude active).** The full 12-phase tick walked by
      SKILL.md still runs, INCLUDING phase 5 (`dispatch`). Phase 11
      (`schedule`) no longer calls `ScheduleWakeup` — it is documented as a
      no-op because the cron owns scheduling.

    **Cron lifecycle (owned by `set-evolve-mode.py`).**

    - `scripts/install-cron.py` installs ONE crontab entry of the form
      `*/30 * * * * cd <repo_root> && python3
      .claude/features/rabbit-auto-evolve/scripts/tick-headless.py >>
      .rabbit/tick-headless.log 2>&1` using the `crontab -l` (read) +
      append + `crontab -` (write) pattern. It is IDEMPOTENT: if an entry
      mentioning `tick-headless.py` already exists, it is a clean no-op
      (running twice yields exactly one entry). Exit 0 on success.

      **Restricted-host graceful fallback (issue #507).** On some hosts the
      `crontab` binary is administratively restricted ("You ... are not
      allowed to use this program (crontab)"). In that case
      `install-cron.py` DETECTS the restriction — distinguished from the
      legitimate "no crontab for user" empty case (exit 1 with empty
      output) by a permission-denial signal in stderr (e.g. "not allowed")
      on `crontab -l`, or by a permission failure on the `crontab -` write
      — and FALLS BACK GRACEFULLY rather than failing opaquely: it exits 0
      and emits a clear, actionable `rabbit_print` message (rendered via
      the contract `rabbit_print` module; never hardcoded ANSI/brand
      strings, per contract Inv 48) that (a) states crontab is restricted
      on this host, (b) warns the loop will not auto-tick headlessly here,
      and (c) gives the exact manual remediation — the `*/30` cron entry to
      hand to a sysadmin AND that the operator can run
      `/rabbit-auto-evolve start` manually each session. Cron remains the
      SOLE tick scheduler WHEN AVAILABLE (Inv 32 unchanged); the fallback
      covers only the restricted-host case so a mode flip is never blocked
      by an un-installable cron. The `RABBIT_CRONTAB_CMD` and
      `RABBIT_AUTO_EVOLVE_REPO_ROOT` overrides are preserved.
    - `scripts/uninstall-cron.py` removes the entry via the
      `crontab -l | grep -v tick-headless | crontab -` pattern. It is
      IDEMPOTENT and safe when the entry is absent (and when no crontab
      exists at all). Exit 0 on success including the absent case.
    - `set-evolve-mode.py on` invokes `install-cron.py` after writing the
      three activation markers; `set-evolve-mode.py off` invokes
      `uninstall-cron.py` before tearing down the markers. A cron
      install/uninstall failure is surfaced but does not by itself fail the
      mode flip (best-effort, like the loop-runtime marker deletion).

    Enforced by `test/test-cron-trigger.py` (e2e): `install-cron.py` installs
    exactly one entry and is idempotent across two runs; `uninstall-cron.py`
    removes it and is a safe no-op when absent; AND when the `crontab` shim
    simulates a restricted host (permission denial on both `-l` and `-`),
    `install-cron.py` exits 0 without crashing and prints the actionable
    restricted-host remediation message (issue #507). By
    `test/test-tick-headless.py` (e2e): the headless tick runs phases 0–1,
    2–4 (plan only — no dispatch), 6, 7–9, and 10 without a Claude session,
    and short-circuits on a stop/abort marker. And by
    `test/test-spec-cron-invariant.py` (e2e): this invariant text is present
    in the spec AND neither the source nor the deployed `SKILL.md` contains
    any `ScheduleWakeup` or `CronCreate` reference, and both document the
    cron-owned scheduling and the headless tick.

## Known gaps

- All implementation phases complete (Phases A–E). The activation
  surface lives on `/rabbit-auto-evolve on|off` (Inv 11); the
  rabbit-config dispatch entry was removed in 0.5.0. Phase F manual
  smoke test (initiate `on`, restart Claude, observe banner, `start`,
  observe tick, `stop`, `off`) remains pending — it requires user-
  driven Claude restart and observation, not a TDD cycle.
- All three prerequisite changes have **landed on `dev`** as of the
  commits noted in the prompt context (#327/#330, #328/#331, #329/#332);
  they are not gaps. The plan's Phase A verification step can be treated
  as already satisfied.

## Open questions (to resolve during Phases C–E)

These were surfaced by the spec-creator subagent and require dispatcher /
owner decisions during component implementation.

1. **`max_parallel` configurability surface.** The design specifies a
   default of 4 and says it is "declared in the auto-evolve configurable",
   but the `feature.json` configuration block only shows `values: {on,
   off}` for the `auto-evolve` subcommand. Is `max_parallel` a separate
   `/rabbit-config` entry, an environment variable, a field in
   `.rabbit/auto-evolve-state.json`, or a CLI flag passed to
   `plan-batch.py --max-parallel`? The plan (Task 6) uses
   `--max-parallel N` as a CLI flag — recommend pinning that as the
   canonical surface and noting the default in spec text.

2. **`safety-check.py` phase-release tag argument shape.** The design
   says the next tag is passed via env `$RABBIT_AUTO_EVOLVE_NEXT_TAG`
   when `--phase release`. Is env the agreed interface, or should
   `release-bump.py` call `safety-check.py` with the tag as a positional
   argument? Tasks 7 and 9 of the plan are ambiguous; pick one before
   Task 7's TDD cycle starts.

3. **(RESOLVED — Inv 9.)** `restart_needed` field type is `string | null`
   (the string carries the reason). Encoded in
   `scripts/schemas/auto-evolve-state.schema.json` and enforced by
   `update-state.py`.

4. **Glob registration / scope-protection.** Standalone feature; no
   globs registered. Once scripts and markers are in place, should the
   owner register the globs `.claude/features/rabbit-auto-evolve/**` and
   `.rabbit/auto-evolve-state.json` and the markers `.rabbit-auto-evolve-*`
   so scope-protection and drift checks apply, or are the markers
   intentionally unscoped (since they are runtime state, not source)?

5. **(RESOLVED — Inv 12 + contract.md `invokes`.)** The cross-scope
   writes to `.claude/features/contract/workspace-structure.json`
   (add `rabbit-auto-evolve` to `features.children`) and
   `.claude/features/contract/templates/prompts/rabbit-auto-evolve.txt`
   (the passthrough template matching the `prompts` declaration) are
   explicitly declared in this feature's `specs/contract.md`
   `invokes.files` block. The writes are performed via one-time
   `.rabbit-scope-override` markers during the Phase D Task 12
   feature touch.

6. **`tdd_state` progression across multi-component build-out.**
   `feature.json` currently shows `tdd_state: "spec"`. The plan calls
   for advancing this through `test-red → impl → test-green`
   per-component; however with 12 separate feature-touch cycles, the
   `tdd_state` field will be bumped multiple times. Should the field
   reflect the overall feature state (staying at `impl` until all 12
   components are green) or track the most recently touched component?

## What this feature does NOT define

- The `contract.lib.runtime` APIs `emit_auto_evolve_banner`,
  `emit_auto_evolve_stop_line`, and the suppression hook in
  `iterate_configurables_alerts` / `_banner` — owned by the `contract`
  feature (Inv 64–65, landed in commit `73d1217`).
- The `tdd-step.py abort` subcommand and the HANDOFF JSON fields
  `discovered_issues` / `aborted_reason` — owned by the `tdd-subagent`
  feature (Inv 50–55, landed in commits `7b4e4b4` and `5a6d195`).
- The `human-approval` and `bypass-permissions` configurables themselves
  — owned by the `rabbit-cage` feature. This feature only flips them
  during `set-evolve-mode.py`.
- The TDD cycle itself — owned by `tdd-subagent` and orchestrated by
  `rabbit-feature-touch`. This feature consumes them.
- The `gh` CLI wrapper for issues — owned by `rabbit-issue`. This
  feature consumes it.
