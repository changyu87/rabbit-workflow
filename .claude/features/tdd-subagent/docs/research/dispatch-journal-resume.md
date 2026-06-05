---
feature: tdd-subagent
version: 1.0.0
owner: rabbit-workflow team
deprecation_criterion: when a rabbit-native dispatch journal is implemented (the impl follow-up referenced in this change's CHANGELOG entry) and this research record folds into that touch's CHANGELOG, OR when Claude Code exposes a native cross-tick resumable orchestration mechanism that supersedes rabbit's across-tick loop lifecycle
status: accepted
---

# Research: can tdd-subagent dispatch adopt a journal/resume mechanism?

## Status

Accepted. This is the written deliverable of the journal/resume research
spike: study whether rabbit's tdd-subagent dispatch can adopt a
journal/resume mechanism (crash-resumable, cached, idempotent fan-out) to
strengthen the loop, WITHOUT moving the across-tick loop lifecycle onto the
native Workflow tool.

## Verdict

**CAN.** A rabbit-native, on-disk per-tick dispatch journal is feasible and
worth building. It closes a real recovery gap in today's fan-out without
ceding any governance guarantee and without depending on native Workflow's
single-invocation journal. The exact plan, schema, and resume algorithm are
below. The implementation is filed as a separate work item against
rabbit-auto-evolve (the feature that owns dispatch state) — see this change's
CHANGELOG entry and PR for the issue number.

The verdict is explicitly scoped: the journal lives entirely in rabbit's
governance/orchestration tier as an on-disk artifact the dispatcher writes
and re-reads. It does NOT move the across-tick loop lifecycle onto native
Workflow. The native-Workflow coexistence decision (contract's
`docs/decisions/native-workflow-coexistence.md`) recorded HYBRID / COEXIST
and noted native Workflow's journaled resume as a NATIVE-ONLY primitive and a
"possible future borrow"; that decision's single-invocation conflict still
stands. This spike borrows the IDEA of a journal, re-homed as a rabbit-native
on-disk record, not the native mechanism.

## Context

The autonomous-evolve loop fans out N TDD subagents in Phase 6 (`dispatch`),
each in an isolated git worktree (Inv 28). A tick can be interrupted after K
of N subagents finish — by a context/scale cutoff, a scheduler kill, or a
crash. The question is whether the NEXT tick can resume the remaining N-K
without re-running the K completed and without losing or duplicating work.

## What the code actually does today

This section is grounded in the live recovery machinery, not in prose intent.

### How a tick fans out and recovers, end to end

1. **Re-fetch each tick.** `fetch-queue.py` runs `gh issue list --state open`
   and selects OPEN issues carrying both a `feature:<name>` and a
   `priority:<level>` label (the actionability basis, Inv 2). Selection is
   purely actionability-based; it reads NO local dispatch state.
2. **Plan.** `plan-batch.py --max-parallel 4` emits `selection_order` (Stage
   1, dispatch-shape blind) and `dispatch_shapes` (Stage 2, per-item shape:
   `parallel-per-feature`, `multi-subagent-barrier`, or `decomposition`).
3. **Dispatch (Phase 6).** The dispatcher hand-drives the only Claude-needing
   phase: it issues one `Agent(... isolation: "worktree")` call per planned
   item. There is NO script that records, per dispatched subagent, its
   branch, PR, worktree, or completion state at dispatch time.
4. **Merge + close (Phase 7).** `merge-prs.py --record-pending` squash-merges
   ready PRs, then parses each merged PR body for `Closes/Fixes/Resolves #N`
   and closes those issues via `item-status.py close --reason completed
   --commit-sha <sha>`. Merged PR numbers are appended to
   `pending_post_merge` in `.rabbit/auto-evolve-state.json`.
5. **Post-merge drain (phases 8-10).** `run-post-merge.py` reads
   `pending_post_merge` and runs release -> cleanup -> catch-up per PR, then
   clears the list. On any phase failure the list is NOT cleared, so the next
   tick's tick-start drain (phase 2) retries the owed work.
6. **Leak cleanup (Phase 7, FIRST).** `clean-dispatch-leaks.py` restores a
   leaked main-HEAD branch switch to `dev` (Inv 44), removes stray untracked
   `.rabbit-scope-active-*` markers, and reverts bookkeeping-only
   `feature.json` edits a worktree dispatch leaked into the main tree (Inv
   43) — failing loudly on any unexpected tracked change.
7. **Orphan sweep (pre-dispatch).** `prune-worktrees.py` force-removes every
   `.claude/worktrees/agent-*` worktree at tick start, on the reasoning that
   the running-guard already proved no other tick is live and Phase 6 has not
   begun, so every existing worktree is an orphan from a prior or interrupted
   tick (Inv 49).

### The de-facto journal today: GitHub issue open/closed state

The system already has an implicit, externally-hosted journal: the OPEN set
of actionable issues on GitHub.

- A subagent that COMPLETED merges its PR; `merge-prs.py` closes the
  referenced issue; the next `fetch-queue.py` no longer surfaces it.
- A subagent that DID NOT complete leaves its issue open (no merged PR); the
  next tick re-fetches and re-dispatches it.

This delivers a weak form of resume: completed work is not re-run (its issue
is closed), and unfinished work is retried (its issue stays open). But it is
coarse and externally hosted, with concrete gaps (next section).

### The `in_flight` field is vestigial

`in_flight` is declared required in `auto-evolve-state.schema.json`,
initialized to `[]` by `start-loop.py`, and validated for shape by
`update-state.py`. It is surfaced read-only by `status-report.py` and
`log-tick.py`. **No phase script ever writes dispatched issue numbers into
it, and `fetch-queue.py` does not consult it to exclude in-flight issues.**
It is observability scaffolding, not a live recovery mechanism — a journal
would supersede it outright.

## Gaps versus a true journal

| Gap | Today | With a journal |
| --- | --- | --- |
| In-flight visibility | `in_flight` never populated; no local record of what was dispatched this tick | journal records each dispatch (issue, feature, branch, worktree, shape, status) at dispatch time |
| Distinguish "dispatched, PR open, awaiting merge" from "never dispatched" | impossible locally — both look like an open issue, so a resumed tick may RE-dispatch an issue whose PR is already open | journal marks the issue `dispatched` with its PR; resume skips it (PR drains via merge, not re-dispatch) |
| Duplicate-dispatch risk on resume | a re-fetched still-open issue whose first dispatch produced an un-merged PR can be dispatched a SECOND time, racing two branches/PRs for one issue | journal-keyed idempotency: an issue already `dispatched`/`pr_open` this cycle is not re-dispatched |
| Worktree -> issue linkage | none; `prune-worktrees.py` force-removes ALL worktrees at tick start, discarding any in-progress isolated work from a crashed mid-tick | journal links worktree to issue/branch, enabling a future targeted resume instead of blanket prune |
| Resume granularity | whole-tick: the next tick re-derives the entire queue from GitHub | per-subagent: skip the K completed, re-dispatch only the N-K unfinished, from a local record |

## Adoption options

### (a) Native Workflow journal for within-tick fan-out — REJECTED

Native Workflow ships resume-from-journal. But adopting it for the loop's
fan-out is blocked on two grounds:

- **Single-invocation conflict (the COEXIST verdict).** Native Workflow is a
  single-invocation orchestration: one `Workflow` run drives its phases and
  resumes its OWN journal within that run. Rabbit's loop lifecycle is
  ACROSS-tick — each tick is a separate headless/in-session invocation fired
  by a scheduler, with state handed off on disk between invocations. Moving
  the across-tick lifecycle onto a native single-invocation journal is exactly
  the conflict the coexistence decision declined; that decision still stands.
- **Host constraints.** This is a genie-wrapped host where `claude` is not on
  `PATH` and the loop self-ticks via a durable `CronCreate` heartbeat, with
  trigger constraints. Betting the loop's recovery on a brand-new native
  harness primitive (a moving target, per the coexistence decision) trades
  rabbit's locatable-failure guarantee (`script > CLI > spec > prompt`) for
  upstream churn risk.

A native journal could still help WITHIN a single tick's fan-out (one
invocation orchestrating N agents), but that is a narrower win than the
across-tick gap this spike targets, and it would couple Phase 6 to native
Workflow. Not worth it now.

