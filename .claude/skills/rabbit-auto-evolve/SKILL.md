---
name: rabbit-auto-evolve
version: 0.17.0
owner: rabbit-workflow team
deprecation_criterion: when Claude Code or rabbit gains a native always-on autonomous-agent mode that supersedes this skill
description: Self-driving rabbit loop that continuously fetches open `rabbit-managed` GitHub issues, triages each one, dispatches TDD subagents to implement actionable work, merges approved PRs into `dev`, tags versioned releases, and reschedules itself via `ScheduleWakeup` until the user issues an explicit stop. Invoke for any natural-language phrasing matching "start auto-evolve", "stop the loop", "auto-evolve status", "let rabbit run", "begin autonomous evolve", or any `/rabbit-auto-evolve <subcommand>` form. Invoking `start` from a fresh state auto-routes to `on` and prompts for a Claude restart — no need to run `on` manually first.
---

# rabbit-auto-evolve

A self-driving rabbit loop. Continuously fetches open `rabbit-managed`
issues, triages each, dispatches TDD subagents, merges approved PRs into
`dev`, tags releases, and re-schedules itself via `ScheduleWakeup` until
the user issues an explicit stop.

The mode is entered via `/rabbit-auto-evolve on` (compound mutator
`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py on`);
exited via `/rabbit-auto-evolve off`. Both transitions require a Claude
restart so the new `permissions.defaultMode` in
`.claude/settings.local.json` takes effect.

## Subcommands

### `on`

Activate auto-evolve mode. Invokes
`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py on`,
which performs three deterministic mutations in order:

1. Write `.rabbit-human-approval-bypass` (flips `human-approval` off).
2. Set `permissions.defaultMode: "bypassPermissions"` in
   `.claude/settings.local.json` (flips `bypass-permissions` on).
3. Write `.rabbit-auto-evolve-active` (signals mode is on).

On success, the script emits two branded `rabbit_print` confirmation
lines to stdout (red `AUTONOMOUS-EVOLVE MODE CONFIGURED — restart Claude
Code to activate`; yellow `After restart, run: /rabbit-auto-evolve
start`). Surface the script's stdout verbatim to the user — do NOT
paraphrase. The message text lives in the script so it stays centralized
(per spec Inv 1 v0.7.4).

### `start`

Begin or resume the loop. Per Inv 21, precondition reporting is owned by
`check-preconditions.py` — invoke it (it always exits 0) and route on the
JSON report shape. Bare `ls .rabbit-auto-evolve-*` patterns are
FORBIDDEN here: they emit ugly `ls: cannot access ...: No such file or
directory` stderr noise on fresh clones where the markers legitimately do
not yet exist.

```
python3 .claude/features/rabbit-auto-evolve/scripts/check-preconditions.py
```

The script reports on the three preconditions as structured JSON:

1. `active-marker` — `.rabbit-auto-evolve-active` marker exists at repo
   root.
2. `approval-bypass` — `human-approval` is off (i.e.
   `.rabbit-human-approval-bypass` present).
3. `bypass-permissions` — `bypass-permissions` is on (i.e.
   `.claude/settings.local.json` has
   `permissions.defaultMode == "bypassPermissions"`).

#### Routing table (per Inv 10, v0.7.7 — issue #386)

Route on the report's `all_pass` field AND the per-check `ok` values.
NEVER dump the raw failing checklist as the sole user response — the
user already expressed intent ("enter auto-evolve mode") by invoking
`start`. The routing branches below are exhaustive:

| Report shape | Action |
|---|---|
| `all_pass: true` | Proceed to start the loop (see "Start the loop" below). |
| `all_pass: false` AND `active-marker` check `ok: false` (fresh state — user never ran `on`) | **Automatically invoke `/rabbit-auto-evolve on`** to run the three activation mutations (Inv 1). The script emits its branded restart prompt; surface that stdout verbatim and end the turn. The user restarts Claude, then runs `start` again. Do NOT show the failing-checklist; do NOT ask for permission — the natural-language intent is sufficient consent. |
| `all_pass: false` AND `active-marker` check `ok: true` AND `bypass-permissions` check `ok: false` (markers exist but user forgot to restart Claude after a previous `on`) | Surface ONE short branded reminder line: `🔁 Markers set — restart Claude Code, then /rabbit-auto-evolve start again`. Do NOT re-run `on` (the markers are already correct). Do NOT show the full checklist. |
| Any other `all_pass: false` shape (genuinely unexpected — partial corruption, manual tampering) | Surface the failing `checks[*].detail` strings as actionable guidance and STOP. This is the fallback branch only — the two routing branches above cover the common fresh-state and forgot-to-restart cases. |

