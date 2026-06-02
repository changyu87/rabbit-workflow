---
title: rabbit-auto-evolve — autonomous evolution mode
date: 2026-06-01
owner: cyxu
status: draft
supersedes: none
prerequisites:
  - tdd-subagent abort/quit mechanism (separate issue)
  - tdd-subagent HANDOFF schema extension (discovered_issues, aborted_reason)
  - contract.lib.runtime banner-suppression hook
---

# rabbit-auto-evolve — Design

## 1. Purpose

`rabbit-auto-evolve` is a new rabbit feature that turns the rabbit workflow
into a self-driving loop. When the mode is active and the user starts the
loop, Claude:

- monitors open `rabbit-managed` issues,
- triages each (work / close-not-planned / defer),
- dispatches TDD subagents — in parallel where features do not conflict,
  sequentially where they do, with a hard barrier for any `feature:contract`
  issue,
- opens PRs against `dev`, merges them (never touches `main`), tags a release
  with a priority-derived semver bump per merge,
- cleans up work branches,
- decides whether the merged change needs no refresh, a `/rabbit-refresh`,
  or a full restart,
- persists state to disk so a restart never nukes progress,
- and re-schedules its next iteration via `ScheduleWakeup`, until the user
  stops it.

The mode is entered via the existing `/rabbit-config` skill. Activation
flips `human-approval` off and `bypass-permissions` on (both managed by
`rabbit-cage` today), writes a marker `.rabbit-auto-evolve-active`, and
emits the standard restart-required prompt. After the user restarts Claude,
the SessionStart banner is a single composite line directing the user to
paste `/rabbit-auto-evolve start` to begin.

## 2. Activation and entry

A new feature `rabbit-auto-evolve` under
`.claude/features/rabbit-auto-evolve/`. Standard rabbit feature shape
(`feature.json`, `docs/spec/spec.md`, `docs/spec/contract.md`, `test/run.py`,
`skills/`, `scripts/`).

`feature.json` declares one CONFIGURATION entry:

- `subcommand: "auto-evolve"`
- `values: {on, off}` — both dispatch via
  `run_feature_script → scripts/set-evolve-mode.py {on|off}`
- `restart_required: true` (so rabbit-config's interpreter emits the
  yellow restart-prompt line after a successful mutation, per
  rabbit-config Inv 20)

`scripts/set-evolve-mode.py on` performs three deterministic mutations in
order, aborting on first error and rolling back the prior ones:

1. Flip `human-approval` → `false` (write `.rabbit-human-approval-bypass`)
2. Flip `bypass-permissions` → `true` (set
   `permissions.defaultMode: bypassPermissions` in
   `.claude/settings.local.json`)
3. Write `.rabbit-auto-evolve-active` marker

`scripts/set-evolve-mode.py off` reverses the three in inverse order.

Both forms end by printing the `restart_required` yellow `rabbit_subline`
emitted by rabbit-config's interpreter, instructing the user to exit and
relaunch Claude for the permission-mode change to take effect.

## 3. Skill surface

One skill `rabbit-auto-evolve` declared in
`feature.json.surface.skills`. Frontmatter declares `model: opus`. The
matching prompts entry injects philosophy + spec-rules + coding-rules (the
skill both orchestrates code and authors specs through the TDD subagent).

Subcommands invoked as `Skill("rabbit-auto-evolve", args: "<sub>")`:

| Subcommand | Purpose | Behavior |
|---|---|---|
| `start` | Begin or resume the loop | Refuses unless mode is active (marker present) AND `human-approval` is off AND `bypass-permissions` is on. Writes `.rabbit-auto-evolve-running` marker. Runs one tick immediately, then ends by calling `ScheduleWakeup` to chain the next. |
| `stop` | Graceful stop | Writes `.rabbit-auto-evolve-stop-requested` marker. The next tick sees it, posts a summary, removes the running marker, and does NOT reschedule. |
| `status` | Read-only inspect | Prints queue length, in-flight set, last-merged PR, last-tagged version, consecutive-failure count, and which restart-marker (if any) is present. Does not mutate. |
| `tick` | Internal — one loop iteration | Not invoked by the user directly. Only `ScheduleWakeup` calls this. The SKILL.md notes the subcommand exists but documents it as `internal`. |