### (b) A rabbit-native dispatch journal — CHOSEN

An on-disk, per-tick dispatch record the dispatcher writes at Phase 6 and
re-reads on re-entry. Fully in rabbit's governance/orchestration tier:
deterministic, locatable, owned by rabbit-auto-evolve dispatch state, with no
dependency on native Workflow. This directly closes the gaps above.

### (c) Hybrid / not-worth-it

A hybrid (native within-tick + rabbit across-tick) doubles the recovery
surface for a marginal within-tick gain and reintroduces the native coupling
(a) rejects. Not chosen.

## Recommendation

Build option (b): a rabbit-native dispatch journal. Adopt nothing from native
Workflow. The implementation is a SEPARATE work item against rabbit-auto-evolve
(it owns dispatch state and the `.rabbit/auto-evolve-state.json` schema); see
this change's CHANGELOG entry and PR for the issue number.

## Exact plan

### Journal schema (additive to the state file)

Add a `dispatch_journal` object to `.rabbit/auto-evolve-state.json`, gated by
a `schema_version` bump (additive, so a minor bump per the schema's semantic
convention). Keyed by tick id; value records every subagent dispatched that
tick:

```
"dispatch_journal": {
  "<tick_id>": {
    "started_at": "2026-06-04T12:00:00Z",
    "entries": [
      {
        "issue": 815,
        "feature": "rabbit-housekeep",
        "shape": "parallel-per-feature",
        "branch": "feat/815-...",
        "worktree": ".claude/worktrees/agent-...",
        "pr": 820,
        "status": "completed"
      }
    ]
  }
}
```

`status` is a small fixed enum: `dispatched` (Agent issued, no result yet),
`pr_open` (subagent returned a PR, not yet merged), `completed` (PR merged /
issue closed), `aborted` (subagent aborted; carries the HANDOFF
`aborted_reason`). All fields except `issue`/`feature`/`shape`/`status` are
nullable (a dispatch may be recorded before its branch/PR exist). The block
is OPTIONAL and additive: a state file without it behaves exactly as today.

