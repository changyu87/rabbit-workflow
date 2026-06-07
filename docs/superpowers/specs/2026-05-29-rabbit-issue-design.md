---
feature: rabbit-issue
version: 1.0.0
owner: cyxu
deprecation_criterion: >
  When GH Issues is replaced or the workflow moves to a different tracker.
  Revisit when claude-plugins-official ships a GH Issues skill that subsumes
  this wrapper.
related_backlog: RABBIT-FILE-BACKLOG-16
status: brainstorm-approved (awaiting implementation plan)
---

# rabbit-issue — Replace `rabbit-file` with GitHub Issues

## Source

Per backlog `RABBIT-FILE-BACKLOG-16` ("Replace rabbit-file B/B system with
GitHub Issues integration for user installs"), augmented by 2026-05-29
brainstorm: the user wants a **full retirement** of the custom B/B branch
model in favor of GitHub Issues, applied to rabbit-self first (the original
backlog framed it for user-installs, but rabbit-self first validates the
design).

GitHub Issues provides everything the custom B/B system does and more:
- Built-in type labels (`bug`, `enhancement`) match our taxonomy
- Timeline events API records SHA-precise event history with stable IDs
- Closing references (`Fixes #N`) auto-link commits/PRs to issue closure
- `state_reason` enum (`completed`, `not_planned`, `duplicate`) covers our
  close-with-fix vs. close-without-work distinction
- No counter.json, no branch worktrees, no 16-retry push — GH allocates
  numbers server-side

No official Anthropic Claude Code plugin exists for GH Issues. The realistic
backends are (a) `github/github-mcp-server` (GitHub-published, heavyweight
MCP) or (b) thin scripts wrapping `gh` CLI. We pick (b) — it matches the
repo's `script > CLI > spec > prompt` tier and the machine-first +
bounded-scope philosophy.

---

## Architecture

**New feature** `rabbit-issue` at `.claude/features/rabbit-issue/` replaces
`rabbit-file`. Thin scripts wrap `gh issue` subcommands; the `SKILL.md`
defines the Work Protocol (file / list / work / show) with the eval-subagent
+ user-decision gate carried over from the existing skill.

**Three deliverables, in order:**

1. **New `rabbit-issue` v1.0.0** — scripts + SKILL.md + spec/contract
2. **One-shot `migrate.py`** — migrates existing B/B items
3. **Cleanup** — branch delete + old feature delete + migrate.py delete

---

## Renames vs. the retiring system

| Old (`rabbit-file`) | New (`rabbit-issue`) |
|---|---|
| Feature dir `.claude/features/rabbit-file/` | `.claude/features/rabbit-issue/` |
| Skill `rabbit-file` | `rabbit-issue` |
| Type `backlog` | `enhancement` (GH-standard) |
| Type `bug` | `bug` (unchanged, GH-standard) |
| `rabbit-feature-touch` "B/B mode" | "issue mode" |
| ID `RABBIT-CAGE-BUG-17` | `#214` (GH issue number) |
| Branch `bug-backlog-files` | (deleted) |
| `counter.json`, `branch_ops.py` | (deleted; GH allocates) |
| `item.json.history` array | GH Timeline (delegated) |
| `--fix-commits` parameter | `Fixes #N` in impl commit message |

---

## Label schema

GH-default type labels + rabbit-owned governance labels:

| Label | Purpose | Values | Required? |
|---|---|---|---|
| `bug` *(GH default)* | Type | exclusive with `enhancement` | exactly one of `bug`/`enhancement` |
| `enhancement` *(GH default)* | Type | exclusive with `bug` | exactly one of `bug`/`enhancement` |
| `rabbit-managed` | Distinguishes rabbit-filed from human-filed | flag | yes |
| `feature:<name>` | Feature scope | one per item | yes |
| `priority:<level>` | Priority | `low`/`medium`/`high`/`critical` | yes |

**Bootstrap:** labels are created on demand at first `file-item.py` call
via idempotent `gh label create … || true`. No separate bootstrap script.

**Safety guard:** `item-status.py` refuses to close/reopen issues that lack
the `rabbit-managed` label. Human-filed issues stay out of rabbit's reach
unless explicitly opted in (apply the label manually).

---

## Scripts

All at `.claude/features/rabbit-issue/scripts/`:

```
file-item.py    — file a new issue
                  args: --type bug|enhancement --feature <name>
                        --title "..." --priority <level> --description "..."
                  output: JSON { "number": 214, "url": "...", "type": "bug" }
                  behavior: ensure-labels (idempotent) → validate → gh issue create

item-status.py  — read or transition state
                  subcommands:
                    show <N>
                    close <N> --reason completed|not-planned [--comment "..."]
                    reopen <N> [--comment "..."]
                  output: JSON with current state
                  behavior: gh issue wrappers; refuse to act on issues missing
                            the `rabbit-managed` label

list-items.py   — list issues with filters
                  args: --type bug|enhancement|all
                        --feature <name>           (optional)
                        --status open|closed|all   (default: open)
                  output: one line per issue, deterministic sort by number ASC:
                          #N  [TYPE]  [STATUS]  [PRIORITY]  feature:<name>  TITLE

migrate.py      — ONE-SHOT, deleted post-cutover
                  walks origin/bug-backlog-files; for each item.json:
                    open  → gh issue create with mapped labels, record in manifest
                    closed → cp item.json → archive/bug-backlog/<feature>/<id>.json
                  writes archive/migration-manifest.json (committed to main)
                  prints summary; idempotent via manifest
```

Estimated runtime LOC: ~120 (vs. current `rabbit-file` at ~600+ including
`branch_ops.py`).

---

## Work Protocol mapping

| Step | Old | New |
|---|---|---|
| File | `file-item.py` → `branch_ops.allocate_id` + commit | `file-item.py` → `gh issue create --label bug,rabbit-managed,feature:X,priority:Y` |
| Fetch for eval | `branch_ops.fetch_item` from branch | `gh issue view <N> --json body,comments,timelineItems` |
| Eval subagent | reads item.json + spec | reads issue body + spec (unchanged shape) |
| User decision gate | brief + ask close/proceed | **unchanged** |
| Close without work | `item-status.py set --status close --reason ...` | `gh issue close <N> --reason not-planned --comment "<why>"` |
| Close after TDD | `item-status.py set --status close --fix-commits ...` | impl commit message includes `Fixes #<N>` → auto-closes on PR merge; closing-reference event records SHA automatically. Skill verifies closure post-merge. |
| List | `list-items.py --type bug/enhancement --status open` | `gh issue list --label rabbit-managed --label bug --state open` |
| Show | `item-status.py show` | `gh issue view <N>` |

Two behavioral simplifications:

1. **History/SHA tracking delegated to GitHub.** No `history` array in any
   local file. GH Timeline + closing-reference is the source of truth.
2. **No counter, no branch worktrees, no retry-on-push.** GH allocates `#N`
   server-side. Spec invariants 99-143 and 316-334 from the old spec retire.

---

## Contract

```json
{
  "provides": {
    "skill": "rabbit-issue",
    "scripts": ["file-item.py", "item-status.py", "list-items.py"],
    "issue_labels": ["bug", "enhancement", "rabbit-managed",
                     "feature:<name>", "priority:<low|medium|high|critical>"]
  },
  "reads": {
    "feature.json": "via rabbit-feature-scope (for --feature validation)",
    "github_issues": "via gh CLI, repo from `git remote get-url origin`"
  },
  "invokes": {
    "rabbit-feature-scope": "skill — resolve feature for ambiguous filings",
    "gh": "CLI tool — issue create/view/close/reopen/list, label create"
  },
  "never": [
    "writes to origin/bug-backlog-files (deleted by migration)",
    "maintains counter.json (GH allocates issue numbers)",
    "maintains item.json history array (GH Timeline is source of truth)",
    "closes/reopens issues lacking the `rabbit-managed` label"
  ]
}
```

---

## Migration sequence (9 steps)

```
1. Build & TDD-test rabbit-issue feature      (no production change yet)
2. Update rabbit-feature-touch "B/B mode" → "issue mode"
   - swap call surface from item.json paths to GH issue numbers
   - skill-level behavior identical
3. Dry-run migrate.py                          (--dry-run flag: report only)
4. Real migration:
   a. migrate.py creates GH issues for all OPEN items, applies labels
   b. migrate.py copies CLOSED item.json → archive/bug-backlog/<feature>/
   c. migrate.py writes archive/migration-manifest.json
5. Verify:
   - count_old_open == count_new_gh_issues
   - count_old_closed == count_archived_files
   - spot-check 2-3 items end-to-end (labels, body, priority)
6. Commit archive/ + migration-manifest.json to main (single PR for review)
7. Delete dedicated branch: git push origin --delete bug-backlog-files
8. Delete .claude/features/rabbit-file/ entirely (single commit)
9. Delete migrate.py from .claude/features/rabbit-issue/scripts/
```

Steps 1-2 are normal feature TDD. Steps 3-9 are the cutover; **step 7
requires explicit user approval** — `migrate.py` reports "ready to delete
branch" but does NOT execute it.

---

## Rollback plan

| Failure point | Recovery |
|---|---|
| Steps 1-2 | Discard branch, no production change |
| Step 4 (mid-migration) | `migrate.py` is idempotent via manifest; re-run skips already-migrated items. If GH issues were partially created, manually `gh issue close <N> --reason not-planned --comment "migration rollback"` and clear manifest entries |
| Step 6 (post-archive commit) | Revert the archive commit; closed items still readable from `origin/bug-backlog-files` (not yet deleted) |
| Step 7 (post-branch-delete) | Hardest — branch lives in `git reflog` briefly. Recovery: `git push origin <reflog-sha>:refs/heads/bug-backlog-files`. **Mitigation:** require human review of step 5 verification before approving step 7. |
| Step 8-9 | Restore from git history |

---

## Archive layout

```
archive/
├── bug-backlog/
│   ├── rabbit-cage/
│   │   ├── RABBIT-CAGE-BUG-3.json     (closed bug)
│   │   └── RABBIT-CAGE-BACKLOG-2.json (closed backlog)
│   └── <other-features>/
│       └── ...
└── migration-manifest.json
```

`migration-manifest.json` shape:

```json
{
  "migrated_at": "2026-05-29T...",
  "rabbit_workflow_repo": "changyu87/rabbit-workflow",
  "old_branch": "bug-backlog-files",
  "open_items": [
    {"old_id": "RABBIT-CAGE-BUG-17", "new_number": 214, "url": "..."}
  ],
  "closed_items": [
    {"old_id": "RABBIT-CAGE-BUG-3",
     "archive_path": "archive/bug-backlog/rabbit-cage/RABBIT-CAGE-BUG-3.json"}
  ]
}
```

The manifest is one-time provenance; not consulted at runtime by any
`rabbit-issue` script.

---

## Test plan

| Test file | Coverage | Approach |
|---|---|---|
| `test-file-item.py` | filing creates GH issue with correct labels | `gh` shim on PATH; assert call args |
| `test-item-status.py` | show/close/reopen wrap `gh issue` correctly | same shim |
| `test-list-items.py` | filter by type/feature/status, deterministic sort | same shim, fixture issues |
| `test-label-bootstrap.py` | `ensure-labels` is idempotent | shim returns exit 1 on duplicate |
| `test-rabbit-managed-guard.py` | scripts refuse to close/reopen issues missing `rabbit-managed` | safety regression |
| `test-migrate-dry-run.py` | dry-run reports correct counts, no writes | synthetic branch fixture |
| `test-migrate-real.py` | real migration creates expected issues, archives closed items, writes manifest | ephemeral test labels + cleanup |
| `test-migrate-idempotent.py` | re-running migrate.py is a no-op | runs twice, asserts second pass empty |
| `test-spec-presence.py` | spec.md + contract.md exist with frontmatter | reused from rabbit-file template |

`gh` CLI shim: a 20-line bash script that records args to a tmp file and
returns canned JSON — avoids hitting real GitHub from CI. Existing
`rabbit-file` tests use a similar pattern for git operations.

---

## Out of scope (deferred — separate backlogs)

- **GH Projects v2 board integration** — kanban / `status:in-progress`
  sub-states. Not needed for current workflow (we only model open/closed).
- **User-install plugin-mode GH-Issues backend** — the *original*
  framing of `RABBIT-FILE-BACKLOG-16`. Defer: install MVP doesn't ship
  `rabbit-file` at all today; revisit after rabbit-self cutover validates
  the design.
- **Cross-tracker abstractions** (Linear / Jira) — pick GH for v1.

---

## Risks

1. **`Fixes #N` auto-close depends on PR merge to default branch.** If we
   ever merge to a non-default branch or land via cherry-pick that doesn't
   trigger the closing reference, the issue stays open. Mitigation:
   skill verifies closure post-merge and falls back to explicit
   `gh issue close` if auto-close didn't fire.
2. **Branch deletion is hard to undo cleanly.** Step 7 gated on human
   review (see rollback plan).
3. **`gh` CLI auth assumed.** All scripts fail loudly with actionable
   error if `gh auth status` is not green. Documented in spec.
4. **No `rabbit-managed` discriminator on legacy GH issues.** If anyone
   has filed issues in `changyu87/rabbit-workflow` outside rabbit, they
   stay invisible to `list-items.py` (filtered out by label). This is
   intentional but worth flagging.

---

## Success criteria

- `rabbit-issue` skill files / lists / closes / reopens issues against
  `changyu87/rabbit-workflow` via `gh` CLI
- All open B/B items appear as GH issues with correct labels
- All closed B/B items appear under `archive/bug-backlog/<feature>/`
- `archive/migration-manifest.json` cross-references old ↔ new IDs
- `origin/bug-backlog-files` branch deleted
- `.claude/features/rabbit-file/` directory deleted
- `migrate.py` deleted
- All tests pass
- `rabbit-feature-touch` "issue mode" works end-to-end on a real GH issue:
  open → file fix branch → TDD → PR with `Fixes #N` → merge → auto-close
