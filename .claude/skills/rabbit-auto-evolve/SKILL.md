---
name: rabbit-auto-evolve
version: 0.30.0
owner: rabbit-workflow team
deprecation_criterion: when Claude Code or rabbit gains a native always-on autonomous-agent mode that supersedes this skill
description: Self-driving rabbit loop that continuously fetches open `rabbit-managed` GitHub issues, triages each one, dispatches TDD subagents to implement actionable work, merges approved PRs into `dev`, tags versioned releases, and is fired on a fixed cadence by a system cron (installed at `on`) until the user issues an explicit stop. Invoke for any natural-language phrasing matching "start auto-evolve", "stop the loop", "auto-evolve status", "let rabbit run", "begin autonomous evolve", or any `/rabbit-auto-evolve <subcommand>` form. Invoking `start` from a fresh state auto-routes to `on` and prompts for a Claude restart — no need to run `on` manually first.
---

# rabbit-auto-evolve

A self-driving rabbit loop. Continuously fetches open `rabbit-managed`
issues, triages each, dispatches TDD subagents, merges approved PRs into
`dev`, tags releases, and is fired on a fixed cadence by a **system cron**
(the tick scheduler where available, installed at `on`) until the user
issues an explicit stop. Per Inv 32 (issues #414, #509, #521) the loop
NEVER self-chains via the deprecated in-session wakeup mechanisms (see spec
Inv 32 for the forbidden set). Scheduling lives in the external system cron
WHERE AVAILABLE; on hosts where crontab is blocked, a durable `CronCreate`
heartbeat is the SANCTIONED fallback trigger (a Claude idle-REPL prompt
scheduler — durable, not an in-session wakeup harness). When work remains at
the end of a tick the loop refires near-immediately in a FRESH context
(Inv 33); when the queue is empty it relies on the heartbeat.

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

After the three markers, `set-evolve-mode.py on` invokes
`.claude/features/rabbit-auto-evolve/scripts/install-cron.py`, which uses
`detect-scheduler.py` (Inv 34) to choose the mechanism. WHERE crontab is
usable it idempotently installs the system-cron entry that fires the
headless tick (Inv 32 / issue #414) — the cron is the tick scheduler. WHERE
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

0. **Self-sync the working tree FIRST (Inv 38 / #524)** — BEFORE any phase
   script runs, so the whole tick executes one consistent (latest-merged)
   script version (the #450 mid-tick self-modification concern):
   `python3 .claude/features/rabbit-auto-evolve/scripts/sync-tree.py`.
   It verifies the tree is clean of uncommitted TRACKED changes (the
   safety-check.py Inv 5 condition), then runs `git pull --ff-only origin
   dev` to fast-forward local `dev` to the PRs this loop merged via `gh pr
   merge`. It uses `git pull --ff-only` — NEVER `git merge`: `settings.json`
   declares `deny: ["Bash(git merge *)"]`, an absolute permissions deny that
   beats any `allow` and even `bypassPermissions`, so a local merge of
   `origin/dev` is denied while `git pull` fast-forwards cleanly. On a dirty
   or non-fast-forwardable divergent tree it exits non-zero and fails loudly
   (surfaced + logged via `tick-log.py`); do NOT proceed with the tick on a
   non-zero sync — never force-merge, never narrow the `git merge` deny.
1. Run the running-guard (Inv 35 / D3, #526):
   `python3 .claude/features/rabbit-auto-evolve/scripts/running-guard.py`.
   It inspects `.rabbit-auto-evolve-running` and clears a STALE marker — STALE
   only when BOTH no live owner process AND `state.json` idle beyond the
   IDLE_WINDOW (default 600 s; either a live owner PID OR recent `state.json`
   activity keeps it FRESH), logging `stale marker cleared` via `tick-log.py`.
   On `{"action":"skip", "reason":"tick-running"}` (a FRESH marker — a tick is
   genuinely running) do NOT start a second tick: log
   `skipped: tick already running` and end the turn. On
   `{"action":"proceed",...}` continue.
2. Invoke
   `python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py`
   (which writes `.rabbit-auto-evolve-running` at repo root, carrying a DURABLE
   owner PID — the long-lived session PID, not the helper's transient PID,
   omitted when undeterminable — plus an ISO-8601 timestamp for the
   running-guard). Per
   Inv 17 the marker write is wrapped in a script so scope-guard does not
   deny the literal Bash command. Per Inv 19, `start-loop.py` additionally
   self-heals before writing the running marker: it deletes any stale
   `.rabbit-auto-evolve-stop-requested` (an explicit `start` cancels a
   pending stop) and bootstraps `.rabbit/auto-evolve-state.json` with
   defaults if it is missing, empty, or malformed (a valid existing
   state file is left untouched).
3. Run one `tick` by walking the shared scripted phase-walk — the dispatcher
   supplies ONLY Phase 5 (see "`tick` (internal)" below). Phase 11 runs
   `schedule-decision.py` (Inv 33) and the dispatcher schedules the
   immediate-refire when work remains — see "Scheduling" below.
4. End the turn. The HOUSEKEEPING tick is fired by the **system cron**
   installed at `on` (where crontab is available) running `tick-headless.py`;
   the DEVELOPMENT tick (phase 5 dispatch) is re-triggered by the scheduler
   firing `/rabbit-auto-evolve tick` in a FRESH context (Inv 32 amendment /
   #509). Every MACHINE wake-up fires the internal `tick`, NEVER the
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

### `log` (per-tick observability log — Inv 37, issue #404)

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
tick`, NEVER `/rabbit-auto-evolve start` (Inv 41). `tick` walks the scripted
phase-walk (pre-dispatch → dispatch → post-dispatch) and at phase 0 it READS
`.rabbit-auto-evolve-stop-requested` and halts cleanly when present — it NEVER
deletes the stop marker. The marker is cleared EXCLUSIVELY by an explicit user
`start` (`start-loop.py`, Inv 19); this is what makes a user stop HOLD across
heartbeats until the user explicitly resumes. `tick` therefore does NOT run
`start-loop.py`'s stop-cancel.

Walked by a live Claude session (via `start` or a cron-surfaced resume). The
in-session tick runs the SAME single shared scripted phase-walk the headless
tick runs (`run-tick-phases.py`, Inv 40); the dispatcher supplies ONLY Phase 5
(`dispatch`), the one phase that needs Claude. The dispatcher does NOT
hand-build any inter-phase data structure (state objects, handoffs) — every
phase handoff is script-to-script (stdin/stdout pipes or on-disk state
mutation). The deterministic walk runs in two segments around Phase 5:

1. **Pre-dispatch segment** (phases 0-1, running-guard, 2-4):
   ```
   python3 .claude/features/rabbit-auto-evolve/scripts/run-tick-phases.py pre-dispatch
   ```
   It runs the tick-start self-sync (Inv 38), the phase 0/1 stop/abort
   short-circuit, the running-guard (Inv 35), and phases 2-4
   (`fetch | triage | plan`). On `{"action":"skip",...}` a clean short-circuit
   fired (sync-fail, stop, abort, or tick-running) — run `end-tick.py` and end
   the turn. On `{"action":"proceed",...}` continue to Phase 5.
2. **Phase 5 (`dispatch`)** — the dispatcher's ONLY hand-driven phase. Dispatch
   the TDD subagents per the Stage-1/Stage-2 plan (Inv 26), each with
   `isolation: "worktree"` (Inv 28).
3. **Post-dispatch segment** (phases 6, 7-9, 10):
   ```
   python3 .claude/features/rabbit-auto-evolve/scripts/run-tick-phases.py post-dispatch
   ```
   It runs phase 6 (merge the PRs in the state's transient `merge_ready` hint),
   phases 7-9 (`run-post-merge.py` drain), and phase 10 (persist). Phase 10
   re-reads the on-disk state (already mutated by the phase scripts), drops the
   transient `merge_ready` key, and pipes the object through `update-state.py`.
   The dispatcher does NOT read `update-state.py` source or the state schema to
   assemble state — the persist is deterministic and identical to the headless
   tick's.
4. **Phase 11 (`schedule`)** — run `schedule-decision.py` (Inv 33) and schedule
   the immediate-refire when work remains (see "Scheduling" below).

Any phase MAY abort the tick early without affecting the next tick's ability to
pick up from disk-persisted state in `.rabbit/auto-evolve-state.json`. The
phase table below maps each phase to its owning script for reference; the live
session walks them via the two `run-tick-phases.py` segments plus Phase 5.

| # | Phase             | Script(s) invoked                            |
|---|-------------------|----------------------------------------------|
| 0 | `stop-check`      | `.claude/features/rabbit-auto-evolve/scripts/log-tick.py rotate` (rotate the observability log if >5MB — Inv 37) then `log-tick.py emit --record-kind tick-start …`; plus the file-existence check on `.rabbit-auto-evolve-stop-requested` |
| 1 | `restart-check`   | (none — file existence check on `.rabbit-auto-evolve-restart-needed`) |
| 1.5 | `post-merge-drain` | `.claude/features/rabbit-auto-evolve/scripts/run-post-merge.py` — drains any `pending_post_merge` owed by a previous truncated tick BEFORE fetch (Inv 30) |
| 2 | `fetch`           | `.claude/features/rabbit-auto-evolve/scripts/fetch-queue.py` |
| 3 | `triage`          | `.claude/features/rabbit-auto-evolve/scripts/triage-batch.py` (wraps `.claude/features/rabbit-auto-evolve/scripts/triage-issue.py` per issue) |
| 4 | `plan`            | `.claude/features/rabbit-auto-evolve/scripts/plan-batch.py` |
| 5 | `dispatch`        | (rabbit-feature-touch — TDD subagent dispatch) |
| 6 | `merge`           | `.claude/features/rabbit-auto-evolve/scripts/merge-prs.py --record-pending` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase merge` (records merged PRs to `pending_post_merge`) |
| 7-9 | `post-merge`    | `.claude/features/rabbit-auto-evolve/scripts/run-post-merge.py` — deterministically runs release (7) → cleanup (8) → catch-up (9) for every PR in `pending_post_merge`, then clears it (Inv 30) — see "Post-merge phases (Inv 30)" below |
|10 | `persist`         | `.claude/features/rabbit-auto-evolve/scripts/update-state.py` writes `.rabbit/auto-evolve-state.json` |
|11 | `schedule`        | `.claude/features/rabbit-auto-evolve/scripts/schedule-decision.py` — decide immediate-refire vs idle (Inv 33); on `immediate-refire` the DISPATCHER schedules the one-shot. See "Scheduling (Inv 32–33)" below |

### Post-merge phases (Inv 30 — issue #499)

Phases 7 (`release`), 8 (`cleanup`), and 9 (`catch-up`) used to be prose
walked by the LLM orchestrator. After phase 6 (`merge`) landed a large batch
of PRs, the orchestrator ended the tick for scale/context reasons and phases
7–9 were SILENTLY dropped (same class as #405 / #409 / #439). They are now
owned by a single deterministic, non-skippable script:

```
python3 .claude/features/rabbit-auto-evolve/scripts/run-post-merge.py
```

`run-post-merge.py` reads `pending_post_merge` (the merged PR numbers recorded
by `merge-prs.py --record-pending` in phase 6) from
`.rabbit/auto-evolve-state.json` and runs, IN ORDER:
`.claude/features/rabbit-auto-evolve/scripts/release-bump.py <pr#>`
(phase 7, once per PR) →
`.claude/features/rabbit-auto-evolve/scripts/cleanup-branches.py <pr-list>`
(phase 8, once) →
`.claude/features/rabbit-auto-evolve/scripts/classify-merge-restart.py <pr#>`
(phase 9, once per PR). On completion it clears `pending_post_merge`. An
empty/absent list is a clean no-op. A phase failure exits non-zero and leaves
`pending_post_merge` intact so the next tick's tick-start drain retries the
owed work.

Invoke `run-post-merge.py` in TWO places:

1. **After phase 6 (`merge`)** when any PR merged — the merge phase wrote the
   merged PR numbers via `merge-prs.py --record-pending`, so this drains them
   through phases 7–9 in the same tick.
2. **At tick START (phase 1.5, between `restart-check` and `fetch`)** — to
   DRAIN any owed post-merge work from a previous truncated tick BEFORE
   fetching new work. This is what makes the dropped-phase failure mode
   self-healing: even if a tick ends right after phase 6, the next tick
   finishes phases 7–9 before doing anything else.

A non-zero `run-post-merge.py` exit is an error-abort (Inv 20): run
`end-tick.py` and surface the failure rather than continue with owed work
silently dropped.

### Scheduling (Inv 32–33 — issues #414, #509, #521)

Phase 11 (`schedule`) is NO LONGER a pure no-op. It runs
`python3 .claude/features/rabbit-auto-evolve/scripts/schedule-decision.py`,
which counts open work (authoritatively, via `fetch-queue.py`), reads the
scheduler mechanism from `detect-scheduler.py`, logs the decision via
`tick-log.py`, and emits JSON:

- `{"decision":"immediate-refire","scheduler":"crontab"|"croncreate",
  "prompt":"/rabbit-auto-evolve tick","when":"~1min","croncreate":{...}}`
  when the queue is non-empty (Inv 33 / D1). The one-shot fires the internal
  `tick`, NEVER `start` (Inv 41) — a halting tick must never cancel a pending
  stop. The DISPATCHER then schedules
  the near-immediate (~1 min) ONE-SHOT in a FRESH context and ENDS the turn
  (do NOT continue inline):
  - **croncreate path:** invoke the actual one-shot `CronCreate(...)` per the
    emitted `croncreate` params. A script cannot call `CronCreate`; this tool
    action is the irreducible Claude step (exactly like phase 5 dispatch).
    The emitted `croncreate.cron` is a PINNED next-minute `M H * * *`
    expression (never `*/1 * * * *`), so a dropped `recurring` fails
    benignly (at most once/day at minute M, not an every-minute storm — Inv 33
    pinned-minute amendment, #531). Two non-negotiable dispatcher rules:
    - **Faithful flag passing (#531).** Pass `recurring` and `durable` to
      `CronCreate` EXACTLY as emitted (both `false`) — never rely on
      `CronCreate` defaults (its default is recurring), never
      hand-translate-and-drop a field (the #513 anti-pattern). Forward
      `croncreate.cron` verbatim too.
    - **At-most-one refire (#531).** Before creating a new refire one-shot,
      `CronList` and `CronDelete` any prior immediate-refire one-shot, so at
      most ONE is alive at a time; never create a refire whose cadence
      duplicates the recurring heartbeat.
  - **crontab path:** schedule the transient/`at`-style one-shot the emitted
    hint documents.
- `{"decision":"idle","detail":"rely on heartbeat"}` when the queue is empty.
  Schedule nothing; the recurring heartbeat (the `*/…` system-cron entry, or
  the durable `CronCreate` heartbeat on restricted hosts) fires the next
  check.

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
walks every deterministic phase EXCEPT phase 5 (`dispatch`), which requires
Claude:

- tick-start self-sync (Inv 38 / #524) — BEFORE any phase, it runs
  `python3 .claude/features/rabbit-auto-evolve/scripts/sync-tree.py` so the
  cron path also self-syncs to the latest merged scripts (`git pull
  --ff-only origin dev`, NEVER the permission-denied `git merge`). On a
  dirty/divergent tree it short-circuits to a clean no-op (logged) rather
  than run stale scripts.
- phase 0 (`stop-check`) + phase 1 (`restart-check`) — if
  `.rabbit-auto-evolve-stop-requested` or `.rabbit-auto-evolve-aborted`
  exists, the tick short-circuits to a clean no-op.
- phases 2–4 (`fetch | triage | plan`) — the canonical pipe.
- phase 5 (`dispatch`) — SKIPPED (no Claude session).
- phase 6 (`merge`) — `merge-prs.py --record-pending` for the PRs listed in
  the state's `merge_ready` field; skipped when there are none.
- phases 7–9 (`post-merge`) — `run-post-merge.py` drains
  `pending_post_merge`.
- phase 10 (`persist`) — `update-state.py`.
- phase 11 (`schedule`) — NO-OP in the headless tick: the recurring heartbeat
  owns the HOUSEKEEPING cadence (Inv 32 amendment). The development-tier
  immediate-refire (Inv 33) needs a live session and is handled in the
  SESSION tick's phase 11 via `schedule-decision.py`, not here.

`tick-headless.py` emits a single JSON result object on stdout summarizing
which phases ran (with `dispatch` always marked `"skipped"`). Dispatch
(phase 5) only happens during a live Claude session tick (`start` / `tick`).

### Tick exit invariant (Inv 20)

Per spec Inv 20, EVERY tick exit path MUST end by invoking
`python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py` as its
last action. `end-tick.py` deletes the `.rabbit-auto-evolve-running`
marker (mirror of `start-loop.py`'s write); without it the marker leaks
across sessions and the user has to remove it manually (which scope-guard
correctly denies, since `.rabbit-auto-evolve-*` markers are not on its
allowlist).

The four named exit paths are:

- **normal completion** — phase 11 (`schedule`) runs
  `schedule-decision.py` (Inv 33): if work remains, the DISPATCHER schedules
  the near-immediate fresh-context refire (croncreate one-shot, or the
  crontab transient hint) per the emitted params; if the queue is empty it
  relies on the heartbeat. Then
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py` runs, then
  the turn ends.
- **phase 0 halt** — `.rabbit-auto-evolve-stop-requested` observed at
  the top of the tick. Post the run summary, then run
  `python3 .claude/features/rabbit-auto-evolve/scripts/end-tick.py`,
  then end the turn (the cron is removed by `off`).
- **safety abort** — any safety violation during phases 6–8 writes
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
which performs a FULL teardown — it first removes the system-cron entry
(via `uninstall-cron.py`, Inv 32 / issue #414) so a torn-down mode never
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
`.rabbit-auto-evolve-aborted` with the abort reason and ends the turn.
The abort marker makes the cron-fired headless tick short-circuit to a
clean no-op, so the loop stays halted. The next SessionStart banner
surfaces the abort to the user.

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