User-typed interrupt is handled by Claude Code's natural turn semantics —
`ScheduleWakeup` only fires when the REPL is idle, so any user prompt
preempts the next wake-up. The loop's stop logic kicks in only when the
user explicitly runs `/rabbit-auto-evolve stop`.

## 4. One tick

A tick is the atomic unit of loop work. The dispatcher (Claude/LLM) walks
these phases. Deterministic substeps push into Python scripts so that the
LLM's job per tick is small: walk the phases, invoke each script, read its
JSON, and act.

```
TICK
├─ 0. STOP-CHECK    read .rabbit-auto-evolve-stop-requested → if present,
│                   summarize run + exit (no reschedule)
├─ 1. RESTART-CHECK read .rabbit-auto-evolve-restart-needed → if present,
│                   exit (no reschedule)
├─ 2. FETCH         scripts/fetch-queue.py → emits open rabbit-managed
│                   issues as JSON (gh issue list, sorted by priority then
│                   created-at)
├─ 3. TRIAGE        for each candidate: scripts/triage-issue.py <issue#> →
│                   emits {decision, reason_code, rationale, feature,
│                   contract_touch, blocked_by}
│                   - close-not-planned → dispatcher calls rabbit-issue's
│                     item-status.py close --reason not_planned + comment
│                   - defer → gh issue edit adds blocked/needs-info label,
│                     skip this tick
│                   - work → feed into Phase 4
├─ 4. PLAN          scripts/plan-batch.py < work-set.json → emits
│                   {barrier_first: [issue#…], groups: [[issue#…], …]}
├─ 5. DISPATCH      for each issue in barrier_first (one at a time, drain
│                   between): Skill("rabbit-feature-touch", args: "<#>")
│                   then for each group sequentially, dispatch the group's
│                   issues in parallel; wait for all HANDOFFs before next
│                   group. Cap parallel-in-flight at max_parallel (default 4).
├─ 6. MERGE         scripts/merge-prs.py <pr-list> → gh pr merge --squash
│                   --auto into dev for each green PR. Never main.
├─ 7. RELEASE       scripts/release-bump.py <merged-pr-list> → per merged
│                   PR: priority → patch|minor|major bump → git tag + gh
│                   release create --target dev
├─ 8. CLEANUP       scripts/cleanup-branches.py <merged-pr-list> → delete
│                   each feature-touch work branch (local + origin)
├─ 9. CATCH-UP      scripts/classify-merge-restart.py <merged-pr-list> →
│                   no-op | refresh | restart-needed
│                   - refresh → Skill("rabbit-refresh")
│                   - restart-needed → write .rabbit-auto-evolve-restart-needed,
│                     fall through to STOP-CHECK on next tick
├─10. PERSIST       scripts/update-state.py → rewrite
│                   .rabbit/auto-evolve-state.json (queue snapshot,
│                   in-flight set, last-merged-sha, last-tagged version,
│                   consecutive-failure count, stop marker observed)
└─11. SCHEDULE      ScheduleWakeup(delaySeconds=N,
                    prompt="Skill('rabbit-auto-evolve','tick')")
                    N derived from workload: full queue → 60s; partial →
                    300s; empty → 1800s
```

The SKILL.md documents all twelve phases (0–11) in this order, names
every script, names the disk-state path, and explains the wake-up
reschedule logic.

## 5. Triage contract

`scripts/triage-issue.py <issue#>` reads only the issue body, labels,
comments, and the named feature's `docs/spec/spec.md` head matter — never
the codebase at large. It emits JSON:

```json
{
  "issue": 123,
  "decision": "work" | "close-not-planned" | "defer",
  "reason_code": "<short-tag>",
  "rationale": "<one sentence>",
  "feature": "<feature-name>",
  "contract_touch": true,
  "blocked_by": [124]
}
```

