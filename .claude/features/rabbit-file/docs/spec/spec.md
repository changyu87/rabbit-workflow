---
feature: rabbit-file
version: 0.3.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when a unified tracking system replaces file-based bug and backlog management
status: active
---

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
  fetch_item(feature, type_, id_str), read_branch(feature, type_, status),
  release_id(feature, type_, id_str), branch_exists().
  Auto-initializes orphan branch and counter.json on first use.
  Canonical ID format: `UPPER(feature)-UPPER(type)-N`. Hyphens already
  present in the feature name are preserved verbatim (NOT escaped, NOT
  collapsed). Examples:
    feature="rabbit-cage",  type_="bug",     N=17 → "RABBIT-CAGE-BUG-17"
    feature="my-feature-x", type_="backlog", N=3  → "MY-FEATURE-X-BACKLOG-3"
    feature="single",       type_="bug",     N=1  → "SINGLE-BUG-1"
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
  Subcommands: get, set, update, show.
  - get --feature F --type T --id ID — prints current status.
  - show --feature F --type T --id ID — prints the full item.json
    (pretty-printed JSON) to stdout. Read-only. Exits non-zero with a
    clear stderr error if the item is missing.
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
  Output MUST be deterministic: items are sorted by `name` (ID string)
  in ascending order before printing, so repeated invocations against
  the same branch state always print identical output. When the
  origin/bug-backlog-files branch does not exist, list-items.py MUST
  print branch-missing guidance regardless of whether filter flags
  were passed — "no branch" is a distinct condition from "no items
  matched filters" and the operator MUST be told which one occurred.

## item.json Schema

Fields: name, type (bug|backlog), title, status (open|close), priority
(low|medium|high|critical), description, related_feature, filed (ISO8601),
filed_by, closed (ISO8601 or null), history (array of {ts, actor, action, note}).

> Note: item.json schema is trusted on read — fetch_item returns whatever
> JSON loads without semantic validation. Malformed-JSON parse errors are
> logged (BUG-24); semantic violations (missing required fields) flow
> through silently. Schema validation is out of scope for now; add
> validation if a downstream consumer requires it.

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
- branch_ops._worktree() MUST set the worktree HEAD to the freshly-fetched
  origin/bug-backlog-files tip after `git fetch origin bug-backlog-files`.
  This guarantees reads see the latest committed items and writes never push
  from a stale base (preventing non-fast-forward push failures). The
  implementation MUST use either (a) `git checkout -B bug-backlog-files
  origin/bug-backlog-files` (capital -B) when no other worktree currently
  has bug-backlog-files checked out, OR (b) a detached HEAD pointing at
  origin/bug-backlog-files for concurrent-safe operation when the shared
  local branch ref would otherwise collide across per-process worktrees.
  Push from a detached HEAD MUST use the refspec `HEAD:bug-backlog-files`.
  The fallback two-step try/checkout-local + checkout-b sequence MUST NOT
  be used.
- branch_ops push operations (counter commit, item commit, commit_sha
  backfill) MUST be wrapped in a retry loop with a bounded number of
  attempts (implementation-defined, at least 3, currently 16). On a
  non-fast-forward push failure OR a transient remote ref-lock contention
  error ("cannot lock ref", "failed to update ref"), the retry MUST
  re-fetch origin/bug-backlog-files, reset the worktree HEAD to the
  freshly-fetched remote tip, re-apply the local changes (re-write
  counter.json or item.json with the same values, or reserve a fresh ID
  if the counter slot was taken by another process), and retry the
  commit + push. A short jittered backoff between attempts decorrelates
  concurrent pushers. After the configured attempt budget is exhausted
  the operation raises RuntimeError with a clear diagnostic that names
  the attempt count and the last underlying error.
- branch_ops.allocate_id MUST be called before commit_item (counter reserves the ID slot).
- item-status.py set MUST require --reason on every transition.
- item-status.py set MUST short-circuit a no-op transition (same status)
  with exit 0 and a clear stdout message naming the current status; no
  history entry is appended and no commit is created. This prevents the
  bug-backlog-files branch from accumulating misleading history entries
  with action=opened|closed that describe transitions that did not
  actually change state. Tests MUST cover both the close→close and
  open→open no-op cases.
- commit_item's second push (commit_sha backfill on the just-written
  item.json) MUST use the same retry-with-fetch+reset+reapply mechanism
  as the primary push. The backfill push contains the SHA of the
  primary commit and is essential for downstream consumers (PR creation,
  release notes) to find the resolving commit; a silent failure leaves
  item.json without commit_sha and breaks every consumer. The retry
  budget and backoff policy MUST be identical to the primary push.
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
- SKILL.md MUST NOT illustrate the legacy fixed-path worktree
  `.claude/tmp/bug-backlog-files` (without the `-<pid>` suffix) in
  user-facing prose, the File Protocol Phase A/B narrative, or the
  `branch_ops.py Lifecycle` section. All worktree path references
  MUST use the per-process form `.claude/tmp/bug-backlog-files-<pid>`
  so the documented behaviour matches the per-pid invariant above.
  Documenting a path the code never creates misleads operators who
  inspect or clean disk state (BUG-34).
