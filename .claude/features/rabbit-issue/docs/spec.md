---
feature: rabbit-issue
version: 1.11.1
owner: rabbit-workflow team
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker; revisit when claude-plugins-official ships a GH Issues skill
---

# rabbit-issue

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](../feature.json).

## Purpose

Wrap the `gh` CLI to provide rabbit's file / list / work / show operations
against GitHub Issues — rabbit's issue store for bugs and enhancements.

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

Every issue filed via `rabbit-issue` carries the type, `feature:`, and
`priority:` labels; the `filed-by:` provenance label is optional (present
only for non-human filers), and the `housekeeping` category label is
optional (present only when the filer marks the issue as housekeeping work):

| Label | Purpose | Cardinality |
|---|---|---|
| `bug` *(GH default)* | Type — exclusive with `enhancement` | exactly one of bug/enhancement |
| `enhancement` *(GH default)* | Type — exclusive with `bug` | exactly one of bug/enhancement |
| `feature:<name>` | Feature scope | required, one per item |
| `priority:<low\|medium\|high\|critical>` | Priority | required, one per item |
| `filed-by:<rabbit\|autonomous-evolve>` | Provenance — non-human filer | optional; absent ⇒ human-filed |
| `housekeeping` | Category — housekeeping-wave work | optional; present ⇒ housekeeping sub-issue |

Labels are auto-created on demand at first `file-item.py` call via
idempotent `gh label create … || true`. No separate bootstrap script.

### Provenance label

The `filed-by:` provenance scheme is a **fixed enum** with exactly two
non-human values:

| Filer | `--filed-by` value | Label stamped |
|---|---|---|
| Human | *(omit `--filed-by`)* | none — human is the untagged default |
| Bot / wrapped rabbit script | `rabbit` | `filed-by:rabbit` |
| Autonomous evolve loop | `autonomous-evolve` | `filed-by:autonomous-evolve` |

`file-item.py` VALIDATES `--filed-by` against the enum `{rabbit,
autonomous-evolve}`. Human provenance is expressed by OMITTING
`--filed-by`, in which case no `filed-by:` label is stamped. Any explicit
value outside the enum — including the literal `human` or any
space-bearing/polluted value — is REJECTED with a clear error before any
gh call.

The label is additive — when present it does not change any of the other
labels. Provenance keeps loop-performance metrics answerable by querying
the `filed-by:autonomous-evolve` label.

### Housekeeping label

`housekeeping` is a sanctioned category label marking an issue as
housekeeping-wave work. It is applied at filing time in one deterministic
step via the `--housekeeping` flag on `file-item.py`:

| Flag | Label stamped |
|---|---|
| *(omit `--housekeeping`)* | none |
| `--housekeeping` | `housekeeping` |

When `--housekeeping` is passed, `file-item.py` adds the `housekeeping`
label in the same `gh issue create` call; when omitted, no `housekeeping`
label is stamped. The label is additive — it does not change any of the
other labels.

### Safety invariant

`item-status.py close` and `item-status.py reopen` refuse to act on
issues that are NOT **actionable** — an actionable issue is one carrying
a valid `feature:<name>` label. A raw, hand-filed GitHub issue with no
labels (or only stray labels) lacks a `feature:` label, so it is not
actionable and stays out of rabbit's automation reach.

### Lifecycle

- `state` is GH's binary `open` / `closed`
- `state_reason` ∈ {`completed`, `not_planned`, `null`}
  - `completed` — closed after TDD fix (default close reason)
  - `not_planned` — closed without work (stale or invalid issue)
- `item-status.py close --reason` accepts the hyphenated, shell-friendly
  forms `completed` and `not-planned`; the script translates `not-planned`
  to gh's space-separated `not planned` at the CLI boundary, which GitHub
  records as `state_reason = not_planned`.