The auto-on routing on fresh state was introduced by issue #386 in
v0.7.7: in v0.7.6 the skill fragmented a single user intent ("enter
auto-evolve mode") into a two-step manual flow by surfacing the
precondition checklist verbatim and waiting for the user to type
`/rabbit-auto-evolve on` themselves.

#### Start the loop (only on `all_pass: true`)

1. Invoke
   `python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py`
   (which writes `.rabbit-auto-evolve-running` at repo root). Per Inv 17
   the marker write is wrapped in a script so scope-guard does not deny
   the literal Bash command. Per Inv 19, `start-loop.py` additionally
   self-heals before writing the running marker: it deletes any stale
   `.rabbit-auto-evolve-stop-requested` (an explicit `start` cancels a
   pending stop) and bootstraps `.rabbit/auto-evolve-state.json` with
   defaults if it is missing, empty, or malformed (a valid existing
   state file is left untouched).
2. Run one `tick` (the 12-phase loop body).
3. Call `ScheduleWakeup` to chain the next tick.

### `stop`

Invoke `python3 .claude/features/rabbit-auto-evolve/scripts/stop-loop.py`
(which writes `.rabbit-auto-evolve-stop-requested` at repo root). The
next tick's phase 0 (`stop-check`) observes the marker, posts a one-line
run summary, and does NOT call `ScheduleWakeup`. The loop then halts
cleanly. Per Inv 17 the marker write is wrapped in a script for the
same scope-guard reason as `start`.

### `status`

`status` is read-only (performs no mutations). Per Inv 29 (issue #405), the
status report is owned by
`status-report.py` — invoke it and surface its stdout. Do NOT LLM-assemble
a bash pipeline; bare `ls .rabbit-auto-evolve-*` / `cat
.rabbit/auto-evolve-state.json` patterns are FORBIDDEN here (they drift
and emit ugly `ls: cannot access ...: No such file or directory` stderr
noise on a fresh clone where the state file and markers legitimately do
not yet exist).

```
python3 .claude/features/rabbit-auto-evolve/scripts/status-report.py
```

The script emits a fixed-format JSON object on stdout (always exits 0
except on a genuine invocation error):

- `queue_length` — queue length (from `.rabbit/auto-evolve-state.json`
  `queue` field)
- `in_flight` — in-flight issue set (from `in_flight`)
- `last_merged_sha` — last-merged PR (from `last_merged_sha`)
- `last_tagged_version` — last-tagged version (from `last_tagged_version`)
- `consecutive_failures` — consecutive-failure count (from
  `consecutive_failures`)
- `markers_present` — the sorted subset of the five runtime markers
  present at the repo root (`.rabbit-auto-evolve-active`,
  `.rabbit-auto-evolve-running`, `.rabbit-auto-evolve-stop-requested`,
  `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`)
- `state_file` — `present` / `absent` / `malformed`; a missing or
  malformed state file is the legitimate fresh-clone case and yields the
  default field values, NOT an error.

`status` performs no mutations.

### `tick` (internal)

Invoked only by `ScheduleWakeup`. Walks 12 phases in order. Any phase MAY
abort the tick early without affecting the next tick's ability to pick up
from disk-persisted state in `.rabbit/auto-evolve-state.json`.

| # | Phase             | Script(s) invoked                            |
|---|-------------------|----------------------------------------------|
| 0 | `stop-check`      | (none — file existence check on `.rabbit-auto-evolve-stop-requested`) |
| 1 | `restart-check`   | (none — file existence check on `.rabbit-auto-evolve-restart-needed`) |
| 2 | `fetch`           | `.claude/features/rabbit-auto-evolve/scripts/fetch-queue.py` |
| 3 | `triage`          | `.claude/features/rabbit-auto-evolve/scripts/triage-batch.py` (wraps `.claude/features/rabbit-auto-evolve/scripts/triage-issue.py` per issue) |
| 4 | `plan`            | `.claude/features/rabbit-auto-evolve/scripts/plan-batch.py` |
| 5 | `dispatch`        | (rabbit-feature-touch — TDD subagent dispatch) |
| 6 | `merge`           | `.claude/features/rabbit-auto-evolve/scripts/merge-prs.py` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase merge` |
| 7 | `release`         | `.claude/features/rabbit-auto-evolve/scripts/release-bump.py` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase release --next-tag vX.Y.Z` |
| 8 | `cleanup`         | `.claude/features/rabbit-auto-evolve/scripts/cleanup-branches.py` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase cleanup` |
| 9 | `catch-up`        | `.claude/features/rabbit-auto-evolve/scripts/classify-merge-restart.py` (per merged PR) |
|10 | `persist`         | `.claude/features/rabbit-auto-evolve/scripts/update-state.py` writes `.rabbit/auto-evolve-state.json` |
|11 | `schedule`        | `ScheduleWakeup` (unless stop-check matched) |

### Tick exit invariant (Inv 20)

Per spec Inv 20, EVERY tick exit path MUST end by invoking
`python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py` as its
last action. `end-tick.py` deletes the `.rabbit-auto-evolve-running`
marker (mirror of `start-loop.py`'s write); without it the marker leaks
across sessions and the user has to remove it manually (which scope-guard
correctly denies, since `.rabbit-auto-evolve-*` markers are not on its
allowlist).

The four named exit paths are:

- **normal completion** — phase 11 (`schedule`) finishes, then
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`
  runs, then `ScheduleWakeup` chains the next tick.
- **phase 0 halt** — `.rabbit-auto-evolve-stop-requested` observed at
  the top of the tick. Post the run summary, then run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`,
  then end the turn (no `ScheduleWakeup`).
- **safety abort** — any safety violation during phases 6–8 writes
  `.rabbit-auto-evolve-aborted` via
  `python3 .claude/features/rabbit-auto-evolve/scripts/mark-aborted.py "<reason>"`.
  Immediately after, run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`
  and end the turn (no `ScheduleWakeup`).
- **error abort** — an unexpected exception in any phase. Run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`
  in the error-handler tail before ending the turn.

`end-tick.py` is idempotent: re-invoking when the marker is already
absent is a clean no-op (exit 0).

Phases 2–4 form the canonical fetch → triage → plan pipe (per Inv 18):

```
python3 .claude/features/rabbit-auto-evolve/scripts/fetch-queue.py \
  | python3 .claude/features/rabbit-auto-evolve/scripts/triage-batch.py \
  | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py --max-parallel 4
```

`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py` is NOT
invoked by `tick` — it runs only when the user flips the mode via
`/rabbit-auto-evolve on|off`.

### Dispatch shape selection (Stage 1 / Stage 2 — Inv 26)

Phase 4 (`plan`) emits TWO decoupled outputs the dispatcher consumes in
phase 5:

- `selection_order` — **Stage 1, dispatch-shape blind.** The order to work
  items in, by the composite key `(priority desc, contract_touch desc,
  issue asc)` (issue #479): priority is PRIMARY, the contract-touch barrier
  is the SECONDARY tiebreak (contract items lead WITHIN a priority tier,
  never across tiers), issue asc is the final tiebreak. The same key drives
  `barrier_first`, so the two agree. It NEVER consults dispatch shape,
  feature count, or "knows how": a high-priority cross-feature item is
  selected before a low-priority single-feature item, and a critical
  non-contract item beats a low-priority contract item.
- `dispatch_shapes` — **Stage 2, item-shaped.** A map of issue-number-string
  → one of exactly THREE shapes. Per item, pick the FIRST that fits:

  | Rank | Shape | When | Mechanics |
  |---|---|---|---|
  | 1 (perf preference) | `parallel-per-feature` | item edits exactly one feature dir | one full single-feature TDD touch (its own `.rabbit-scope-active-<feature>` marker); multiple such items dispatch in parallel |
  | 2 | `multi-subagent-barrier` | item edits >1 feature dir, below the decompose threshold | per-feature subagents land SERIALLY on ONE shared branch; subagent k+1 fetches subagent k's pushed commit before starting; each piece is a full single-feature touch with its own scope marker; one PR closes the item |
  | 3 | `decomposition` | item edits ≥ `--decompose-threshold` feature dirs (default 10) | file N per-feature sub-issues via `python3 .claude/features/rabbit-issue/scripts/file-item.py …` (a contract INVOKE, not a cross-feature edit), each labelled `rabbit-managed` + the right `feature:<name>` label; keep the parent OPEN and queue the sub-issues, which re-enter Stage 1/Stage 2 on the next tick |

  `parallel-per-feature` is the **performance preference, not a correctness
  requirement** — items that don't fit it still get done via shape 2 or 3,
  just slower. The dispatcher MUST NOT skip, defer indefinitely, or escalate
  an item merely because it doesn't fit shape 1.

  The struck shape ("sequential single-subagent with a persistent
  `.rabbit-scope-override session`") is NEVER used. Autonomous-evolve ALWAYS
  uses a full per-feature touch gated by `.rabbit-scope-active-<feature>`; it
  NEVER writes a persistent `.rabbit-scope-override session` for feature
  edits. Bounded scope is a hard constraint, not waivable by autonomy
  (maintainer policy on issue #435). A one-time override is permitted ONLY
  for plan / temporary-document writing — never for feature code edits.

### Worktree isolation for TDD dispatches (Inv 28 — issue #430)

**Every Agent call for a TDD-subagent dispatch in phase 5 MUST include
`isolation: "worktree"`.** This is a DISPATCHER policy, not a subagent
policy — the dispatcher requests the isolated worktree on the Agent call;
the subagent itself is isolation-agnostic.

Without isolation, parallel TDD subagents share the dispatcher's single
shared git working directory: one subagent's branch checkout reverts
another's edits, commits land on the wrong branch, and each subagent's
`.rabbit-scope-active-<feature>` marker clobbers the others' (observed:
3 of 4 parallel dispatches in one tick collided). `isolation: "worktree"`
gives each dispatch its own working tree, branch, HEAD, and scope marker,
so both the parallel shape (`parallel-per-feature`) and the
serial-on-one-branch shape (`multi-subagent-barrier`) stay collision-free.

Worktrees are created branched from `dev` HEAD (NOT `main`, NOT a fresh
tree) per the `worktree.baseRef: "head"` setting in
`.claude/settings.local.json`. This requirement formalizes an
already-manual practice — the maintainer has been passing
`isolation: "worktree"` by hand on every dispatch; issue #430 makes it a
binding invariant.

**Known limitation (stale base):** `worktree.baseRef: "head"` requires a
session restart to take effect; until the session has been restarted after
the setting landed, a newly created worktree may branch from a stale base
and a subagent may need to re-branch from `origin/dev` manually at the
start of its cycle. This is a Claude Code worktree-harness limitation, not
a feature defect; it resolves on the next session restart.

### `off`

Deactivate auto-evolve mode. Invokes
`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py off`,
which performs a FULL teardown — the four loop-runtime markers first
(innermost first, idempotent), then the three `on` mutations in inverse
order:

1. Delete any of the four loop-runtime markers if present
   (`.rabbit-auto-evolve-running`, `.rabbit-auto-evolve-stop-requested`,
   `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`).
2. Delete `.rabbit-auto-evolve-active`.
3. Delete the `permissions.defaultMode` key from
   `.claude/settings.local.json`.
4. Delete `.rabbit-human-approval-bypass`.

On success, the script emits one branded `rabbit_print` confirmation
line to stdout (green `Autonomous-evolve mode deactivated — full
teardown complete`). Surface the script's stdout verbatim to the user
— do NOT paraphrase (per spec Inv 1 v0.7.4).

A Claude restart is required so the cleared `permissions.defaultMode`
takes effect.

Disk-persisted state lives at `.rabbit/auto-evolve-state.json`, schema
`scripts/schemas/auto-evolve-state.schema.json` (v1.0.0).

## Discovered issues and aborted_reason handling

The TDD subagent HANDOFF carries two optional fields the loop reacts to
during phase 5 (`dispatch`) result processing:

- `discovered_issues` — array of `{title, body, labels}` objects. The loop
  files each via `rabbit-issue` (script
  `python3 .claude/features/rabbit-issue/scripts/file-item.py …`) with the
  `rabbit-managed` label so the next tick's `fetch` phase picks them up.
- `aborted_reason` — non-null string. The loop adds a `blocked-by:#N`
  label to the original issue (where `N` is the discovered blocker if
  available, else the dispatch retains the existing reason) and leaves
  the issue OPEN so a future tick may retry.

## Markers (control flow)

| Marker (repo root)                          | Meaning                                  |
|---------------------------------------------|------------------------------------------|
| `.rabbit-auto-evolve-active`                | mode is on; suppresses per-configurable alerts |
| `.rabbit-auto-evolve-running`               | a tick is currently dispatching          |
| `.rabbit-auto-evolve-stop-requested`        | graceful stop pending for next tick      |
| `.rabbit-auto-evolve-restart-needed`        | catch-up rung requires Claude restart    |
| `.rabbit-auto-evolve-aborted`               | safety violation; loop will not resume   |

## Red Flags — STOP

**While `.rabbit-auto-evolve-running` is present, the dispatcher MUST NOT emit `AskUserQuestion` calls.**

The user has affirmatively delegated authority by entering auto-evolve
mode; routine "should I continue?" prompts are forbidden. On a genuine
hard blocker (test failure with no obvious fix, safety violation, spec
ambiguity not covered by resolved Open Questions), the dispatcher writes
`.rabbit-auto-evolve-aborted` with the abort reason and ends the turn
without calling `ScheduleWakeup`. The next SessionStart banner surfaces
the abort to the user.

Other red flags:

- Never call `gh pr merge` on a PR whose base is not `dev`.
- Never delete a branch not matching `^feat/.+`.
- Never create a tag that already exists.
- Never merge when the working tree is dirty.
- Never write a persistent `.rabbit-scope-override session` for feature
  edits. Cross-feature work is handled by `decomposition` or
  `multi-subagent-barrier` (Inv 26) — every write stays inside one feature's
  `.rabbit-scope-active-<feature>` scope.
- Never dispatch a TDD subagent without `isolation: "worktree"` on the
  Agent call (Inv 28) — parallel dispatches sharing one working tree
  collide on branch, HEAD, commits, and scope markers.

`safety-check.py` enforces these; `merge-prs.py` and
`cleanup-branches.py` also refuse defense-in-depth.