- SKILL.md MUST NOT reference any `/rabbit-file …` slash-command
  invocation. The Overview declares "there are NO slash commands";
  every other section (including the List Protocol's branch-missing
  guidance) MUST be consistent. Canonical user-facing invocations are
  the direct `python3 .claude/features/rabbit-file/scripts/…` script
  calls listed in the Overview table (BUG-34).
- SKILL.md List Protocol MUST document (a) the deterministic
  sort-by-name output contract mandated for list-items.py and (b) the
  distinct "branch does not exist" condition versus the "no items
  matched filters" condition. These two operator-facing facts
  originate in this spec's invariants for list-items.py; the skill
  MUST surface them so operators know the guarantees without having
  to read spec.md (BUG-34).
- feature.json `surface.skills` MUST be a non-empty array containing
  the entry `rabbit-file` (matching the deployed skill directory
  `skills/rabbit-file/SKILL.md`). An empty `surface.skills` while a
  SKILL.md exists violates the surface-declaration contract: build
  and scope tooling reads this surface to identify deployable skills,
  and an empty entry causes the SKILL.md to be silently ignored
  (BUG-34).
- The feature MUST declare a `docs/spec/contract.md` document
  following the schema used by sibling features (top-level JSON block
  with `provides`, `reads`, `invokes`, `manages`, and `never` keys;
  YAML frontmatter carrying `feature`, `version`, `template_version`,
  `owner`, and `deprecation_criterion`). This satisfies the policy
  mandate "Every component declares its contract"
  (spec-rules.md §2). The contract enumerates the provided scripts
  (file-item.py, item-status.py, list-items.py, branch_ops.py), the
  consumed files and external state, the invoked tools, the runtime
  markers managed (none), and the explicit "never does" list
  (BUG-34).
- Both file-item.py (at filing time) and item-status.py update (at
  field mutation time) MUST enforce PER-FIELD length limits on title
  and description values (BACKLOG-7):
    MAX_TITLE_LEN = 200
    MAX_DESCRIPTION_LEN = 10240   (10 KiB)
  These limits are asymmetric: titles are short labels, descriptions
  are long-form. The shared 500-char cap from the pre-BACKLOG-7
  implementation is REMOVED — it was both too tight (blocking
  legitimate descriptions) and broke the file/update symmetry (filing
  accepted any size; only update enforced).
  Values exceeding the per-field limit are rejected with exit non-zero
  and a stderr error naming the field, the limit, and the actual length.
  Both scripts import the constants and the validator from a single
  source-of-truth module (`branch_ops.py` or a sibling — implementer's
  choice) so the limits cannot drift between file and update paths.
- Both file-item.py and item-status.py update MUST sanitize title and
  description values by stripping ASCII control characters EXCEPT the
  whitespace characters tab (`\t`), newline (`\n`), and carriage return
  (`\r`) before length validation (BACKLOG-7). This protects
  `list-items.py` output from terminal escape injection (a title
  containing `\x1b[2J` would clear the user's terminal on list).
  The sanitize step runs first, then the length check runs on the
  sanitized value. The sanitized value is what gets written to
  `item.json`, so the on-disk artifact is always free of forbidden
  control characters.
- file-item.py MUST NOT leave an ID slot orphaned on commit_item
  failure. When commit_item raises after allocate_id succeeded,
  file-item.py MUST call branch_ops.release_id(feature, type_, id_str)
  to roll back the counter slot when safe (the counter still points one
  past the just-allocated ID — i.e. no other process has allocated
  above it). release_id is best-effort: if the slot has already been
  consumed by another process, it is left alone (no error) and the
  counter advances normally. The caller surfaces the original
  commit_item error to the user; rollback success is reported on stderr.
- read_branch MUST log a structured warning to stderr for every
  malformed item.json it encounters (JSONDecodeError, OSError). The
  warning names the file path and the underlying error. The malformed
  item is then skipped. Silent skipping (the previous behaviour) hides
  data corruption from operators.
- branch_ops.commit_item MUST NOT mutate the caller-supplied item dict.
  The caller's dict is treated as input-only; commit_sha backfill is
  performed on an internal copy. This guarantees callers can re-use
  their item dict for retry/logging without observing surprise fields.
- branch_ops module MUST expose the canonical branch name and identity
  as module-level constants (`BRANCH`, `IDENTITY_NAME`,
  `IDENTITY_EMAIL`) so downstream tooling can reference them without
  duplicating string literals.
- branch_ops._ensure_branch bootstraps the orphan bug-backlog-files
  branch on first use (per the Scripts section), with no
  topology-specific defensive guard. Rabbit assumes a standalone
  workspace topology: every workspace's `origin` points directly at the
  authoritative remote (e.g. GitHub), never at another local workspace.
  Chained workspaces (wsN → wsN-1 → ... → GitHub) are unsupported; the
  BUG-32 local-origin guard and `_is_local_origin` helper were removed
  in BACKLOG-12 as part of that posture. An operator who misconfigures
  `origin` to a local filesystem path will surface a normal git error
  on first push attempt — no extra defensive scaffolding sits in the
  hot path to detect that case.

## Out of scope

- Bug triage (rabbit-triage.sh)
- Feature scaffolding (rabbit-cage)
- Legacy data in .claude/archive/

## Tech Stack

All runtime scripts and test harnesses are Python. No shell (.sh) scripts are used.

## Tests

test/run.py runs all test suites. Transitions via tdd-step.py.
