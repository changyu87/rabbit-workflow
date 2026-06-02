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

4. **`plan-batch.py` conflict-graph + barrier dispatch planner.** The CLI
   `cat work-set.json | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py [--max-parallel N]`
   reads a JSON array of triage objects on stdin (caller passes only
   `decision == "work"` items) and emits a deterministic dispatch plan
   to stdout:

   ```json
   {
     "barrier_first": [123, 124],
     "groups": [[125, 126], [127]]
   }
   ```

   Each input item carries at least: `issue` (int), `feature` (string),
   `contract_touch` (bool), and `priority` (one of `critical` / `high`
   / `medium` / `low`; missing or unrecognized → sorts last).

   The script is a pure JSON processor — no `gh`, no `git`, no
   filesystem reads or writes other than stdin/stdout.

   `--max-parallel N` (positional flag, default 4) is the canonical
   surface for the cap (resolved Open Question 1). The flag MUST be
   integer-valued and ≥ 1; non-integer or `< 1` exits non-zero with
   argparse error.

   Algorithm (4 steps from design doc §6):

   1. **Pull out `contract_touch == true` items** into `barrier_first`,
      sorted by priority desc (critical > high > medium > low;
      no-priority last) then `issue` ascending.
   2. **Build a conflict graph on the remainder.** Nodes are issues;
      an edge exists between A and B iff `A.feature == B.feature`.
   3. **Greedy graph coloring.** Sort the remainder by priority desc
      then `issue` ascending; walk in that order and assign each issue
      the lowest-numbered color (group index) that has no neighbor
      already in it. `groups` is the color partition, in color order.
   4. **Apply `--max-parallel` cap.** Any group whose size exceeds the
      cap is split into sub-groups of size ≤ cap. Sub-groups appear as
      separate consecutive entries in the output `groups` list
      (parallel-safe within each sub-group; the loop processes
      sub-groups sequentially).

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
   | 5 | Working tree is clean (`git status --porcelain` empty) | all |

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
     tag / dirty tree) under the appropriate phase → non-zero exit;
     stderr names the violated invariant.
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
   3. Otherwise call `gh pr merge <#> --squash --auto`. On success →
      `{pr: N, status: "merged"}`; on failure →
      `{pr: N, status: "failed", reason: "gh-merge-failed: <stderr>"}`.

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
   2. Apply bump table → compute `next_tag = vX.Y.Z`.
   3. `safety-check.py <pr#> --phase release --next-tag <next_tag>`.
      Non-zero → emit `{status: "skipped", reason: "safety-check-failed"}`
      and stop (no git mutation, exit 0).
   4. `git describe --tags --abbrev=0` → `prior_tag`.
   5. `git tag -a <next_tag> -m "<auto-evolve> #<pr> <title>"`.
   6. `git push origin <next_tag>`.
   7. `gh release create <next_tag> --notes-from-tag --target dev`.

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
   | `schema_version` | string | Literal `"1.0.0"` |
   | `updated_at` | string | ISO 8601 UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ` |
   | `queue` | array of objects | each `{issue: int, decision: string, feature: string}` |
   | `in_flight` | array of int | currently-dispatched issue numbers |
   | `last_merged_sha` | string \| null | last PR merge commit SHA |
   | `last_tagged_version` | string \| null | last release tag (e.g. `"v0.5.3"`) |
   | `consecutive_failures` | int | ≥ 0 |
   | `stop_requested` | bool | stop marker observed |
   | `restart_needed` | string \| null | reason string when set, else null (resolved Open Question 3 — NOT a pure boolean) |

   The schema file itself carries top-level `schema_version`, `owner`,
   and `deprecation_criterion` keys per spec-rules §3.

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

10. **`rabbit-auto-evolve` SKILL documents 4 subcommands and 12-phase
    tick.** `skills/rabbit-auto-evolve/SKILL.md` declares
    `model: opus` in frontmatter and documents four subcommands:

    - `start` — verifies the three preconditions
      (`.rabbit-auto-evolve-active` present, `human-approval` off,
      `bypass-permissions` on). On all-pass, writes
      `.rabbit-auto-evolve-running`, runs one tick, calls
      `ScheduleWakeup` to chain the next.
    - `stop` — writes `.rabbit-auto-evolve-stop-requested`; the next
      tick observes and does NOT call `ScheduleWakeup`.
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

    The SKILL.md also describes the in-loop discovery handling per
    design §6: when a TDD subagent's HANDOFF carries
    `discovered_issues`, file each via `rabbit-issue`; when
    `aborted_reason` is set, label `blocked-by:#N` on the original
    issue and leave it open.

    Enforced by `test/test-tick-skill.py`,
    `test/test-start-stop-skill.py`, and
    `test/test-discovered-issues.py`.

11. **`feature.json` configuration entry uses `set-evolve-mode.py`
    compound mutator with `restart_required: true`.** The
    `configuration` array carries one entry:

    ```json
    {
      "id": "auto-evolve",
      "subcommand": "auto-evolve",
      "values": {
        "on":  {"api": "run_feature_script", "args": {"script": "scripts/set-evolve-mode.py", "argv": ["on"]}},
        "off": {"api": "run_feature_script", "args": {"script": "scripts/set-evolve-mode.py", "argv": ["off"]}}
      },
      "default": "off",
      "alert-on": "on",
      "alert-message": {
        "text": "AUTONOMOUS-EVOLVE MODE ACTIVE — composite (human-approval + bypass-permissions + auto-evolve marker)",
        "icon": "🤖",
        "color": "red"
      },
      "restart_required": true
    }
    ```

    Both `on` and `off` dispatch through `set-evolve-mode.py` (Inv 1)
    which handles ordering and rollback. `restart_required: true`
    forces Claude restart between `on` and the first `/start` so
    Claude Code picks up the new `settings.local.json`
    `permissions.defaultMode`.

12. **`feature.json` declares the `prompts` and `runtime` entries
    binding rabbit-auto-evolve to the rabbit dispatcher.** The
    manifest's `prompts` array contains exactly one entry:

    ```json
    {
      "id": "rabbit-auto-evolve",
      "kind": "skill",
      "inject": ["philosophy", "spec-rules", "coding-rules"],
      "slots": ["args"]
    }
    ```

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

## Known gaps

- All Phase C scripts have landed (#335, #339, #341, #343, #345, #347,
  #349, #351, #353). Phase D Task 12 (SKILL.md + feature.json wiring
  + workspace-structure.json + passthrough template) lands in this
  cycle. Phase D Task 13 (banner suppression test) and Phase E
  (feature-shape compliance + final suite) follow.
- No `CHANGELOG.md` exists yet (added in Phase E Task 14).
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
   explicitly declared in this feature's `docs/spec/contract.md`
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
