---
feature: rabbit-issue
version: 1.0.0
owner: cyxu
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker; revisit when claude-plugins-official ships a GH Issues skill
---

# rabbit-issue

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../../feature.json).

## Purpose

Wrap the `gh` CLI to provide rabbit's file / list / work / show operations
against GitHub Issues, replacing the retiring `rabbit-file` feature's
custom branch-backed bug-and-backlog (B/B) system.

## Schema / Behavior

### Surface

Three runtime scripts under `.claude/features/rabbit-issue/scripts/`:

- `file-item.py` — file a new bug or enhancement issue
- `item-status.py` — show, close, or reopen an issue
- `list-items.py` — list issues with type / feature / status filters

Plus a shared helper module `_gh.py`.

A single `rabbit-issue` skill (under `skills/rabbit-issue/SKILL.md`)
defines the Work Protocol that orchestrates the three runtime scripts.

### Label schema

Every issue filed via `rabbit-issue` carries five labels:

| Label | Purpose | Cardinality |
|---|---|---|
| `bug` *(GH default)* | Type — exclusive with `enhancement` | exactly one of bug/enhancement |
| `enhancement` *(GH default)* | Type — exclusive with `bug` | exactly one of bug/enhancement |
| `rabbit-managed` | Distinguishes rabbit-filed issues from human-filed | required |
| `feature:<name>` | Feature scope | required, one per item |
| `priority:<low\|medium\|high\|critical>` | Priority | required, one per item |

Labels are auto-created on demand at first `file-item.py` call via
idempotent `gh label create … || true`. No separate bootstrap script.

### Safety invariant

`item-status.py close` and `item-status.py reopen` refuse to act on
issues that lack the `rabbit-managed` label. Human-filed issues stay
out of rabbit's automation reach unless the label is explicitly
applied.

### Lifecycle

- `state` is GH's binary `open` / `closed`
- `state_reason` ∈ {`completed`, `not_planned`, `null`}
  - `completed` — closed after TDD fix (default close reason)
  - `not_planned` — closed without work (stale or invalid issue)
- Reopen restores `state = open`, `state_reason = reopened`

### SHA / event history

Delegated entirely to GitHub's Timeline API. No local `history` array,
no `--fix-commits` parameter. The "closing reference" feature
(`Fixes #N` in commit messages) auto-links commits to issue closure
and records the SHA in the timeline event.

### Repository discovery

The target repo slug is derived at runtime from
`git remote get-url origin`. All scripts fail loudly with an
actionable error if:

- `gh auth status` is not green, or
- the `origin` remote is not a GitHub URL.

## What this feature does NOT define

- **Branch-backed item storage** — `rabbit-file` owned that; retired by
  this feature's predecessor cutover.
- **GH Projects v2 boards / kanban / sub-status workflows** — out of
  scope; if needed, file a separate backlog.
- **Cross-tracker abstractions** (Linear, Jira, etc.) — only `gh` is
  supported in v1.
- **User-install plugin-mode backend** — the original
  `RABBIT-FILE-BACKLOG-16` framing was for user installs; deferred
  until rabbit-self validates the design. The install MVP does not
  ship `rabbit-issue` yet.
- **The TDD cycle** — `rabbit-feature-touch` (in `rabbit-feature`)
  drives TDD; `rabbit-issue` is consumed by it in "issue mode" but
  does not own that cycle.

## Tests

`test/run.py` runs the end-to-end suite. The suite uses a `gh` CLI
shim (`test/gh_shim.sh`) on `PATH` to avoid hitting real GitHub
during unit tests; the live smoke test is operational verification
only and is not part of `run.py`.

Per the TDD state machine: spec authored here, then transition to
`test-red` once the test files land, then to `impl`/`test-green`
as the runtime scripts come online.