- **Close-reason gating.** A close must assert something real:
  - `--reason completed` REQUIRES `--commit-sha <sha>`. The script
    validates that the SHA resolves to a real commit in the local git
    repo (`git rev-parse --verify <sha>^{commit}`). A missing or
    unresolvable SHA aborts the close before any gh call.
  - `--reason not-planned` REQUIRES `--reason-text <text>` of at least
    50 characters, free of reflexive-deferral boilerplate. The script
    rejects (case-insensitive substring match) any of: `too risky`,
    `out of scope`, `out-of-scope`, `declined autonomous dispatch`,
    `not now`, `later`, `don't want`, `do not want`. A specific reason
    that is long enough and clean is accepted.
  - **The validated `--reason-text` is PERSISTED, not just gated.** A
    `not-planned` close posts the reason-text as the close comment so the
    closed issue carries its justification as an audit trail. When
    `--comment` is also supplied, the close comment is the
    reason-text followed by the comment (reason-text first, separated by a
    blank line); when only `--reason-text` is given it is the close comment
    on its own. The comment travels with the same `gh issue close` call.
  - The actionability guard runs first (the safety boundary), then
    the reason gating, then the gh call — so a rejected close never
    issues `gh issue close` and never touches a non-actionable issue.
- Reopen restores `state = open`, `state_reason = reopened`

### SHA / event history

Delegated entirely to GitHub's Timeline API. No local `history` array,
no `--fix-commits` parameter. The "closing reference" feature
(`Fixes #N` in commit messages) auto-links commits to issue closure
and records the SHA in the timeline event.

### Repository discovery

`rabbit-issue` ALWAYS targets the upstream rabbit-workflow repo,
regardless of the cwd's git remote. Bugs about rabbit go to rabbit's
repo, period — never to the user's project repo.

`_gh.py` resolves the target repo slug as:

1. The `RABBIT_ISSUE_REPO` environment variable when set (override for
   forks, testing, etc. — e.g. `RABBIT_ISSUE_REPO=myfork/rabbit-workflow`).
2. Otherwise the const `RABBIT_REPO_DEFAULT = "changyu87/rabbit-workflow"`
   declared at module top in `_gh.py`.

`_gh.py` does NOT call `git remote get-url origin` at any point — in
plugin installs the cwd is the user's project, which would silently
direct bugs to the wrong target.

Scripts still fail loudly when `gh auth status` is not green.

### Reading issue comments

When rabbit-issue needs to read an issue's comment bodies, it MUST go
through the JSON API — `gh issue view <N> --json comments` — and parse
the returned JSON, NOT the human-readable `gh issue view <N> --comments`
view.

`gh issue view <N> --comments` triggers a deprecated Projects-classic
`projectCards` GraphQL field on repos that touch that path. On this repo
that request FAILS and returns an EMPTY body, so comments appear absent
even when they are present — a silent correctness trap. The
`--json comments` path does NOT hit the deprecated field and returns the
comment bodies reliably; `_gh.py` exposes `gh_issue_comments(number)` as
the only sanctioned comment-read path.

## What this feature does NOT define

- **Branch-backed item storage** — out of scope; GH Issues is the
  backing store and the GH Timeline owns history.
- **GH Projects v2 boards / kanban / sub-status workflows** — out of
  scope; if needed, file a separate issue.
- **Cross-tracker abstractions** (Linear, Jira, etc.) — only `gh` is
  supported in v1.
- **User-install plugin-mode backend** — deferred until rabbit-self
  validates the design; the install MVP does not ship `rabbit-issue` yet.
- **The TDD cycle** — `rabbit-feature-touch` (in `rabbit-feature`)
  drives TDD; the Work Protocol invokes it via its default full
  seven-step TDD cycle (NOT the lightweight Override Path), passing the
  issue title + body as the request text. `rabbit-issue` does not own
  that cycle and does not invent a "normal mode" / "issue mode" of it —
  `rabbit-feature-touch` defines no such mode.

## Tests

`test/run.py` runs the end-to-end suite. The suite uses a `gh` CLI
shim (`test/gh_shim.sh`) on `PATH` to avoid hitting real GitHub
during unit tests.