Decision rules (top-down, first match wins):

| Rule | Decision | reason_code |
|---|---|---|
| Issue lacks `feature:<name>` or `priority:<level>` label | `defer` | `malformed-labels` |
| Feature named by label does not exist on disk | `close-not-planned` | `unknown-feature` |
| Issue title/body matches a closed issue in last 30 days (case-folded substring on title) | `close-not-planned` | `duplicate` |
| Issue references a feature whose `feature.json.status == "retired"` | `close-not-planned` | `feature-retired` |
| Issue body declares `blocked-by: #N` AND any #N is still open | `defer` | `blocked` |
| Feature's spec already documents the requested behavior verbatim (substring match on issue summary line) | `close-not-planned` | `already-spec'd` |
| Otherwise | `work` | `actionable` |

`contract_touch` is true iff the issue label is `feature:contract` OR the
body declares a path under `.claude/features/contract/`.

Anything ambiguous defaults to `defer` with reason_code `needs-judgment` —
never silently to `work`. The loop under-dispatches rather than
over-dispatches.

## 6. Conflict graph and dispatch

`scripts/plan-batch.py` consumes the work-classified set and emits a
deterministic dispatch plan:

```json
{
  "barrier_first": [123, 124],
  "groups": [
    [125, 126],
    [127]
  ]
}
```

Algorithm:

1. **Pull out contract issues.** Any issue with `contract_touch: true` is
   removed from the main set and placed in `barrier_first`, sorted by
   priority then issue number. Phase 5 drains `barrier_first` entirely
   (one at a time, waiting for each HANDOFF) before touching `groups`.
2. **Build conflict graph on the remainder.** Nodes = issues. Edge between
   A and B iff `A.feature == B.feature`. (Future extension: per-feature
   `paths` glob overlap detection — out of scope v1.)
3. **Greedy graph coloring.** Sort issues by priority descending, then
   issue number ascending. Walk in order; assign each issue the
   lowest-numbered color (group) that has no neighbor already in it.
   The groups list is the color partition, in color order.

**Bounded parallelism.** Cap in-flight subagents per tick at
`max_parallel` (declared in the auto-evolve configurable; default 4). If a
group exceeds the cap, split it into sub-groups of size ≤ cap, parallel
within each sub-group, sequential across sub-groups.

**In-loop discovery handling.** If a dispatched TDD subagent's HANDOFF
reports a `discovered_issues: [...]` array (new field on the TDD HANDOFF
contract — see Section 11 prerequisites), the dispatcher:

1. Files each discovered item via `rabbit-issue` with reason
   `discovered-during-evolve`.
2. If the HANDOFF reports `aborted_reason` (the original work was blocked
   by the discovery), the dispatcher posts a `blocked-by:#N` label on the
   original issue, comments with the abort summary, and leaves the issue
   open.
3. The aborted issue is dropped from this tick and re-enters the queue on
   the next tick (triage will defer it because of the new `blocked` label).

## 7. Live-update / catch-up semantics

The loop's state lives on disk in `.rabbit/auto-evolve-state.json`. Every
tick reads it fresh. A full restart never nukes progress — the user just
types `/rabbit-auto-evolve start` again after restart and the next tick
picks up where the previous left off.

Refresh ladder (chosen automatically by
`scripts/classify-merge-restart.py` based on the merged file list):

1. **No-op** (default) — code/script/hook/skill-body fixes. Next tick uses
   the new code; Claude Code re-reads SKILL.md and scripts on each
   invocation, so no action needed.
2. **`/rabbit-refresh`** invoked by the loop itself — when the merged PR
   touches `.claude/features/policy/*.md` or generated `CLAUDE.md`.
   Re-injects policy into context.
3. **Restart-required HANDOFF** — when the merged PR touches
   `settings.json`, adds a brand-new skill, or modifies a hook in a way
   that changes the system-prompt-pinned surface. The loop completes the
   merge + tag, writes `.rabbit-auto-evolve-restart-needed` with the
   reason, posts a Stop rabbit_subline `restart Claude, then
   /rabbit-auto-evolve start to resume`, and does **not** schedule the
   next wake-up. On next SessionStart the banner surfaces the resume
   command.

