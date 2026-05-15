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

- item-status.py: Reads or transitions item status. Subcommands: get, set.
  set requires --status open|close --reason R. Optional --fix-commits SHA.
  Calls branch_ops.fetch_item then branch_ops.commit_item.

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

- branch_ops.py MUST use git worktree at .claude/tmp/bug-backlog-files for
  all writes. Worktree is always cleaned up via try/finally.
- branch_ops.allocate_id MUST be called before commit_item (counter reserves the ID slot).
- item-status.py set MUST require --reason on every transition.
- SKILL.md MUST include a user-decision gate in Work Protocol before invoking
  rabbit-feature-touch.

## Out of scope

- Bug triage (rabbit-triage.sh)
- Feature scaffolding (rabbit-cage)
- Legacy data in .claude/archive/

## Tests

test/run.sh runs all test suites. Transitions via tdd-step.sh.
