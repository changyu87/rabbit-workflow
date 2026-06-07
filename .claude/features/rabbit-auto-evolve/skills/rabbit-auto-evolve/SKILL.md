---
name: rabbit-auto-evolve
version: 0.86.1
owner: rabbit-workflow team
deprecation_criterion: when Claude Code or rabbit gains a native always-on autonomous-agent mode that supersedes this skill
description: Self-driving rabbit loop that continuously fetches open actionable GitHub issues (valid `feature:` + `priority:` label), triages each one, dispatches TDD subagents to implement actionable work, merges approved PRs into `dev`, tags versioned releases, and is fired on a fixed cadence by a system cron (installed at `on`) until the user issues an explicit stop. Invoke for any natural-language phrasing matching "start auto-evolve", "stop the loop", "auto-evolve status", "let rabbit run", "begin autonomous evolve", "enter auto evolve mode" / "enter auto-evolve mode" (the unhyphenated "auto evolve" spelling counts too), "turn on autonomous evolve" / "enable autonomous evolve", "resume the loop", or any `/rabbit-auto-evolve <subcommand>` form. Invoking `start` from a fresh state auto-routes to `on` and prompts for a Claude restart — no need to run `on` manually first.
---

# rabbit-auto-evolve

A self-driving rabbit loop. Continuously fetches open ACTIONABLE issues
(valid `feature:` + `priority:` label — the actionability selection basis,
Inv 2),
triages each, dispatches TDD subagents, merges approved PRs into
`dev`, tags releases, and is fired on a fixed cadence by a **system cron**
(the tick scheduler where available, installed at `on`) until the user
issues an explicit stop. Per Inv 32 the loop NEVER self-chains via the
deprecated in-session wakeup mechanisms (see spec Inv 32 for the forbidden
set). Scheduling lives in the external system cron
WHERE AVAILABLE; on hosts where crontab is blocked, a durable `CronCreate`
heartbeat is the SANCTIONED fallback trigger (a Claude idle-REPL prompt
scheduler — durable, not an in-session wakeup harness). When work remains at
the end of a tick the loop refires near-immediately (Inv 33); when the queue
is empty it relies on the heartbeat. The refired tick gets a FRESH context
ONLY on the system-cron / headless path (a brand-new Claude-free process);
on the `CronCreate` fallback the prompt re-enters the SAME live session, so
context is REUSED and ACCUMULATES across ticks, bounded by auto-compaction —
NOT a fresh context (Inv 33).

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

1. Write `.rabbit-human-approval-bypass` AND the new
   `.rabbit-tdd-autonomous` (flips `human-approval` off; both names written
   during the Phase 1 coexistence window, both honored on read).
2. Set `permissions.defaultMode: "bypassPermissions"` in
   `.claude/settings.local.json` (flips `bypass-permissions` on).
3. Write `.rabbit-auto-evolve-active` (signals mode is on).

After the three markers, `set-evolve-mode.py on` invokes
`.claude/features/rabbit-auto-evolve/scripts/install-cron.py`, which uses
`detect-scheduler.py` (Inv 34) to choose the mechanism. WHERE crontab is
usable it idempotently installs the system-cron entry that fires the
headless tick (Inv 32) — the cron is the tick scheduler. WHERE
crontab is administratively blocked it does NOT fail: it exits 0 and emits a
JSON signal `{"scheduler":"croncreate","action":"dispatcher-must-create-heartbeat",
"cron":"13,43 * * * *","prompt":"/rabbit-auto-evolve tick","durable":true}`
plus a branded line saying the durable `CronCreate` heartbeat will be set up
on the next `/rabbit-auto-evolve start`. The heartbeat fires the INTERNAL
`tick` (which respects but never deletes the stop marker), NEVER the
USER-intent `start` — a MACHINE wake-up must not inherit `start`'s
stop-cancelling semantics (Inv 41).

**CronCreate heartbeat creation (DISPATCHER action, croncreate path only).**
A script CANNOT call `CronCreate` — it is a Claude tool. So when
`install-cron.py` (or `detect-scheduler.py`) signals `scheduler:"croncreate"`,
the DISPATCHER creates the durable heartbeat on the first `start`,
IDEMPOTENTLY: call `CronList` first and create only if no matching heartbeat
exists, then `CronCreate(cron="13,43 * * * *", prompt="/rabbit-auto-evolve tick",
durable=true)`. The heartbeat fires the INTERNAL `tick`, NEVER the USER-intent
`start`: a cron-fired wake-up that fired `start` would inherit Inv 19's
stop-cancel and silently resurrect a user-halted loop (Inv 41). The `13,43`
minutes avoid the `:00`/`:30` marks per CronCreate guidance. `CronCreate` is
the SANCTIONED fallback trigger here — a durable idle-REPL prompt scheduler,
NOT an in-session wakeup harness (the forbidden set is named in spec Inv 32).

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
2. `approval-bypass` — `human-approval` is off (i.e. EITHER the legacy
   `.rabbit-human-approval-bypass` OR the new `.rabbit-tdd-autonomous`
   present; dual-read during the Phase 1 coexistence window).
3. `bypass-permissions` — `bypass-permissions` is on (i.e.
   `.claude/settings.local.json` has
   `permissions.defaultMode == "bypassPermissions"`).

#### Routing table (per Inv 10)

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

