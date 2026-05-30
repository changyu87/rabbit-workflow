---
name: rabbit-issue
version: 1.0.0
owner: cyxu
deprecation_criterion: when GH Issues is replaced or the workflow moves to a different tracker; revisit when claude-plugins-official ships a GH Issues skill
description: Use whenever Claude detects intent to file, list, show, close, reopen, or otherwise lifecycle-manage a bug or enhancement in this repository's GitHub Issues — including casual phrasings like "file a bug", "log an enhancement", "open a feature request", "what bugs are open", "list issues for <feature>", "show issue 42", "work this bug", "close that issue", "mark issue N as not planned", or "reopen issue N". rabbit-issue REPLACES the retired rabbit-file feature; do NOT invoke rabbit-file or its scripts — they are gone. rabbit-issue wraps the `gh` CLI to operate on GitHub Issues, honours the `rabbit-managed` label as a safety guard so human-filed issues are never touched, and orchestrates the File / List / Work protocols against the three runtime scripts under `.claude/features/rabbit-issue/scripts/`. Trigger on any GH-Issues lifecycle phrasing — even when the user does not say "GitHub" or "issue" explicitly.
---

## Overview

Three modes — **File**, **List**, and **Work** — operate against GitHub
Issues via the `gh` CLI. Two issue types are supported: **bug** and
**enhancement** (GH's defaults). The repository is discovered at runtime
from `git remote get-url origin`; `gh auth status` must be green or the
scripts fail loudly with an actionable error.

rabbit-issue REPLACES the retired `rabbit-file` feature. The legacy
branch-backed bug-and-backlog (B/B) storage on `origin/bug-backlog-files`
is gone. Do not invoke `rabbit-file`, its scripts, or any
`item-status.py` / `file-item.py` under `.claude/features/rabbit-file/`.
All lifecycle operations route through this skill.

There are no slash commands. The invocation surface is direct script
invocation:

| Mode | Script | Purpose |
|---|---|---|
| File | `python3 .claude/features/rabbit-issue/scripts/file-item.py …`       | File a new bug or enhancement |
| Work | `python3 .claude/features/rabbit-issue/scripts/item-status.py …`     | Show, close, or reopen an issue |
| List | `python3 .claude/features/rabbit-issue/scripts/list-items.py …`      | List issues with type / feature / status filters |
| Show | `python3 .claude/features/rabbit-issue/scripts/item-status.py show <N>` | Print a single issue's JSON |

The shared helper `_gh.py` resolves the repo slug and wraps `gh` calls.

---

## Label Schema

Every issue filed via `rabbit-issue` carries **five** labels. The labels
are auto-created on demand (idempotent `gh label create … || true`) at
first `file-item.py` call — there is no separate bootstrap step.

| Label | Purpose | Cardinality |
|---|---|---|
| `bug` *(GH default)* | Type — exclusive with `enhancement` | exactly one of bug/enhancement |
| `enhancement` *(GH default)* | Type — exclusive with `bug` | exactly one of bug/enhancement |
| `rabbit-managed` | Distinguishes rabbit-filed issues from human-filed | required |
| `feature:<name>` | Feature scope | required, one per issue |
| `priority:<low\|medium\|high\|critical>` | Priority | required, one per issue |

The `rabbit-managed` label is load-bearing for the safety invariant
below. Do not strip it from issues filed via this skill.

---

## File Protocol

When the user confirms they want to file a bug or enhancement:

1. **Resolve feature scope** — invoke `rabbit-feature-scope` to identify
   the related feature. Ask the user only if the scope is ambiguous.
2. **Collect missing fields** — ask clarifying questions for any of
   `title`, `description`, `priority`. Do not invent values.
3. **Run `file-item.py`**:
   ```bash
   python3 .claude/features/rabbit-issue/scripts/file-item.py \
     --type bug|enhancement \
     --feature <feature-name> \
     --title "..." \
     --priority <low|medium|high|critical> \
     --description "..."
   ```
   The script auto-creates any missing labels, then calls
   `gh issue create` with all five labels attached.
4. **Report** the assigned issue number and URL back to the user. GH
   allocates the number; rabbit does not maintain a local counter.

---

## List Protocol

When the user wants to see open or closed issues:

```bash
python3 .claude/features/rabbit-issue/scripts/list-items.py \
  [--type bug|enhancement|all] \
  [--feature <feature-name>] \
  [--status open|closed]
```

Defaults: `--type all`, `--status open`, no feature filter. The script
calls `gh issue list` with the resolved label filters and prints a
deterministic, sorted summary.

Output format: `NUMBER  [TYPE]  [STATE]  [PRIORITY]  [feature:<name>]  TITLE`

Output is sorted ascending by issue number so repeated invocations
against the same repo state always print identical lines.

---

## Work Protocol

When the user asks to work, close, or reopen an issue:

1. **Fetch** — `python3 .claude/features/rabbit-issue/scripts/item-status.py show <N>`
   reads the issue from GH. If the issue is not found, inform the user
   and stop.

2. **Eval subagent** — dispatch a read-only default-model subagent with
   the fetched issue JSON and the affected feature's `docs/spec/spec.md`.
   It returns:
   - **Verdict**: `valid` (still relevant and reproducible) or
     `stale/invalid` with reason.
   - **Test gap analysis**: names the existing tests covering the
     affected behaviour and lists any missing tests that the implementer
     should add before turning RED → GREEN. A bug fix without an
     accompanying regression test is incomplete — surface this gap up
     front so the user can authorize the test work.

   The subagent is read-only: it does NOT edit code, file new items, or
   touch issue state.

3. **User-decision gate** — brief the user with the verdict, the test
   gap, and a clear recommendation:
   - Summarize verdict and reasoning.
   - Recommend close-without-work (if stale/invalid) or proceed (if
     valid).
   - Do NOT invoke `rabbit-feature-touch` until the user confirms.

4. **If the user chooses close without work**:
   ```bash
   python3 .claude/features/rabbit-issue/scripts/item-status.py close <N> \
     --reason not_planned \
     --comment "<why>"
   ```
   `not_planned` is the correct reason for closing stale or invalid
   issues. The safety guard below still applies.

5. **If the user confirms to proceed**:
   - Invoke `rabbit-feature-touch` in **normal mode**, passing the issue
     title + body as the request text (no special CLI flag, no "issue
     mode" — `rabbit-feature-touch` does NOT need to know about GH
     Issues at all; tracking and closure are rabbit-issue's concern).
   - The TDD cycle's implementation commit should include `Fixes #N` in
     the commit message so GitHub auto-closes the issue with
     `state_reason = completed` and auto-links the SHA in the Timeline
     once the PR merges to the default branch.
   - **After touch returns successfully — rabbit-issue verifies closure:**
     - **Auto-close path** — if the impl commit included `Fixes #N` AND
       the PR merged to the default branch, GH already closed the
       issue (`gh issue view <N>` shows `closed`). Nothing more to do.
     - **Fallback path** — otherwise (e.g., squash-merge stripped the
       trailer, the PR merged via the web UI without it, or the work
       landed via direct commit), rabbit-issue explicitly closes:
       ```bash
       python3 .claude/features/rabbit-issue/scripts/item-status.py close <N> \
         --reason completed \
         --comment "TDD cycle complete in <commit-sha>"
       ```
       Always verify state with `gh issue view <N>` before the
       fallback close so an already-closed issue is not re-closed.

---

## Safety Invariants

These guard the boundary between human-filed and rabbit-filed issues,
and between rabbit and the GH API.

- **`rabbit-managed` guard** — `item-status.py close` and
  `item-status.py reopen` refuse to act on issues that lack the
  `rabbit-managed` label. Human-filed issues stay out of rabbit's
  automation reach unless that label is explicitly applied. Do not work
  around the guard by adding the label without the human's consent;
  ask first.
- **`gh auth` required** — every script checks `gh auth status` and
  fails with an actionable error if authentication is not green. Do
  not fall back to unauthenticated calls.
- **GH remote only** — the repo slug is derived from
  `git remote get-url origin`. If `origin` is not a GitHub URL the
  scripts fail loudly. Do not patch the slug; redirect the user to fix
  the remote.

---

## Lifecycle

GH issue state is binary; `state_reason` distinguishes the close path.

```
                +-- reason: completed   --> closed (the fix landed)
                |
   open  --close---+-- reason: not_planned --> closed (stale / invalid)
     ^            |
     |            +-- reason: null        --> closed (legacy / external)
     |
   reopen <--- closed
```

- `state` ∈ {`open`, `closed`}
- `state_reason` ∈ {`completed`, `not_planned`, `null`}
  - `completed` — closed after a TDD fix (default close reason for work
    that landed). Set automatically by `Fixes #N` auto-close, or
    manually via `--reason completed` fallback.
  - `not_planned` — closed without work (stale or invalid).
  - `null` — pre-rabbit closures or external closes; not produced by
    this skill.
- Reopen restores `state = open` with `state_reason = reopened`.

SHA / event history is delegated entirely to GH's Timeline API. There
is no local `history` array and no `--fix-commits` parameter — the
closing-reference feature (`Fixes #N` in commit messages) auto-links
commits to issue closure and records the SHA in the timeline event.

---

## Why This Shape

- **GH Issues, not a custom branch.** The legacy `rabbit-file` feature
  maintained items as JSON on `origin/bug-backlog-files`. That gave us
  CLI-only auditability but cost a custom counter, custom history
  array, and custom worktree machinery — all of which GH already
  provides. Moving to GH Issues removes that surface entirely and lets
  the Timeline API own SHA history.
- **`rabbit-managed` label, not a private repo.** rabbit needs to
  automate issues without accidentally closing or reopening a human's
  issue. A label is the cheapest opt-in marker GH offers, and the guard
  is enforced at the script boundary (not at the gh layer) so the
  refusal is locatable in our code.
- **`Fixes #N` auto-close, not a `--fix-commits` flag.** GH already
  links commits to closures via the closing-reference syntax. Adding a
  rabbit-side flag would duplicate that work and drift from what
  reviewers see in the GH UI. The fallback exists for the rare
  squash-merge-stripped trailer case, not as the primary path.

---

## Scripts Reference

| Script | Purpose |
|---|---|
| `file-item.py` | File a new bug or enhancement (auto-creates labels) |
| `item-status.py` | `show <N>` / `close <N>` / `reopen <N>` (rabbit-managed guard enforced on close/reopen) |
| `list-items.py` | List with `--type`, `--feature`, `--status` filters; deterministic sort |
| `_gh.py` | Shared helper — repo slug discovery, `gh` invocation wrappers |
