---
name: rabbit-auto-evolve
version: 0.7.0
owner: cyxu
deprecation_criterion: when Claude Code or rabbit gains a native always-on autonomous-agent mode that supersedes this skill
description: Self-driving rabbit loop that continuously fetches open `rabbit-managed` GitHub issues, triages each one, dispatches TDD subagents to implement actionable work, merges approved PRs into `dev`, tags versioned releases, and reschedules itself via `ScheduleWakeup` until the user issues an explicit stop. Invoke for any natural-language phrasing matching "start auto-evolve", "stop the loop", "auto-evolve status", "let rabbit run", "begin autonomous evolve", or any `/rabbit-auto-evolve <subcommand>` form. Run `/rabbit-auto-evolve on` first, then restart Claude (so `permissions.defaultMode: bypassPermissions` from `settings.local.json` is picked up), then `/rabbit-auto-evolve start`.
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

On success, prints a user-facing line instructing the user to **restart
Claude** (so `permissions.defaultMode: bypassPermissions` from
`settings.local.json` is picked up) and then run `/rabbit-auto-evolve
start`.

### `start`

Begin or resume the loop. Verifies three preconditions in order:

1. `.rabbit-auto-evolve-active` marker exists at repo root.
2. `human-approval` is off (i.e. `.rabbit-human-approval-bypass` present).
3. `bypass-permissions` is on (i.e. `.claude/settings.local.json` has
   `permissions.defaultMode == "bypassPermissions"`).

If any precondition fails, refuse with a clear message naming the missing
condition. On all-pass:

1. Invoke
   `python3 .claude/features/rabbit-auto-evolve/scripts/start-loop.py`
   (which writes `.rabbit-auto-evolve-running` at repo root). Per Inv 17
   the marker write is wrapped in a script so scope-guard does not deny
   the literal Bash command.
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

read-only. Prints to stdout:

- queue length (from `.rabbit/auto-evolve-state.json` `queue` field)
- in-flight issue set (from `in_flight`)
- last-merged PR (from `last_merged_sha`)
- last-tagged version (from `last_tagged_version`)
- consecutive-failure count (from `consecutive_failures`)
- which restart marker (if any) is present
  (`.rabbit-auto-evolve-active`, `.rabbit-auto-evolve-running`,
  `.rabbit-auto-evolve-stop-requested`,
  `.rabbit-auto-evolve-restart-needed`, `.rabbit-auto-evolve-aborted`)

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
| 3 | `triage`          | `.claude/features/rabbit-auto-evolve/scripts/triage-issue.py` (per issue) |
| 4 | `plan`            | `.claude/features/rabbit-auto-evolve/scripts/plan-batch.py` |
| 5 | `dispatch`        | (rabbit-feature-touch — TDD subagent dispatch) |
| 6 | `merge`           | `.claude/features/rabbit-auto-evolve/scripts/merge-prs.py` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase merge` |
| 7 | `release`         | `.claude/features/rabbit-auto-evolve/scripts/release-bump.py` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase release --next-tag vX.Y.Z` |
| 8 | `cleanup`         | `.claude/features/rabbit-auto-evolve/scripts/cleanup-branches.py` → `.claude/features/rabbit-auto-evolve/scripts/safety-check.py --phase cleanup` |
| 9 | `catch-up`        | `.claude/features/rabbit-auto-evolve/scripts/classify-merge-restart.py` (per merged PR) |
|10 | `persist`         | `.claude/features/rabbit-auto-evolve/scripts/update-state.py` writes `.rabbit/auto-evolve-state.json` |
|11 | `schedule`        | `ScheduleWakeup` (unless stop-check matched) |

`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py` is NOT
invoked by `tick` — it runs only when the user flips the mode via
`/rabbit-auto-evolve on|off`.

### `off`

Deactivate auto-evolve mode. Invokes
`.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py off`,
which reverses the three `on` mutations in inverse order:

1. Delete `.rabbit-auto-evolve-active`.
2. Delete the `permissions.defaultMode` key from
   `.claude/settings.local.json`.
3. Delete `.rabbit-human-approval-bypass`.

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

`safety-check.py` enforces these; `merge-prs.py` and
`cleanup-branches.py` also refuse defense-in-depth.