The auto-on routing on fresh state keeps a single user intent ("enter
auto-evolve mode") from fragmenting into a two-step manual flow: the skill
never surfaces the precondition checklist verbatim and waits for the user to
type `/rabbit-auto-evolve on` themselves.

#### Start the loop (only on `all_pass: true`)

0. **Self-heal for the explicit user `start` ONLY (Inv 19).** Invoke
   `python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py`. As the
   EXPLICIT USER `start` entry it performs the two intent-tied self-heal steps
   BEFORE the walk runs: it deletes any stale
   `.rabbit-auto-evolve-stop-requested` (an explicit `start` cancels a pending
   stop — the SOLE stop-cancel path, Inv 41) and bootstraps
   `.rabbit/auto-evolve-state.json` with defaults if it is missing, empty, or
   malformed (a valid existing state file is left untouched). It does NOT write
   the `.rabbit-auto-evolve-running` marker — that write is owned by the shared
   phase-walk (Inv 42). A MACHINE-fired `tick` NEVER runs this step (see
   "`tick` (internal)" below).
1. Run one `tick` by walking the shared scripted phase-walk — the dispatcher
   supplies ONLY Phase 6 (see "`tick` (internal)" below). The walk's
   pre-dispatch segment self-syncs the tree (Inv 38), runs the running-guard
   (Inv 35), and — ONLY when the guard returns `proceed` — writes the
   `.rabbit-auto-evolve-running` marker itself (Inv 42), carrying a DURABLE
   owner PID (the long-lived session PID, omitted when undeterminable) plus an
   ISO-8601 timestamp. Because the marker is written AFTER the guard, the walk
   never false-skips on a marker it itself wrote. On a pre-dispatch
   `{"action":"skip",...}` (sync-fail, stop, abort, or a FRESH marker from a
   DIFFERENT live tick — `reason: tick-running`) do NOT start a second tick:
   run `end-tick.py` and end the turn. On `{"action":"proceed",...}` continue
   to Phase 6. Phase 12 runs `schedule-decision.py` (Inv 33) and the dispatcher
   schedules the immediate-refire when work remains — see "Scheduling" below.
2. End the turn. The HOUSEKEEPING tick is fired by the **system cron**
   installed at `on` (where crontab is available) running `tick-headless.py`;
   the DEVELOPMENT tick (phase 6 dispatch) is re-triggered by the scheduler
   firing `/rabbit-auto-evolve tick` (Inv 32) — a FRESH context on the
   system-cron path, but the SAME live session (context reused, accumulating,
   auto-compaction-bounded) on the `CronCreate` fallback. Every
   MACHINE wake-up fires the internal `tick`, NEVER the
   USER-intent `start` (Inv 41): `tick` respects but never deletes the stop
   marker, so a heartbeat can never cancel a human's explicit stop. There is
   NO in-session wakeup-harness self-chaining (the forbidden mechanisms are
   named in spec Inv 32).

### `stop`

Invoke `python3 .claude/features/rabbit-auto-evolve/scripts/stop-loop.py`
(which writes `.rabbit-auto-evolve-stop-requested` at repo root). The
next tick's phase 0 (`stop-check`) observes the marker, posts a one-line
run summary, and halts cleanly (the headless tick short-circuits to a clean
no-op). To stop the cron from firing entirely, run `/rabbit-auto-evolve
off`, which uninstalls the cron entry. Per Inv 17 the marker write is
wrapped in a script for the same scope-guard reason as `start`.

### `status`

`status` is read-only (performs no mutations). Per Inv 29, the
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
- `in_flight` — in-flight issue set (derived from `dispatch_journal`, Inv 54;
  falls back to a literal `in_flight` array when no journal is present)
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

### `log` (per-tick observability log — Inv 37)

Manage the FULL per-tick observability log at `.rabbit/auto-evolve.log` — a
persistent, append-only, machine-readable (JSON-lines) execution trace written
by every tick. It exists so the user can debug what the loop did / when it last
ran / why it stalled, and so OTHER Claude sessions can `tail`/grep the file to
answer "is the loop alive?" / "what phase did it last reach?" without
round-tripping to the running session.

This log is DISTINCT from the minimal Inv 36 `.rabbit/tick.log`
(`tick-log.py`), which records only heartbeat/guard/schedule DECISIONS. The two
logs COEXIST (different files, different purposes); the `log` subcommand never
touches `tick.log`.

Every `log` subcommand routes through a script — the enable flag, verbosity
level, rotation, and path resolution are owned by `log-tick.py` /
`log-path.py`, never assembled inline (Inv 17). The enable flag (DEFAULT on)
and the verbosity level live in rabbit-auto-evolve's OWN config
(`.rabbit/auto-evolve-log-config.json`), NOT in rabbit-cage's `configuration`
array.

| Subcommand | Action |
|---|---|
| `log on` | Enable logging. Runs `python3 .claude/features/rabbit-auto-evolve/scripts/log-tick.py config on`. |
| `log off` | Disable logging — `log-tick.py` then writes NOTHING (zero file growth, a hard requirement). Runs `python3 .claude/features/rabbit-auto-evolve/scripts/log-tick.py config off`. |
| `log level <quiet\|normal\|debug>` | Set verbosity (strictly-additive levels; DEFAULT `normal`). Runs `python3 .claude/features/rabbit-auto-evolve/scripts/log-tick.py config level <level>`. |
| `log path` | Print the absolute log-file path (for `tail -f $(… log-path.py)`). Runs `python3 .claude/features/rabbit-auto-evolve/scripts/log-path.py`. |
| `log tail [N]` | Print the last N lines (DEFAULT 20). Resolve the path via `log-path.py`, then `tail -n <N>` it. |
| `log clear` | Truncate the log AFTER confirming with the user. Resolve the path via `log-path.py`, then truncate it. |

Verbosity levels (each includes everything the lighter level emits):

- `quiet` — tick start/end only.
- `normal` (DEFAULT) — tick boundaries + phase results + blockers.
- `debug` — every phase transition with timestamps plus payload sizes/counts.

A record below the active level is DROPPED (no file growth). Each emitted line
is capped at 2 KB hard (the writer truncates the longest array fields rather
than emit an oversized line). Rotation runs at TICK START (phase 0, via
`log-tick.py rotate`), not on every write: when `auto-evolve.log` exceeds 5 MB
it rotates `.log` → `.log.1` → `.log.2` → `.log.3`, keeping AT MOST 3 rotated
files (≤ 4 total).

### `tick` (internal)

The internal phase-walk fired by every MACHINE wake-up — the recurring
heartbeat and the immediate-refire one-shot both fire `/rabbit-auto-evolve
tick`, NEVER `/rabbit-auto-evolve start` (Inv 41). `tick` invokes the shared
scripted phase-walk DIRECTLY (pre-dispatch → dispatch → post-dispatch) with NO
cancel-stop and NO bootstrap: those self-heal steps are owned by the explicit
user `start` entry (`start-loop.py`, Inv 19) ONLY. At phase 0 the walk READS
`.rabbit-auto-evolve-stop-requested` and halts cleanly when present — it NEVER
deletes the stop marker. The marker is cleared EXCLUSIVELY by an explicit user
`start`; this is what makes a user stop HOLD across heartbeats until the user
explicitly resumes. The running marker, by contrast, is written by the shared
walk itself (after its own running-guard returns `proceed`, Inv 42) on BOTH the
in-session and headless paths — so neither path false-skips on a marker it
itself wrote.

Walked by a live Claude session (via `start` or a cron-surfaced resume). The
in-session tick runs the SAME single shared scripted phase-walk the headless
tick runs (`run-tick-phases.py`, Inv 40); the dispatcher supplies ONLY Phase 6
(`dispatch`), the one phase that needs Claude. The dispatcher does NOT
hand-build any inter-phase data structure (state objects, handoffs) — every
phase handoff is script-to-script (stdin/stdout pipes or on-disk state
mutation). The deterministic walk runs in two segments around Phase 6:

1. **Pre-dispatch segment** (phases 0-1, running-guard, 3-5):
   ```
   python3 .claude/features/rabbit-auto-evolve/scripts/run-tick-phases.py pre-dispatch
   ```
   It runs the tick-start self-sync (Inv 38), the phase 0/1 stop/abort
   short-circuit, the running-guard (Inv 35), then — ONLY when the guard returns
   `proceed` — writes the `.rabbit-auto-evolve-running` marker itself (Inv 42),
   and finally phases 3-5 (`fetch | triage | plan`). Sequencing the guard before
   the marker write, in this ONE place for both the in-session and headless
   paths, is what stops a path from false-skipping on a marker it itself wrote.
   On `{"action":"skip",...}` a clean short-circuit fired (sync-fail, stop,
   abort, or a FRESH marker from a different live tick — `tick-running`) — run
   `end-tick.py` and end the turn. On `{"action":"proceed",...}` continue to
   Phase 6.
2. **Phase 6 (`dispatch`)** — the dispatcher's ONLY hand-driven phase. Before
   dispatching, consult the per-tick dispatch journal (Inv 54) so a resumed
   tick skips already-handled subagents:
   ```
   <plan-json> | python3 .claude/features/rabbit-auto-evolve/scripts/resume-dispatch.py --tick-id <tick-id>
   ```
   It returns `{"dispatch": [...], "skip": [...]}`; dispatch ONLY the
   `dispatch` set (the `skip` set is `completed`/`pr_open` this cycle and
   drains via the merge path). Then run the dispatch set in this STRICT order
   (Inv 54, Inv 55) so the GitHub `in-progress` label is visible for the FULL
   minutes-to-hours TDD subagent execution window — NOT just a flicker:
   1. **Record ALL `dispatched` journal entries first** — one entry for every
      issue in the dispatch set, BEFORE any Agent call, so the journal's live set
      is complete:
      ```
      python3 .claude/features/rabbit-auto-evolve/scripts/record-dispatch.py --tick-id <tick-id> --issue <N> --feature <name> --shape <shape> --status dispatched [--branch <b>] [--worktree <w>]
      ```
   2. **Then run `reconcile-labels.py`** — a SCRIPTED invocation (the label
      logic stays in the script; the dispatcher only triggers it here) that
      stamps `in-progress` on the now-live dispatched set BEFORE the Agent calls,
      so the label covers the entire subagent run:
      ```
      python3 .claude/features/rabbit-auto-evolve/scripts/reconcile-labels.py
      ```
   3. **Then fire the Agent calls** — dispatch the TDD subagents per the
      Stage-1/Stage-2 plan (Inv 26), each with `isolation: "worktree"` (Inv 28).
      The label is already live; the subagents now run for minutes/hours.
   4. **Record each HANDOFF return** — when a dispatch's HANDOFF comes back,
      update its journal entry (`--status pr_open`/`aborted` with `--branch`/`--pr`):
      ```
      python3 .claude/features/rabbit-auto-evolve/scripts/record-dispatch.py --tick-id <tick-id> --issue <N> --feature <name> --shape <shape> --status <status> [--branch <b>] [--pr <N>]
      ```
3. **Post-dispatch segment** (phases 7, 8-10, 11):
   ```
   python3 .claude/features/rabbit-auto-evolve/scripts/run-tick-phases.py post-dispatch
   ```
   The segment FIRST runs `reconcile-labels.py` (Inv 55, add-on-entry) BEFORE
   any merge, so the `dispatched`/`pr_open` live set gets the GitHub
   `in-progress` label added while still live — even a single-tick item
   (dispatch → PR → merge in one tick) is labelled before merge drains it. This
   add-on-entry call ALSO covers the HEADLESS path, which skips Phase 6 entirely
   and so never runs the phase-6 in-session reconcile above.
   Phase 7 then runs `clean-dispatch-leaks.py` (Inv 43, Inv 44) to
   deterministically clean KNOWN worktree-dispatch leak-class noise from the
   main tree BEFORE the merge. As its first step it restores a leaked main-HEAD
   branch switch (Inv 44): when a subagent's `git checkout -B <branch>
   origin/dev` left the dispatcher's MAIN HEAD on a feature branch (which would
   trip safety-check Inv 1 "branch is dev" and skip the batch), and the tree is
   clean with no un-pushed unique commits, it runs `git checkout dev` to
   restore HEAD; if the tree is dirty or the branch has un-pushed work it FAILS
   LOUDLY rather than discard it. It then cleans the worktree-dispatch
   file-leak classes — an untracked stray `.rabbit-scope-active-*` marker or a
   bookkeeping-only `feature.json` edit that a worktree-isolated Phase 6
   dispatch leaked (which would otherwise trip safety-check Inv 5 and skip the
   batch). The
   cleanup FAILS LOUDLY (the tick aborts) on any unexpected tracked change, so
   a genuine uncommitted change is never destroyed. It then runs the rest of
   phase 7 (merge the PRs in the state's transient `merge_ready` hint),
   phases 8-10 (`run-post-merge.py` drain), and phase 11 (persist). Phase 11
   re-reads the on-disk state (already mutated by the phase scripts), drops the
   transient `merge_ready` key, and pipes the object through `update-state.py`.
   The dispatcher does NOT read `update-state.py` source or the state schema to
   assemble state — the persist is deterministic and identical to the headless
   tick's. AFTER persist, the segment runs `reconcile-labels.py` (Inv 55) a
   SECOND time (strip-on-exit) to mirror the journal-derived live set onto the
   GitHub `in-progress` label, primarily STRIPPING it from issues that left the
   live set during this segment (merged → `completed`); the phase-6 in-session
   add, this segment's add-on-entry, and this strip-on-exit together keep the
   label truthful across all three Inv 55 touchpoints. The two post-dispatch
   calls are script-owned; the phase-6 call is a dispatcher-triggered SCRIPTED
   invocation of `reconcile-labels.py` (NOT hand-assembled label logic). A
   reconcile failure never fails the tick. FINALLY the segment runs
   `tick-jitter.py compute` (Inv 56) to refresh the empirical CronCreate
   jitter-offset artifact from the current `.rabbit/tick.log` fire history, so the
   idle banner's next-tick ETA stays accurate; like the reconcile, this runs on
   BOTH paths and a compute failure never fails the tick.
4. **Phase 12 (`schedule`)** — run `schedule-decision.py` (Inv 33) and schedule
   the immediate-refire when work remains (see "Scheduling" below).

Any phase MAY abort the tick early without affecting the next tick's ability to
pick up from disk-persisted state in `.rabbit/auto-evolve-state.json`. The
phase table below maps each phase to its owning script for reference; the live
session walks them via the two `run-tick-phases.py` segments plus Phase 6.

| # | Phase             | Script(s) invoked                            |
|---|-------------------|----------------------------------------------|
| 0 | `stop-check`      | `.claude/features/rabbit-auto-evolve/scripts/log-tick.py rotate` (rotate the observability log if >5MB — Inv 37) then `log-tick.py emit --record-kind tick-start …`; plus the file-existence check on `.rabbit-auto-evolve-stop-requested` |
| 1 | `restart-check`   | (none — file existence check on `.rabbit-auto-evolve-restart-needed`) |
| 2 | `post-merge-drain` | `.claude/features/rabbit-auto-evolve/scripts/run-post-merge.py` — drains any `pending_post_merge` owed by a previous truncated tick BEFORE fetch (Inv 30) |
| 3 | `fetch`           | `.claude/features/rabbit-auto-evolve/scripts/fetch-queue.py` |
| 4 | `triage`          | `.claude/features/rabbit-auto-evolve/scripts/triage-batch.py` (wraps `.claude/features/rabbit-auto-evolve/scripts/triage-issue.py` once per queued issue) |
| 5 | `plan`            | `.claude/features/rabbit-auto-evolve/scripts/plan-batch.py` |
| 6 | `dispatch`        | record ALL `dispatched` journal entries → `.claude/features/rabbit-auto-evolve/scripts/reconcile-labels.py` (Inv 55 — phase-6 in-session add: stamps `in-progress` on the just-dispatched set BEFORE the Agent calls, so the label covers the full TDD subagent run) → rabbit-feature-touch TDD subagent dispatch (Agent calls) |
| 7 | `merge`           | `.claude/features/rabbit-auto-evolve/scripts/reconcile-labels.py` (Inv 55 — add-on-entry: labels the just-dispatched live set BEFORE merge drains it) → `.claude/features/rabbit-auto-evolve/scripts/clean-dispatch-leaks.py` (Inv 43, Inv 44 — deterministic pre-merge cleanup of known worktree-dispatch leaks: restores a leaked main-HEAD branch switch to `dev` FIRST, then cleans file-leak classes; refuses non-zero on unexpected dirt or un-pushed leaked-branch work) → `.claude/features/rabbit-auto-evolve/scripts/merge-prs.py --record-pending` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase merge` (records merged PRs to `pending_post_merge`) |
| 8-10 | `post-merge`    | `.claude/features/rabbit-auto-evolve/scripts/run-post-merge.py` — deterministically runs release (8) → cleanup (9) → catch-up (10) for every PR in `pending_post_merge`, then clears it (Inv 30) — see "Post-merge phases (Inv 30)" below |
|11 | `persist`         | `.claude/features/rabbit-auto-evolve/scripts/update-state.py` writes `.rabbit/auto-evolve-state.json`, then `.claude/features/rabbit-auto-evolve/scripts/reconcile-labels.py` runs AGAIN (Inv 55 — strip-on-exit: strips the `in-progress` label from issues that left the live set after merge; pairs with the phase-7 add-on-entry call; add/strip via rabbit-issue `ensure_labels`; never fails the tick), then `.claude/features/rabbit-auto-evolve/scripts/tick-jitter.py compute` (Inv 56 — refreshes the empirical jitter-offset artifact from `.rabbit/tick.log` so the idle banner ETA stays accurate; never fails the tick) |
|12 | `schedule`        | `.claude/features/rabbit-auto-evolve/scripts/schedule-decision.py` — decide immediate-refire vs idle (Inv 33); on `immediate-refire` the DISPATCHER schedules the one-shot. See "Scheduling (Inv 32–33)" below |

### Post-merge phases (Inv 30)

Phases 8 (`release`), 9 (`cleanup`), and 10 (`catch-up`) are owned by a single
deterministic, non-skippable script rather than prose walked by the LLM
orchestrator. Prose-walked post-merge phases are silently dropped when phase
7 (`merge`) lands a large batch of PRs and the orchestrator ends the tick for
scale/context reasons; the script makes them non-skippable:

```
python3 .claude/features/rabbit-auto-evolve/scripts/run-post-merge.py
```

`run-post-merge.py` reads `pending_post_merge` (the merged PR numbers recorded
by `merge-prs.py --record-pending` in phase 7) from
`.rabbit/auto-evolve-state.json` and runs, IN ORDER:
`.claude/features/rabbit-auto-evolve/scripts/release-bump.py <pr#>`
(phase 8, once per merged PR) →
`.claude/features/rabbit-auto-evolve/scripts/cleanup-branches.py <pr-list>`
(phase 9, once) →
`.claude/features/rabbit-auto-evolve/scripts/classify-merge-restart.py <pr#>`
(phase 10, once per merged PR). On completion it clears `pending_post_merge`. An
empty/absent list is a clean no-op. A phase failure exits non-zero and leaves
`pending_post_merge` intact so the next tick's tick-start drain retries the
owed work.

Invoke `run-post-merge.py` in TWO places:

1. **After phase 7 (`merge`)** when any PR merged — the merge phase wrote the
   merged PR numbers via `merge-prs.py --record-pending`, so this drains them
   through phases 8–10 in the same tick.
2. **At tick START (phase 2, between `restart-check` and `fetch`)** — to
   DRAIN any owed post-merge work from a previous truncated tick BEFORE
   fetching new work. This is what makes the dropped-phase failure mode
   self-healing: even if a tick ends right after phase 7, the next tick
   finishes phases 8–10 before doing anything else.

A non-zero `run-post-merge.py` exit is an error-abort (Inv 20): run
`end-tick.py` and surface the failure rather than continue with owed work
silently dropped.

### Scheduling (Inv 32–33)

Phase 12 (`schedule`) is NO LONGER a pure no-op. It runs
`python3 .claude/features/rabbit-auto-evolve/scripts/schedule-decision.py`,
which counts DISPATCHABLE work (authoritatively, via the same
`fetch-queue.py | triage-batch.py | plan-batch.py` pipe phase 6 dispatches
from — the plan's `selection_order`, not the raw open count, so blocked/gated
backlogs go idle instead of spinning the loop), reads the
scheduler mechanism from `detect-scheduler.py`, logs the decision via
`tick-log.py`, and emits JSON:

- `{"decision":"immediate-refire","scheduler":"crontab"|"croncreate",
  "prompt":"/rabbit-auto-evolve tick #refire","when":"~1min",
  "croncreate":{...},"dispatcher_actions":{...},
  "authoritative_version":"<vX.Y.Z|null>"}` when the dispatchable plan is
  non-empty (Inv 33 / D1). The one-shot fires the internal
  `tick`, NEVER `start` (Inv 41) — a halting tick must never cancel a pending
  stop. The `#refire` MARKER on the prompt makes the refire one-shot
  distinguishable from the recurring heartbeat (bare `/rabbit-auto-evolve
  tick`) so dedup can never tear down the heartbeat (Inv 47). The
  DISPATCHER then schedules
  the near-immediate (~1 min) ONE-SHOT and ENDS the turn
  (do NOT continue inline). The refired tick's context is FRESH only on the
  system-cron / headless path; on the croncreate path the one-shot re-enters
  the SAME live session (context reused/accumulating, auto-compaction-bounded,
  NOT a fresh context):
  - **croncreate path:** invoke the actual one-shot `CronCreate(...)` per the
    emitted `croncreate` params. A script cannot call `CronCreate`; this tool
    action is the irreducible Claude step (exactly like phase 6 dispatch).
    The emitted `croncreate.cron` is a PINNED near-future `M H * * *`
    expression (current minute + 2, never `*/1 * * * *`), so a dropped
    `recurring` fails benignly (at most once/day at minute M, not an
    every-minute storm — Inv 33 pinned-minute amendment). The `+2` BUFFER
    keeps the pinned minute strictly in the future even after the
    `CronList`/`CronDelete`/`CronCreate` dedup round-trip below crosses a
    wall-clock minute boundary (a `+1` minute was dropped intermittently).
    Three non-negotiable dispatcher rules:
    - **Faithful flag passing.** Pass `recurring` and `durable` to
      `CronCreate` EXACTLY as emitted (both `false`) — never rely on
      `CronCreate` defaults (its default is recurring), never
      hand-translate-and-drop a field. Forward `croncreate.cron` verbatim too.
    - **At-most-one refire.** Before creating a new refire
      one-shot, `CronList` and `CronDelete` any prior immediate-refire
      one-shot, so at most ONE is alive at a time; never create a refire whose
      cadence duplicates the recurring heartbeat.
    - **Follow `dispatcher_actions` verbatim (Inv 47).** To make the
      above deterministic, pass the `CronList` result back to
      `schedule-decision.py` via the `RABBIT_AUTO_EVOLVE_CRON_LIST` env var; it
      emits `dispatcher_actions` = `{"delete_refire_ids":[...],
      "preserve_heartbeat_ids":[...],"create_refire":{...}}`. `CronDelete`
      EVERY id in `delete_refire_ids`, leave every id in
      `preserve_heartbeat_ids` UNTOUCHED (never delete the heartbeat), then
      `CronCreate` the single `create_refire`.
  - **crontab path:** schedule the transient/`at`-style one-shot the emitted
    hint documents.
- `{"decision":"idle","detail":"rely on heartbeat"}` when the queue is empty.
  Schedule nothing; the recurring heartbeat (the `*/…` system-cron entry, or
  the durable `CronCreate` heartbeat on restricted hosts) fires the next
  check.

EVERY decision (both shapes) ALSO carries `authoritative_version` — the
current version resolved THIS TICK from `git describe --tags --abbrev=0`,
falling back to the state `last_tagged_version`, falling back to null
(Inv 64). **Version narration grounding:** whenever the dispatcher
narrates or cites the current version (in a tick summary, a banner, or any
status sentence), it MUST cite this `authoritative_version` read FRESH from
the tick output — NEVER a version number carried in accumulated session
context. On the croncreate session-reuse path the session is REUSED across
ticks and context ACCUMULATES, so a remembered version goes stale; the
`authoritative_version` field is the fresh, deterministic source the narrator
reads each tick instead.

`CronCreate` is PERMITTED solely as the fallback trigger — a durable
idle-REPL prompt scheduler, NOT an in-session wakeup harness (the forbidden
set, including the deprecated wakeup call, is named in spec Inv 32). The
recurring heartbeat is
installed by `set-evolve-mode.py on` (`install-cron.py` — crontab where
available, else the dispatcher's durable `CronCreate` heartbeat) and removed
by `set-evolve-mode.py off` (`uninstall-cron.py`). The crontab heartbeat
entry has the form:

```
*/30 * * * * cd <repo_root> && python3 \
  .claude/features/rabbit-auto-evolve/scripts/tick-headless.py \
  >> .rabbit/tick-headless.log 2>&1
```

**Tuning the cadence (operational config).** The `*/30` above is the
DEFAULT, not a hard wire. The tick cadence is operational config: set the
`RABBIT_AUTO_EVOLVE_CADENCE` env var, or write `{"cadence_minutes": <n>}` to
rabbit-auto-evolve's own `.rabbit/auto-evolve-cadence-config.json` (state dir
honors `RABBIT_AUTO_EVOLVE_STATE_DIR`), then re-run `set-evolve-mode.py on` (or
`install-cron.py`) to reinstall. `install-cron.py` resolves the cadence once
(env > config file > the `CADENCE_MINUTES = 30` default), VALIDATES it as an
integer in `1..59`, and derives BOTH the system-cron `*/N * * * *` entry AND
the `CronCreate`-fallback heartbeat from that SAME value — so the two paths
never split. An invalid value is rejected: `install-cron.py` warns and falls
back to the default rather than installing a nonsense cron line.

This converts the prior silent-stop failure mode (a dropped in-session
wakeup once halted the loop for 5h+ with no error) into an external,
observable scheduler whose decisions are all logged (Inv 36) and whose stale
running markers are cleared by the running-guard (Inv 35) so the loop never
wedges silently.

### Headless tick (cron)

The cron-fired headless tick is owned by
`python3 .claude/features/rabbit-auto-evolve/scripts/tick-headless.py`. It
runs WITHOUT a Claude session and walks the SAME single shared scripted
phase-walk (`run-tick-phases.py`, Inv 40) the in-session tick walks — chaining
`pre-dispatch -> (skip dispatch, no Claude) -> post-dispatch`. It therefore
walks every deterministic phase EXCEPT phase 6 (`dispatch`), which requires
Claude:

- tick-start self-sync (Inv 38) — BEFORE any phase, it runs
  `python3 .claude/features/rabbit-auto-evolve/scripts/sync-tree.py` so the
  cron path also self-syncs to the latest merged scripts (`git pull
  --ff-only origin dev`, NEVER the permission-denied `git merge`). On a
  dirty/divergent tree it short-circuits to a clean no-op (logged) rather
  than run stale scripts.
- phase 0 (`stop-check`) + phase 1 (`restart-check`) — if
  `.rabbit-auto-evolve-stop-requested` or `.rabbit-auto-evolve-aborted`
  exists, the tick short-circuits to a clean no-op.
- phases 3–5 (`fetch | triage | plan`) — the canonical pipe.
- phase 6 (`dispatch`) — SKIPPED (no Claude session).
- phase 7 (`merge`) — `merge-prs.py --record-pending` for the PRs listed in
  the state's `merge_ready` field; skipped when there are none.
- phases 8–10 (`post-merge`) — `run-post-merge.py` drains
  `pending_post_merge`.
- phase 11 (`persist`) — `update-state.py`.
- phase 12 (`schedule`) — NO-OP in the headless tick: the recurring heartbeat
  owns the HOUSEKEEPING cadence (Inv 32 amendment). The development-tier
  immediate-refire (Inv 33) needs a live session and is handled in the
  SESSION tick's phase 12 via `schedule-decision.py`, not here.

`tick-headless.py` emits a single JSON result object on stdout summarizing
which phases ran (with `dispatch` always marked `"skipped"`). Dispatch
(phase 6) only happens during a live Claude session tick (`start` / `tick`).

### Tick exit invariant (Inv 20)

Per spec Inv 20, EVERY tick exit path MUST end by invoking
`python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py` as its
last action. `end-tick.py` deletes the `.rabbit-auto-evolve-running`
marker (mirror of the shared phase-walk's write, Inv 42); without it the marker leaks
across sessions and the user has to remove it manually (which scope-guard
correctly denies, since `.rabbit-auto-evolve-*` markers are not on its
allowlist).

The four named exit paths are:

- **normal completion** — phase 12 (`schedule`) runs
  `schedule-decision.py` (Inv 33): if work remains, the DISPATCHER schedules
  the near-immediate refire (croncreate one-shot, or the
  crontab transient hint) per the emitted params; if the queue is empty it
  relies on the heartbeat. The refired tick's context is FRESH only on the
  system-cron / headless path; the croncreate one-shot REUSES the same live
  session (history accumulates, bounded by auto-compaction — Inv 33).
  Then
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py` runs, then
  the turn ends.
- **phase 0 halt** — `.rabbit-auto-evolve-stop-requested` observed at
  the top of the tick. Post the run summary, then run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`,
  then end the turn (the cron is removed by `off`).
- **safety abort** — any safety violation during phases 7–9 writes
  `.rabbit-auto-evolve-aborted` via
  `python3 .claude/features/rabbit-auto-evolve/scripts/mark-aborted.py "<reason>"`.
  Immediately after, run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`
  and end the turn (the headless tick then short-circuits to a no-op
  while the abort marker is present).
- **error abort** — an unexpected exception in any phase. Run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`
  in the error-handler tail before ending the turn.

`end-tick.py` is idempotent: re-invoking when the marker is already
absent is a clean no-op (exit 0).

Per Inv 37 (g), every tick records its execution trace to the per-tick
observability log: at tick START (phase 0, after `log-tick.py rotate`) emit a
`tick-start` record; at every phase boundary emit a `phase` (or, at `debug`,
`phase-transition`) record as the active verbosity level dictates; and on EVERY
exit path emit a `tick-end` record via
`python3 .claude/features/rabbit-auto-evolve/scripts/log-tick.py emit
--record-kind tick-end …` before `end-tick.py`. These emits are no-ops when the
enable flag is off, so the trace adds zero file growth when logging is disabled.

Phases 3–5 form the canonical fetch → triage → plan pipe (per Inv 18):

```
python3 .claude/features/rabbit-auto-evolve/scripts/fetch-queue.py \
  | python3 .claude/features/rabbit-auto-evolve/scripts/triage-batch.py \
  | python3 .claude/features/rabbit-auto-evolve/scripts/plan-batch.py --max-parallel 4
```

`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py` is NOT
invoked by `tick` — it runs only when the user flips the mode via
`/rabbit-auto-evolve on|off`.

### Duplicate resolution via native GitHub state (Inv 60)

The duplicate-DETECTION heuristic is unchanged: `triage-issue.py` rule 3
flags a duplicate by the case-folded title-substring match against
closed-in-last-30-days issues and emits `decision=close-not-planned`,
`reason_code=duplicate`, and the matched closed issue's number in
`duplicate_of`. When the dispatcher acts on a `reason_code=duplicate`
verdict it resolves the duplicate via the AUTHORITATIVE GitHub-native
duplicate state — NOT a reinvented `duplicate` label or a free-prose
not-planned close — by invoking the script:

```
python3 .claude/features/rabbit-auto-evolve/scripts/resolve-duplicate.py resolve <dup#> <duplicate_of#>
```

This closes `<dup#>` with `gh api --method PATCH repos/{slug}/issues/<dup#>
-f state=closed -f state_reason=duplicate` and posts one cross-reference
comment naming `<duplicate_of#>`, so the native duplicate relationship is
visible. The native close-as-duplicate is a CLOSE — a terminal convergence
consistent with the convergence guarantee (Inv 25) — never a
label-strip-while-open de-queue. The reinvented `duplicate` label is a
deprecating coexistence mirror honored ONLY on read (`resolve-duplicate.py
status <n>`); a new resolution NEVER stamps the label, only the native
state. Deprecation criterion: drop the `duplicate` label read once no open
or recently-closed issue carries the label and native
`state_reason=duplicate` is the sole expressed duplicate marker.

### Dispatch shape selection (Stage 1 / Stage 2 — Inv 26)

Phase 5 (`plan`) emits TWO decoupled outputs the dispatcher consumes in
phase 6:

- `selection_order` — **Stage 1, dispatch-shape blind.** The order to work
  items in, by the composite key `(computed_score desc, contract_touch desc,
  issue asc)`: the loop's `computed_score` (Inv 44) is PRIMARY, the
  contract-touch barrier is the SECONDARY tiebreak (contract items lead WITHIN
  a score tier, never across tiers), issue asc is the final tiebreak. The
  filer `priority:` label is ONE weighted input folded into `computed_score`,
  not the standalone primary key — so a higher-scoring `low` item can sort
  ahead of a `medium` whose other observable signals are weaker (Inv 44 by
  design). The same key drives `barrier_first`, so the two agree. It NEVER
  consults dispatch shape, feature count, or "knows how": a higher-scoring
  cross-feature item is selected before a lower-scoring single-feature item,
  and a higher-scoring non-contract item beats a lower-scoring contract item.
- `dispatch_shapes` — **Stage 2, item-shaped.** A map of issue-number-string
  → one of exactly THREE shapes. Per item, pick the FIRST that fits:

  | Rank | Shape | When | Mechanics |
  |---|---|---|---|
  | 1 (perf preference) | `parallel-per-feature` | item edits exactly one feature dir | one full single-feature TDD touch (its own `.rabbit-scope-active-<feature>` marker); multiple such items dispatch in parallel |
  | 2 | `multi-subagent-barrier` | item edits >1 feature dir, below the decompose threshold | per-feature subagents land SERIALLY on ONE shared branch; subagent k+1 fetches subagent k's pushed commit before starting; each piece is a full single-feature touch with its own scope marker; one PR closes the item |
  | 3 | `decomposition` | item edits ≥ `--decompose-threshold` feature dirs (default 10) | file N per-feature sub-issues via `python3 .claude/features/rabbit-issue/scripts/file-item.py … --parent <parent#>` (a contract INVOKE, not a cross-feature edit), each labelled with the right `feature:<name>` + `priority:<level>` label; `--parent` makes each child born linked to the parent as a GitHub-native sub-issue (a DERIVATIVE human-readable view). **Then record the AUTHORITATIVE parent→children linkage machine-readably** via `python3 .claude/features/rabbit-auto-evolve/scripts/record-decomposition.py <parent#> <child#> …` (Inv 53) — the `decomposition_parents` state map is the source of truth, NEVER the GitHub-native link and NEVER a prose comment table; keep the parent OPEN and queue the sub-issues, which re-enter Stage 1/Stage 2 on the next tick. The per-tick `run-post-merge.py` drain then deterministically closes the parent once all its recorded children are closed (`close-decomposed-parents.py`, Inv 53) — the dispatcher NEVER hand-closes a decomposed parent |

  `parallel-per-feature` is the **performance preference, not a correctness
  requirement** — items that don't fit it still get done via shape 2 or 3,
  just slower. The dispatcher MUST NOT skip, defer indefinitely, or escalate
  an item merely because it doesn't fit shape 1.

  **Cross-scope routing (Inv 51).** `triage-issue.py` flags an issue whose
  BODY spans multiple feature dirs (a repo-wide sweep, a cross-feature rename,
  or an explicit cross-scope phrase like "repo-wide" / "across all features")
  with `cross_scope: true`. `plan-batch.py` NEVER shapes such an item as
  `parallel-per-feature` — a single bounded per-feature subagent cannot write
  across features, so a cross_scope item is routed to `multi-subagent-barrier`
  (below the decompose threshold) or `decomposition` (at/above it). Every
  cross_scope work item's issue number is listed under the plan's
  `cross_scope_items` key so the dispatcher sees which items need the
  barrier/decomposition path rather than parallel single-feature dispatch.

  **Decomposition-parent exclusion (Inv 58).** `triage-issue.py` flags an OPEN
  issue that is a recorded decomposition PARENT — it HAS GitHub-native
  sub-issues (`gh api repos/{slug}/issues/<n>` → `sub_issues_summary.total >
  0`) OR is a key in the `decomposition_parents` state map (coexistence
  fallback) — with `decomposition_parent: true`. `plan-batch.py` FILTERS such
  an item out of the dispatchable plan entirely: it appears in neither
  `selection_order`, `dispatch_shapes`, nor `cross_scope_items`. A
  decomposition parent carries no own code change and converges via child
  rollup (closed by `close-decomposed-parents.py` once all children close, Inv
  53), never via dispatch — so the dispatcher never sees it and never hand-skips
  it. The parent stays OPEN and tracked-by-decomposition (it does not violate
  the convergence guarantee, Inv 25). A child sub-issue (it has a PARENT link
  but no children of its own) is still selected and shaped normally.

  The struck shape ("sequential single-subagent with a persistent
  `.rabbit-scope-override session`") is NEVER used. Autonomous-evolve ALWAYS
  uses a full per-feature touch gated by `.rabbit-scope-active-<feature>`; it
  NEVER writes a persistent `.rabbit-scope-override session` for feature
  edits. Bounded scope is a hard constraint, not waivable by autonomy
  (maintainer policy). A one-time override is permitted ONLY
  for plan / temporary-document writing — never for feature code edits.

### Worktree isolation for TDD dispatches (Inv 28)

**Every Agent call for a TDD-subagent dispatch in phase 6 MUST include
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
`.claude/settings.local.json`. Inv 28 makes passing `isolation: "worktree"`
on every dispatch a binding invariant rather than a manual practice.

**Known limitation (stale base):** `worktree.baseRef: "head"` requires a
session restart to take effect; until the session has been restarted after
the setting landed, a newly created worktree may branch from a stale base
and a subagent may need to re-branch from `origin/dev` manually at the
start of its cycle. This is a Claude Code worktree-harness limitation, not
a feature defect; it resolves on the next session restart.

### `off`

Deactivate auto-evolve mode. Invokes
`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py off`,
which performs a FULL teardown — it first removes the system-cron entry
(via `uninstall-cron.py`, Inv 32) so a torn-down mode never
leaves a live cron, then deletes the four loop-runtime markers (innermost
first, idempotent), then reverses the three `on` mutations in inverse
order:

0. Remove the system-cron headless-tick entry (idempotent; safe when
   absent).
1. Delete any of the four loop-runtime markers if present
   (`.rabbit-auto-evolve-running`, `.rabbit-auto-evolve-stop-requested`,
   `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`).
2. Delete `.rabbit-auto-evolve-active`.
3. Delete the `permissions.defaultMode` key from
   `.claude/settings.local.json`.
4. Delete `.rabbit-human-approval-bypass` AND `.rabbit-tdd-autonomous`
   (both bypass-marker names during the Phase 1 coexistence window;
   idempotent).

On success, the script emits one branded `rabbit_print` confirmation
line to stdout (green `Autonomous-evolve mode deactivated — full
teardown complete`). Surface the script's stdout verbatim to the user
— do NOT paraphrase (per spec Inv 1 v0.7.4).

A Claude restart is required so the cleared `permissions.defaultMode`
takes effect.

Disk-persisted state lives at `.rabbit/auto-evolve-state.json`, schema
`scripts/schemas/auto-evolve-state.schema.json` (v1.4.0).

## Discovered issues and aborted_reason handling

The TDD subagent HANDOFF carries two optional fields the loop reacts to
during phase 6 (`dispatch`) result processing:

- `discovered_issues` — array of `{title, body, labels}` objects. The loop
  files each via `rabbit-issue` (script
  `python3 .claude/features/rabbit-issue/scripts/file-item.py …`) with a
  `feature:<name>` + `priority:<level>` label so the next tick's `fetch`
  phase picks them up.
- `aborted_reason` — non-null string. When a concrete blocker issue `N` is
  discovered, the loop records the dependency in the AUTHORITATIVE
  GitHub-native dependencies graph (`gh api --method POST
  repos/{slug}/issues/<original>/dependencies/blocked_by -F issue_id=<N-id>`)
  so the next tick's triage reads the blocked state natively; the
  `blocked-by:#N` label/body marker is a deprecating fallback retained only
  during the coexistence window. The original issue stays OPEN so a future
  tick may retry once the native blocker closes.

## Republish deployed surfaces before opening the PR (Inv 50)

A version-bumping TDD subagent bumps a feature's SOURCE `SKILL.md` (required
for four-way version equality across `feature.json`, `docs/`, the source
skill, and the deployed skill) but CANNOT write the deployed
`.claude/skills/<feature>/SKILL.md` copy — that path is outside the
subagent's `.rabbit-scope-active-<feature>` scope, so the scope guard denies
the write. Left unrepublished, the deployed copy lags source and
`contract/test/test-deployed-skills-match-source.py` is RED in the PR.

After a version-bumping subagent returns — or ANY HANDOFF reporting a changed
deployed surface (a `SKILL.md`-changed note, a hook/command/file change) —
the dispatcher MUST republish the feature's deployed copies IN THE WORKTREE,
BEFORE opening the PR, by running:

    python3 .claude/features/rabbit-auto-evolve/scripts/republish-feature.py <feature> --repo-root <worktree-root>

`republish-feature.py` reads `<feature>`'s `feature.json` `manifest` and
invokes the contract-owned `contract.lib.publish.<api>` for every `publish_*`
entry (a cross-scope INVOKE declared in this feature's `contract.md`
`invokes.modules`). It is idempotent (a deployed copy already matching source
is a no-op), emits a JSON summary on stdout of what was (re)published, and is
a clean no-op for a feature with no manifest. Commit the refreshed deployed
copy into the PR so `test-deployed-skills-match-source.py` is green at merge
time. Run it once per feature whose deployed surface changed (including
rabbit-auto-evolve's own skill when this feature is the one touched).

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
`.rabbit-auto-evolve-aborted` with the abort reason and ends the turn.
The abort marker makes the cron-fired headless tick short-circuit to a
clean no-op, so the loop stays halted. The next SessionStart banner
surfaces the abort to the user.

**While `.rabbit-auto-evolve-running` is present, the dispatcher MUST NOT strip the actionability labels (`feature:`/`priority:`) from an OPEN issue as a parking or hand-back action.**

"De-queue" — dropping a queue-gating label while leaving the issue OPEN — is
the AskUserQuestion human-handoff escape (above) leaking through a different
mechanism (Inv 25). `fetch-queue.py` selects on ACTIONABILITY (open +
valid `feature:` + valid `priority:`), so stripping either label silently
exits the issue from the loop's view and strands it
open-but-untracked, defeating the convergence guarantee (Inv 25). The
convergence guarantee is LABEL-INDEPENDENT: an open valid issue must converge
to a terminal-or-tracked state. The only permitted non-work
outcomes are a bounded `defer` (tracked) or `close-not-planned` with a strong
reason — never label removal.

Other red flags:

- Never call `gh pr merge` on a PR whose base is outside the `{dev, main}` integration-target coexistence set.
- Never delete a branch not matching `^feat/.+`.
- Never create a tag that already exists.
- Never merge when the working tree is dirty.
- Never merge when the pre-merge install smoke fails — `safety-check.py
  --phase merge` runs `install-smoke.py` (Inv 63, bottom-line check 6: an
  isolated network-free fresh install + `--update` of rabbit-cage's install.py
  against the current tree); a non-zero smoke exit blocks the batch so
  install/closure breakage never lands on the integration target.
- Never write a persistent `.rabbit-scope-override session` for feature
  edits. Cross-feature work is handled by `decomposition` or
  `multi-subagent-barrier` (Inv 26) — every write stays inside one feature's
  `.rabbit-scope-active-<feature>` scope.
- Never dispatch a TDD subagent without `isolation: "worktree"` on the
  Agent call (Inv 28) — parallel dispatches sharing one working tree
  collide on branch, HEAD, commits, and scope markers.

`safety-check.py` enforces these; `merge-prs.py` and
`cleanup-branches.py` also refuse defense-in-depth.
