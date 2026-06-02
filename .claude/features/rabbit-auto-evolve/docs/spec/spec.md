---
feature: rabbit-auto-evolve
version: 0.2.0
owner: cyxu
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
and reschedules itself via `ScheduleWakeup` until the user issues an
explicit stop — all without requiring human approval at each step.

## Paths governed

- (none — standalone feature)

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
| `scripts/safety-check.py` | CLI | Validates five bottom-line invariants (branch is `dev`, PR base is `dev`, head branch matches `^feat/.+`, tag does not already exist, working tree is clean); exits non-zero on any violation |
| `scripts/merge-prs.py` | CLI | Calls `safety-check.py --phase merge` then `gh pr merge --squash --auto` for each PR; refuses any PR whose base is not `dev` |
| `scripts/release-bump.py` | CLI | Reads merged PR priority label and diff scope; applies patch/minor/major semver bump per design table; creates annotated git tag and `gh release` targeting `dev` |
| `scripts/cleanup-branches.py` | CLI | Derives head branch from each merged PR; calls `safety-check.py --phase cleanup`; deletes branch locally and on origin; refuses to delete anything not matching `^feat/.+` |
| `scripts/classify-merge-restart.py` | CLI | Reads merged PR file list; classifies into `no-op`, `refresh`, or `restart` based on which path patterns appear; emits a single string on stdout |
| `scripts/update-state.py` | CLI | Reads JSON from stdin; validates against `schemas/auto-evolve-state.schema.json`; atomically writes `.rabbit/auto-evolve-state.json` via temp+rename |

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
- Contract-touch issues (`feature:contract` label or body paths under
  `.claude/features/contract/`) are always isolated into a `barrier_first`
  queue processed one at a time before any parallel group runs. (design
  doc §6)
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

   On `off`, the three reverse in inverse order: delete
   `.rabbit-auto-evolve-active`; delete the `permissions.defaultMode`
   key via `contract.lib.mutation.delete_json_key`; delete
   `.rabbit-human-approval-bypass` via
   `contract.lib.mutation.delete_marker`.

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
     "decision": "work" | "close-not-planned" | "defer",
     "reason_code": "<short-tag>",
     "rationale": "<one sentence>",
     "feature": "<feature-name or null>",
     "contract_touch": true,
     "blocked_by": [124]
   }
   ```

   The script reads only:
   - Issue metadata (title, body, labels, state, comments) via
     `gh issue view <N> --repo <repo> --json
     number,title,body,labels,state,comments`.
   - The named feature's `docs/spec/spec.md` head matter (YAML
     frontmatter and the first markdown section only) — for rule 6.
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
   | 7 | Otherwise | `work` | `actionable` |

   `contract_touch` is `true` iff the issue carries a
   `feature:contract` label OR the body literally declares any path
   under `.claude/features/contract/`.

   **Ambiguity default:** Any case the seven rules cannot resolve
   (e.g. malformed `blocked-by` syntax, unparsable spec head matter,
   `gh` returning a payload missing expected fields) defaults to
   `decision=defer`, `reason_code=needs-judgment`. The triage MUST
   NEVER fall through silently to `work`; the loop under-dispatches
   rather than over-dispatches.

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
   - Smoke test: invoke with `--help`; assert exit 0 and recognizable
     usage text.

## Known gaps

- Phase C scripts still to land: `plan-batch.py`, `safety-check.py`,
  `merge-prs.py`, `release-bump.py`, `cleanup-branches.py`,
  `classify-merge-restart.py`, `update-state.py`. (`set-evolve-mode.py`
  landed in PR #335; `fetch-queue.py` in PR #339; `triage-issue.py`
  lands in this cycle.) Each remaining script lands via its own
  feature-touch cycle.
- `feature.json` carries placeholder values: `summary: "rabbit-auto-evolve
  feature"` and `deprecation_criterion: "TBD — set after first review"`.
  Both must be filled before the feature passes the shape-compliance test
  (`test-feature-shape.py`). The spec frontmatter above already carries
  the final `deprecation_criterion`; `feature.json` will be aligned in
  Phase D Task 12.
- `feature.json` declares empty `surface.skills`, no `configuration`
  block, no `runtime` block, and no `prompts` block. These are populated
  in Phase D Task 12.
- `test/run.py` is a scaffold placeholder; no `test-*.py` files exist
  yet.
- No `SKILL.md` exists under `skills/rabbit-auto-evolve/` yet.
- No `CHANGELOG.md` exists yet (added in Phase E Task 14).
- No `scripts/schemas/auto-evolve-state.schema.json` exists yet (added in
  Task 11).
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

3. **`restart_needed` field type in state schema.** Task 11 of the plan
   defines `restart_needed: bool|null` in one place and "reason string
   when set, else null" in another. Pick: pure boolean (clean), or
   nullable string (carries the reason for surfacing). Latter is more
   useful — recommend `string | null` and update plan accordingly.

4. **Glob registration / scope-protection.** Standalone feature; no
   globs registered. Once scripts and markers are in place, should the
   owner register the globs `.claude/features/rabbit-auto-evolve/**` and
   `.rabbit/auto-evolve-state.json` and the markers `.rabbit-auto-evolve-*`
   so scope-protection and drift checks apply, or are the markers
   intentionally unscoped (since they are runtime state, not source)?

5. **`workspace-structure.json` cross-scope write.** Task 12 modifies
   `.claude/features/contract/workspace-structure.json` from within this
   feature's touch cycle. The plan calls it "allowlisted." Should this
   be explicitly recorded under `docs/spec/contract.md` `invokes`, and
   does the `contract` feature's spec need a corresponding `provides`
   entry before Task 12 runs?

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