Classification is deterministic — done by
`scripts/classify-merge-restart.py` inspecting the merged PR's file list
against three globs. Easy to test, easy to extend.

## 8. Banner customization (SessionStart and Stop)

When auto-evolve mode is active (marker `.rabbit-auto-evolve-active`
present), the existing per-configurable alerts for `human-approval=false`
and `bypass-permissions=true` are **suppressed**, replaced by a single
composite banner from rabbit-auto-evolve.

Mechanism (does not touch rabbit-cage internals):

1. `feature.json` declares a new RUNTIME api `emit_auto_evolve_banner`
   on SessionStart and `emit_auto_evolve_stop_line` on Stop. Both live in
   `contract.lib.runtime` — small additive extension owned by `contract`.
2. `iterate_configurables_alerts` and `iterate_configurables_banner`
   (already in `contract.lib.runtime`) check for
   `.rabbit-auto-evolve-active`; when present they skip the two
   underlying alerts (treat them as muted).
3. `emit_auto_evolve_banner` emits two `rabbit_subline` lines on
   SessionStart:
   - Line 1 (red, ✨): `AUTONOMOUS-EVOLVE MODE ACTIVE — loop will dispatch
     TDD subagents and merge to dev without prompts`
   - Line 2 (yellow, ▶): `to start the loop, paste:
     /rabbit-auto-evolve start` — the literal command, copy-pasteable.
   - If `.rabbit-auto-evolve-restart-needed` is present, line 2 is
     replaced with: `resume after restart: paste /rabbit-auto-evolve
     start`.
   - If `.rabbit-auto-evolve-aborted` is present, line 2 is replaced with:
     `loop aborted on safety violation — see
     .rabbit/auto-evolve-state.json and clear marker to resume`.
4. `emit_auto_evolve_stop_line` emits at most one `rabbit_subline` on
   Stop, mutually exclusive among: running, stop-requested,
   restart-needed, aborted.

The suppression rule is the only line that touches
`contract.lib.runtime`; everything else is owned by rabbit-auto-evolve's
own scripts.

## 9. Release, merge, and safety invariants

Per merged PR, `scripts/release-bump.py` reads the merged PR's
`priority:<level>` label and the diff scope to choose the bump:

| Trigger | Bump |
|---|---|
| `priority:low` or `priority:medium` | patch (`X.Y.Z` → `X.Y.Z+1`) |
| `priority:high` or `priority:critical` | minor (`X.Y.Z` → `X.Y+1.0`) |
| Issue body contains `bump:major` directive OR PR touches ≥ N features (default N=3) OR PR touches anything under `.claude/features/contract/schemas/` | major (`X.Y.Z` → `X+1.0.0`) |

The script:

1. Reads current top tag via `git describe --tags --abbrev=0`.
2. Computes the next version per the table.
3. `git tag -a vX.Y.Z -m "<auto-evolve> #<issue> <title>"`.
4. `git push origin vX.Y.Z`.
5. `gh release create vX.Y.Z --notes-from-tag --target dev`.

**Bottom-line invariants** (enforced by `scripts/safety-check.py`, called
at the start of every merge/release phase — abort tick on any failure):

- Current branch is `dev`. Never operates on `main`.
- The PR base branch is `dev`. Never `main`.
- The work branch about to be deleted matches the pattern emitted by
  feature-touch (`feat/<feature>-<issue>` or similar), not `dev` / `main`
  / any release branch.
- Tag does not already exist.
- Working tree is clean.

Any safety violation aborts the tick with a `[🐇 rabbit 🐇]` red alert,
writes a sticky `.rabbit-auto-evolve-aborted` marker (visible on
SessionStart and Stop until cleared), and does not reschedule. The loop
will not resume until the user clears the marker — autonomous mode does
not silently retry safety violations.

## 10. Tests

