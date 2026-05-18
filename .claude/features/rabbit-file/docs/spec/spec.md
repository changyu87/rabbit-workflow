# rabbit-file

Structured source of truth is feature.json.

## Purpose

Unified bug and backlog filing and lifecycle for all rabbit features.
Replaces rabbit-bug and rabbit-backlog. All items stored on
origin/bug-backlog-files branch, never on main.

## Scripts

- branch_ops.py: All git operations against origin/bug-backlog-files.
  Uses git worktree at .claude/tmp/bug-backlog-files (gitignored).
  Exposes: allocate_id(feature, type_), commit_item(feature, type_, id_str, item),
  fetch_item(feature, type_, id_str), read_branch(feature, type_, status).
  Auto-initializes orphan branch and counter.json on first use.
  ID format: <FEATURE-UPPER>-BUG-N or <FEATURE-UPPER>-BACKLOG-N
  e.g. feature="rabbit-cage", type_="bug", N=17 → "RABBIT-CAGE-BUG-17".
  counter.json schema: {"next": N} where N is the next unused integer (starts at 1).
  allocate_id reads N, writes N+1, commits "counter: reserve <ID>", pushes.
  commit_item writes item.json, commits "item: <id_str>", pushes, backfills commit_sha.
  Internal helpers (not exported): _worktree(repo_root), counter_path(wt, feature, type_),
  read_counter(wt, feature, type_), write_counter(wt, feature, type_, n).

- file-item.py: Files a new bug or backlog item. Args: --type bug|backlog
  --feature F --title T --priority low|medium|high|critical --description D.
  Calls branch_ops.allocate_id then branch_ops.commit_item.
  Prints assigned ID and commit SHA to stdout.

- item-status.py: Reads, transitions, or updates fields on an item.
  Subcommands: get, set, update.
  - get --feature F --type T --id ID — prints current status.
  - set --feature F --type T --id ID --status open|close --reason R
    [--fix-commits SHA] — transitions status. Appends history entry
    {ts, actor, action=opened|closed, note=reason, [fix_commits]}.
  - update --feature F --type T --id ID --field <name> --value <val>
    --reason R — mutates a single mutable field on an OPEN item.
    Supported fields: priority, title, description. Other fields
    (name, type, status, closed, history, related_feature, filed,
    filed_by, commit_sha) are immutable and rejected with a clear error.
    For --field priority, --value must be one of low|medium|high|critical.
    Update is REJECTED on closed items (status != "open") with a clear
    error directing the user to reopen first. Appends history entry
    {ts, actor, action=updated, field, old_value, new_value, note=reason}.
  All subcommands call branch_ops.fetch_item; mutating subcommands call
  branch_ops.commit_item.

- list-items.py: Lists items from origin/bug-backlog-files. Args:
  --type bug|backlog|all --feature F --status open|close.
  Output format: NAME  [TYPE]  [STATUS]  [PRIORITY]  TITLE.
  If branch missing, prints guidance to file first.

## item.json Schema

Fields: name, type (bug|backlog), title, status (open|close), priority
(low|medium|high|critical), description, related_feature, filed (ISO8601),
filed_by, closed (ISO8601 or null), history (array of {ts, actor, action, note}).

## Branch Layout

origin/bug-backlog-files root:
  rabbit/features/<feature>/bugs/counter.json
  rabbit/features/<feature>/bugs/<FEATURE-BUG-N>/item.json
  rabbit/features/<feature>/backlogs/counter.json
  rabbit/features/<feature>/backlogs/<FEATURE-BACKLOG-N>/item.json

## Invariants

- branch_ops.py MUST use git worktree at a UNIQUE per-process path under
  .claude/tmp/ for all writes. The path format is
  .claude/tmp/bug-backlog-files-<pid> where <pid> is the current process ID.
  Each process gets its own isolated worktree so concurrent invocations from
  different agents do not collide on the same filesystem path. Worktree is
  always cleaned up via try/finally. The legacy fixed path
  .claude/tmp/bug-backlog-files MUST NOT be used (it caused FileNotFoundError
  and stale-state races under concurrent agent dispatch — RABBIT-FILE-BUG-18).
- branch_ops._worktree() MUST check out the worktree branch using
  `git checkout -B bug-backlog-files origin/bug-backlog-files` (capital -B)
  after fetching origin/bug-backlog-files. This unconditionally resets the
  local tracking branch to the freshly-fetched remote tip, so that reads see
  the latest committed items and writes never push from a stale base
  (preventing non-fast-forward push failures). The fallback two-step
  try/checkout-local + checkout-b sequence MUST NOT be used.
- branch_ops push operations (counter commit, item commit, commit_sha
  backfill) MUST be wrapped in a retry loop with up to 3 attempts. On a
  non-fast-forward push failure, the retry MUST re-fetch
  origin/bug-backlog-files, reset the worktree branch to the freshly-fetched
  remote tip (`git checkout -B bug-backlog-files origin/bug-backlog-files`),
  re-apply the local changes (re-write counter.json or item.json with the
  same values, or reserve a fresh ID if the counter slot was taken by
  another process), and retry the commit + push. After 3 failed attempts
  the operation raises RuntimeError with a clear diagnostic.
- branch_ops.allocate_id MUST be called before commit_item (counter reserves the ID slot).
- item-status.py set MUST require --reason on every transition.
- item-status.py update MUST require --field, --value, and --reason.
  The set of mutable fields is exactly {priority, title, description}.
  Any other --field value (including name, type, status, closed,
  history, related_feature, filed, filed_by, commit_sha) is rejected
  with exit non-zero and a stderr message naming the rejected field.
- item-status.py update MUST reject items where status != "open" with a
  clear stderr error directing the user to reopen the item first; no
  history entry is appended on rejection.
- The history entry appended by item-status.py update has shape
  {ts, actor, action: "updated", field, old_value, new_value, note}
  where note carries the --reason text. This is distinct from the
  open/closed entries written by `set`, which have shape
  {ts, actor, action: "opened"|"closed", note, [fix_commits]}.
- Direct edits to item.json on the bug-backlog-files branch are
  prohibited. All mutations go through file-item.py (create),
  item-status.py set (status transitions), or item-status.py update
  (field mutations). This guarantees every mutation has an audit
  trail in the history array.
- SKILL.md MUST include a user-decision gate in Work Protocol before invoking
  rabbit-feature-touch.

## Out of scope

- Bug triage (rabbit-triage.sh)
- Feature scaffolding (rabbit-cage)
- Legacy data in .claude/archive/

## Tech Stack

All runtime scripts and test harnesses are Python. No shell (.sh) scripts are used.

## Tests

test/run.py runs all test suites. Transitions via tdd-step.py.