### Where written and read

- **Written** by a new `record-dispatch.py` (sibling of `merge-prs.py`),
  invoked by the dispatcher at Phase 6: one append per Agent call at dispatch
  time (`status: dispatched`), and one update when each HANDOFF returns
  (`pr_open`/`aborted`, recording branch/PR). This keeps the SKILL.md body
  free of computed-value bash (the Script-Backed Orchestration rule): the
  SKILL invokes the script; the script owns the read-modify-write.
- **Promoted to `completed`** by `merge-prs.py` in the SAME read-modify-write
  that today appends to `pending_post_merge`: when a PR merges, mark its
  journal entry `completed`. No new write site.
- **Read** at tick start by a new `resume-dispatch.py` consulted in the
  pre-dispatch segment (alongside the running-guard): it returns the set of
  issues already `dispatched`/`pr_open`/`completed` for the current cycle so
  the dispatcher's Phase 6 skips them and re-dispatches only the unfinished.

### How resume skips completed subagents

On re-entry, `resume-dispatch.py` reads the journal for the active cycle and
partitions the re-fetched actionable queue:

- issue marked `completed` -> SKIP (its PR merged; nothing to do).
- issue marked `pr_open` -> SKIP dispatch; the open PR drains through the
  normal merge path (Phase 7), not a second dispatch.
- issue marked `dispatched` but with a stale/absent worktree and no PR ->
  RE-dispatch (the prior dispatch was interrupted before producing a PR).
- issue absent from the journal -> dispatch normally (never seen this cycle).

This converts whole-tick re-derivation into per-subagent resume: the K
completed are skipped from a local record, only the N-K unfinished are
re-dispatched, and an issue whose first dispatch already produced an open PR
is never raced by a duplicate dispatch.

### Interaction with `in_flight` / `pending_post_merge` / leak-cleanup

- **`in_flight`** — SUBSUMED. The journal's `dispatched`/`pr_open` entries are
  the real in-flight set the vestigial field never carried. The field is
  retired in the same change (drop it from the schema's required set, or
  derive it as a read-only projection of the journal for `status-report.py`),
  closing the dead-field gap this research surfaced.
- **`pending_post_merge`** — UNCHANGED, complementary. It tracks OWED
  post-merge work (phases 8-10) for already-merged PRs; the journal tracks
  DISPATCH lifecycle up to merge. They meet at the `completed` transition
  (one read-modify-write in `merge-prs.py` updates both). No duplication.
- **`clean-dispatch-leaks.py`** — UNCHANGED. It cleans main-tree NOISE from
  worktree dispatches (stray markers, leaked HEAD switch, bookkeeping-only
  `feature.json` edits). That is orthogonal to dispatch bookkeeping; the
  journal does not replace it. A future enhancement MAY let the journal's
  worktree linkage make `prune-worktrees.py` resume-aware instead of blanket
  force-removing all worktrees, but that is out of scope for the first cut.

### Cycle identity and journal lifecycle

A "cycle" is the work span for a queue snapshot; a natural cycle id is the
state's `last_merged_sha` plus a monotonic tick counter, or simply the tick's
start timestamp. The journal is pruned by `run-post-merge.py` when a cycle's
entries are all `completed`/`aborted` (the same place that clears
`pending_post_merge`), bounding its on-disk growth — satisfying the
designed-deprecation requirement that the artifact has an explicit
end-of-life.

## Way IN (adoption trigger)

Build the journal now: the impl follow-up issue (see CHANGELOG/PR) is the
trigger. Adopt the native-Workflow journal ONLY if a future native release
exposes a CROSS-tick resumable orchestration mechanism that supersedes
rabbit's across-tick loop lifecycle AND carries rabbit's governance
guarantees — the same governance-superseding bar the coexistence decision
set. That is not today's native Workflow.

## Way OUT (off-ramp / rollback)

The journal block is OPTIONAL and additive. To roll back: stop writing it
(make `record-dispatch.py` a no-op) and remove the `resume-dispatch.py`
consult from the pre-dispatch segment; the loop reverts to today's behavior
(re-fetch each tick, GitHub open-state as the de-facto journal,
`pending_post_merge` + leak-cleanup unchanged). No data is lost because the
authoritative recovery source — open issues on GitHub — is unchanged; the
journal is a local accelerant, not a new source of truth. The retired
`in_flight` field can be reinstated as `[]` if a consumer still expects it.
The trigger to exercise the off-ramp: the journal's read-modify-write proves
a contention or correctness hazard in the loop, or a native cross-tick
mechanism makes it redundant.

## Follow-up

A separate implementation enhancement against rabbit-auto-evolve captures the
build (journal schema, `record-dispatch.py` / `resume-dispatch.py`, the
`merge-prs.py` `completed` transition, the `in_flight` retirement, and the
journal pruning). See the follow-up issue referenced in this change's
CHANGELOG entry and PR.