The feature ships its own `test/run.py` walking every `test-*.py`.
Coverage maps to spec invariants in the standard rabbit format. All
filesystem mutations occur inside `tempfile.TemporaryDirectory()` scopes
(per rabbit-config Inv 17). `gh` calls use the same shim pattern as
rabbit-issue.

| Test | What it locks in |
|---|---|
| `test-set-evolve-mode.py` | `set-evolve-mode.py on` flips all three flags in order and rolls back on simulated failure; `off` reverses |
| `test-banner-suppression.py` | When `.rabbit-auto-evolve-active` is present, the two underlying alerts emit zero lines; the auto-evolve banner emits exactly two |
| `test-triage-rules.py` | Each row of the Section 5 decision table fires deterministically against a synthetic issue corpus |
| `test-plan-batch.py` | Conflict graph coloring is deterministic; contract issues always land in `barrier_first`; `max_parallel` cap is respected |
| `test-release-bump.py` | Each row of the Section 9 bump table maps the right priority/scope to the right semver delta |
| `test-safety-check.py` | Every bottom-line invariant aborts the tick when violated; never aborts on a valid `dev` operation |
| `test-classify-merge-restart.py` | Each rung of the Section 7 refresh ladder fires for the right merged-file pattern |
| `test-tick-skill.py` | SKILL.md documents all twelve phases (0–11) of Section 4 in order, names every script, names the disk-state path |
| `test-start-stop-skill.py` | `start` refuses unless all three preconditions hold; `stop` writes the stop marker; `status` is read-only |
| `test-state-persistence.py` | `update-state.py` writes JSON conforming to a schema; the loop reads it on every tick (round-trip) |
| `test-discovered-issues.py` | HANDOFF with `discovered_issues` triggers `rabbit-issue` filing; `aborted_reason` triggers `blocked-by` labeling on the original |
| `test-prompts-declared.py` | feature.json declares the standard prompts entry for the skill |
| `test-feature-shape.py` | feature.json + spec + contract have version alignment, owner, deprecation_criterion |

## 11. Prerequisites and out of scope

**Hard prerequisites** (file as separate rabbit-issues now; must land
before rabbit-auto-evolve is mergeable):

1. **TDD abort/quit mechanism in tdd-subagent.** Current state machine
   assumes `test-red → impl → test-green`. Auto-evolve needs the subagent
   to be able to abort mid-cycle when it discovers a blocking issue, emit
   a HANDOFF with `aborted_reason` + `discovered_issues`, and leave the
   feature unlocked. Owner: `tdd-subagent`.
2. **HANDOFF schema extension.** Add optional fields
   `discovered_issues: [{title, body, labels}]` and
   `aborted_reason: string` to the TDD subagent HANDOFF contract. Owner:
   `tdd-subagent` (contract change → `feature:contract` issue too).
3. **`emit_auto_evolve_banner` and the suppression rule in
   `contract.lib.runtime`.** Additive change to
   `iterate_configurables_alerts` / `iterate_configurables_banner` to
   mute the two underlying alerts when the auto-evolve marker is present.
   Owner: `contract`.

**Out of scope v1:**

- File-overlap conflict detection beyond same-feature. The v1 conflict
  edge is "same `feature:<name>` label". Glob-based file overlap is a
  future extension.
- Cross-tracker support — only `gh` issues, matching rabbit-issue's scope.
- A web dashboard or HTML report. The `status` subcommand prints plain
  text.
- Auto-merging PRs that fail CI. The loop calls `gh pr merge --auto`
  (waits for green); if checks fail, the loop posts a `ci-red` label and
  moves on. The failed PR re-enters the queue on the next tick via triage
  (which will likely defer it as `needs-judgment`).
- Modifying `main` in any way, ever. Hard invariant in `safety-check.py`.
- Working human-filed (non-`rabbit-managed`) issues. The fetch step
  filters to `label:rabbit-managed`. Matches rabbit-issue's existing
  safety invariant.

**Deprecation criterion:** when Claude Code (or rabbit) gains a native
always-on autonomous-agent mode that supersedes this skill.

**Initial version:** `0.1.0`. The feature is `status: active` once the
test suite is green.
