# rabbit-file Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Critical workflow rule:** Every write to `.claude/features/rabbit-file/` MUST go through `/rabbit-feature-touch`. Do NOT write feature files directly. The only exceptions are Task 0 (archive, scope override) and Task 1 (initial scaffold, scope override — because the feature does not yet exist for rabbit-feature-touch to act on).

**Goal:** Replace `rabbit-bug` and `rabbit-backlog` with a single unified `/rabbit-file` skill that stores items on a dedicated branch `origin/bug-backlog-files` using Python scripts.

**Architecture:** Four Python scripts under `.claude/features/rabbit-file/scripts/` — `branch_ops.py` owns all git operations against the dedicated branch via git worktree; `file-item.py`, `item-status.py`, and `list-items.py` delegate to it. A unified SKILL.md replaces both old skills and is published via build contract.

**Tech Stack:** Python 3, subprocess (git), json, argparse. No third-party dependencies.

---

## Task 0: Archive legacy data and gitignore tmp

**Files:**
- Move: `.claude/bugs/` → `.claude/archive/bugs/`
- Move: `.claude/backlogs/` → `.claude/archive/backlogs/`
- Modify: `.gitignore`

- [ ] **Step 1: Activate session scope override**

```bash
touch .rabbit-scope-active
```

- [ ] **Step 2: Move legacy directories**

```bash
mkdir -p .claude/archive
git mv .claude/bugs .claude/archive/bugs
git mv .claude/backlogs .claude/archive/backlogs
```

- [ ] **Step 3: Add .claude/tmp/ to .gitignore**

Open `.gitignore` and append:
```
.claude/tmp/
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "archive: move legacy bugs+backlogs to .claude/archive/, gitignore .claude/tmp/"
```

- [ ] **Step 5: Remove scope override**

```bash
rm .rabbit-scope-active
```

---

## Task 1: Scaffold the rabbit-file feature

**Files:**
- Create: `.claude/features/rabbit-file/feature.json`
- Create: `.claude/features/rabbit-file/docs/spec/spec.md`

This is the only task that writes to the feature directory without `rabbit-feature-touch`, because the feature doesn't exist yet for it to act on.

- [ ] **Step 1: Activate session scope override**

```bash
touch .rabbit-scope-active
```

- [ ] **Step 2: Create feature directory structure**

```bash
mkdir -p .claude/features/rabbit-file/scripts
mkdir -p .claude/features/rabbit-file/skills/rabbit-file
mkdir -p .claude/features/rabbit-file/docs/spec
mkdir -p .claude/features/rabbit-file/test
```

- [ ] **Step 3: Write feature.json**

Create `.claude/features/rabbit-file/feature.json`:
```json
{
  "name": "rabbit-file",
  "version": "0.1.0",
  "owner": "rabbit-workflow team",
  "tdd_state": "spec-only",
  "summary": "Unified bug and backlog filing, tracking, and lifecycle. Stores items on origin/bug-backlog-files branch via Python scripts. Replaces rabbit-bug and rabbit-backlog.",
  "surface": {
    "hooks": [],
    "commands": [],
    "agents": [],
    "skills": [],
    "scripts": [
      "scripts/branch_ops.py",
      "scripts/file-item.py",
      "scripts/item-status.py",
      "scripts/list-items.py"
    ]
  },
  "deprecation_criterion": "when a unified tracking system replaces file-based bug and backlog management",
  "updated": "2026-05-14"
}
```

- [ ] **Step 4: Write initial spec**

Create `.claude/features/rabbit-file/docs/spec/spec.md`:
```markdown
# rabbit-file

Structured source of truth is feature.json.

## Purpose

Unified bug and backlog filing and lifecycle for all rabbit features.
Replaces rabbit-bug and rabbit-backlog. All items stored on
origin/bug-backlog-files branch, never on main.

## Scripts

- branch_ops.py: All git operations against origin/bug-backlog-files.
  Uses git worktree at .claude/tmp/bug-backlog-files (gitignored).
  Exposes: allocate_id(feature, type), commit_item(feature, type, id, item_dict),
  fetch_item(feature, type, id), read_branch(feature, type, status).
  Auto-initializes orphan branch and counter.json on first use.

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
```

- [ ] **Step 5: Write test/run.sh stub**

Create `.claude/features/rabbit-file/test/run.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
total_fail=0
run_suite() {
    local script="$1"
    echo "=== $script ==="
    if bash "$SCRIPT_DIR/$script"; then echo ""; else total_fail=$((total_fail + 1)); echo ""; fi
}
echo "rabbit-file test runner"
echo ""
run_suite test-scripts-exist.sh
if [ "$total_fail" -eq 0 ]; then echo "ALL SUITES PASSED"; exit 0
else echo "FAILED: $total_fail suite(s) had failures"; exit 1; fi
```

- [ ] **Step 6: Write initial existence test**

Create `.claude/features/rabbit-file/test/test-scripts-exist.sh`:
```bash
#!/usr/bin/env bash
set -uo pipefail
FEATURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$FEATURE_DIR/scripts"
pass=0; fail=0
assert_pass() { echo "PASS: $1"; pass=$((pass+1)); }
assert_fail() { echo "FAIL: $1 — $2"; fail=$((fail+1)); }

for s in branch_ops.py file-item.py item-status.py list-items.py; do
    if [ -f "$SCRIPTS/$s" ]; then assert_pass "$s exists"
    else assert_fail "$s exists" "missing at $SCRIPTS/$s"; fi
done

echo ""; echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
```

- [ ] **Step 7: Commit scaffold**

```bash
git add .claude/features/rabbit-file/
git commit -m "scaffold: rabbit-file feature — feature.json, spec, test stub"
```

- [ ] **Step 8: Remove scope override**

```bash
rm .rabbit-scope-active
```

---

## Task 2: Implement branch_ops.py

Invoke `/rabbit-feature-touch` to drive TDD for this component. The spec section "Scripts — branch_ops.py" is the input. branch_ops.py is the core — all other scripts depend on it.

**Files:**
- Create: `.claude/features/rabbit-file/scripts/branch_ops.py`
- Create: `.claude/features/rabbit-file/test/test-branch-ops.sh`

- [ ] **Step 1: Update spec with branch_ops behavior detail**

Open `.claude/features/rabbit-file/docs/spec/spec.md` and replace the branch_ops.py description with:

```
- branch_ops.py: Module (importable and CLI). All functions use a context
  manager _worktree(repo_root) that runs:
    git worktree add .claude/tmp/bug-backlog-files origin/bug-backlog-files
  on enter, and:
    git worktree remove --force .claude/tmp/bug-backlog-files
  on exit (always, even on exception).

  If origin/bug-backlog-files does not exist, _worktree creates it as an
  orphan branch with an empty root commit before adding the worktree.

  counter_path(wt, feature, type_) -> Path
    Returns wt/rabbit/features/<feature>/<type_>s/counter.json.
    Creates parent dirs if missing.

  read_counter(wt, feature, type_) -> int
    Reads counter.json {"next": N}. Returns 1 if file missing (first item).

  write_counter(wt, feature, type_, n)
    Writes {"next": n} to counter.json.

  allocate_id(feature, type_) -> (id_str, None)
    Opens worktree, reads counter N, writes counter N+1, commits
    "counter: reserve <FEATURE-TYPE-N>" and pushes. Returns id_str
    e.g. "RABBIT-CAGE-BUG-17".

  commit_item(feature, type_, id_str, item: dict) -> sha
    Opens worktree, writes item.json under
    rabbit/features/<feature>/<type_>s/<id_str>/item.json,
    commits "item: <id_str>" and pushes. Gets commit SHA.
    Backfills {"commit_sha": sha} into item.json, commits
    "sha: backfill <id_str>" and pushes. Returns sha.

  fetch_item(feature, type_, id_str) -> dict | None
    Opens worktree, reads item.json. Returns dict or None if not found.

  read_branch(feature=None, type_=None, status=None) -> list[dict]
    Opens worktree, walks all item.json files under rabbit/features/.
    Filters by feature (if given), type (if given), status (if given).
    Returns list of item dicts.
```

- [ ] **Step 2: Invoke rabbit-feature-touch**

```
/rabbit-feature-touch
```

When prompted, specify: implement branch_ops.py per spec, write tests in
`test/test-branch-ops.sh` covering: worktree setup/teardown, counter
init when missing, allocate_id increments counter and returns correct ID,
commit_item writes item.json and backfills SHA, fetch_item returns None
for missing item, read_branch filters by feature/type/status.

- [ ] **Step 3: Verify test-green**

```bash
bash .claude/features/rabbit-file/test/run.sh
```
Expected: `ALL SUITES PASSED`

---

## Task 3: Implement file-item.py

- [ ] **Step 1: Update spec — add file-item.py CLI detail**

Append to the `file-item.py` entry in spec.md:
```
  CLI: python3 file-item.py --type bug|backlog --feature F --title T
       --priority low|medium|high|critical --description D [--filed-by USER]
  Exit 1 on missing required args or invalid priority.
  Calls branch_ops.allocate_id(feature, type_) -> id_str.
  Builds item dict: {name: id_str, type: type_, title, status: "open",
    priority, description, related_feature: feature,
    filed: utcnow().isoformat()+"Z", filed_by: filed_by or git user,
    closed: null, history: [{ts, actor: filed_by, action: "opened",
    note: "initial filing"}]}.
  Calls branch_ops.commit_item(feature, type_, id_str, item) -> sha.
  Prints to stdout: "Filed: <id_str>  sha: <sha>"
```

- [ ] **Step 2: Add test suite to test/run.sh**

In `test/run.sh` add: `run_suite test-file-item.sh`

- [ ] **Step 3: Invoke rabbit-feature-touch**

```
/rabbit-feature-touch
```

When prompted: implement file-item.py per spec. Tests in
`test/test-file-item.sh` must cover: missing --title exits 1, invalid
priority exits 1, valid call produces "Filed: X-BUG-1 sha: ..." on
stdout (use a temp isolated git repo for the branch), item.json on
the branch has correct fields (name, type, status=open, priority).

- [ ] **Step 4: Verify test-green**

```bash
bash .claude/features/rabbit-file/test/run.sh
```
Expected: `ALL SUITES PASSED`

---

## Task 4: Implement item-status.py

- [ ] **Step 1: Update spec — add item-status.py CLI detail**

Append to `item-status.py` entry in spec.md:
```
  CLI subcommands:
    get --feature F --type bug|backlog --id ID
      Prints: STATUS
    set --feature F --type bug|backlog --id ID
        --status open|close --reason R [--fix-commits SHA]
      Requires --reason (non-empty), exit 1 if missing.
      Fetches item via branch_ops.fetch_item; exit 1 if not found.
      Updates item["status"] and item["closed"] (set to now if close,
      null if open). Appends history entry {ts, actor: git user,
      action: "opened"|"closed", note: reason,
      fix_commits: SHA (if provided)}.
      Calls branch_ops.commit_item to write back.
      Prints: "Status set: <id> -> <status>"
```

- [ ] **Step 2: Add test suite to test/run.sh**

In `test/run.sh` add: `run_suite test-item-status.sh`

- [ ] **Step 3: Invoke rabbit-feature-touch**

```
/rabbit-feature-touch
```

When prompted: implement item-status.py per spec. Tests in
`test/test-item-status.sh` must cover: get returns current status,
set without --reason exits 1, set open→close sets closed timestamp
and appends history, set close→open clears closed field,
set on nonexistent item exits 1.

- [ ] **Step 4: Verify test-green**

```bash
bash .claude/features/rabbit-file/test/run.sh
```
Expected: `ALL SUITES PASSED`

---

## Task 5: Implement list-items.py

- [ ] **Step 1: Update spec — add list-items.py CLI detail**

Append to `list-items.py` entry in spec.md:
```
  CLI: python3 list-items.py [--type bug|backlog|all]
       [--feature F] [--status open|close]
  Defaults: --type all, no feature filter, no status filter.
  If origin/bug-backlog-files does not exist: print
    "No items filed yet. Use /rabbit-file file bug or /rabbit-file file backlog."
  and exit 0.
  Calls branch_ops.read_branch(feature, type_, status).
  For each item prints one line:
    NAME  [TYPE]  [STATUS]  [PRIORITY]  TITLE
  If no items match filters: print "No items found."
```

- [ ] **Step 2: Add test suite to test/run.sh**

In `test/run.sh` add: `run_suite test-list-items.sh`

- [ ] **Step 3: Invoke rabbit-feature-touch**

```
/rabbit-feature-touch
```

When prompted: implement list-items.py per spec. Tests in
`test/test-list-items.sh` must cover: missing branch prints guidance
and exits 0, --type bug returns only bugs, --type all returns both,
--status open filters correctly, --feature filters by feature name,
output format matches `NAME  [TYPE]  [STATUS]  [PRIORITY]  TITLE`.

- [ ] **Step 4: Verify test-green**

```bash
bash .claude/features/rabbit-file/test/run.sh
```
Expected: `ALL SUITES PASSED`

---

## Task 6: Write SKILL.md

- [ ] **Step 1: Copy validated draft into feature**

```bash
touch .rabbit-scope-active
cp /tmp/rabbit-file-skill-draft/SKILL.md \
   .claude/features/rabbit-file/skills/rabbit-file/SKILL.md
rm .rabbit-scope-active
```

- [ ] **Step 2: Invoke rabbit-feature-touch to add SKILL.md invariant and test**

```
/rabbit-feature-touch
```

When prompted: add invariant to spec: "SKILL.md at
skills/rabbit-file/SKILL.md MUST exist and contain all five sections:
Overview, File Protocol, Work Protocol, List Protocol, branch_ops.py
Lifecycle." Add `run_suite test-skill.sh` to test/run.sh. Write
`test/test-skill.sh` that asserts SKILL.md exists and contains those
section headings.

- [ ] **Step 3: Verify test-green**

```bash
bash .claude/features/rabbit-file/test/run.sh
```
Expected: `ALL SUITES PASSED`

---

## Task 7: Update build contract

**Files:**
- Modify: `.claude/features/contract/build-contract.json`

- [ ] **Step 1: Invoke rabbit-feature-touch on the contract feature**

```
/rabbit-feature-touch  (target: contract feature)
```

When prompted: add a new target to build-contract.json:
```json
{
  "name": "skills/rabbit-file/SKILL.md",
  "type": "copy-file",
  "source": ".claude/features/rabbit-file/skills/rabbit-file/SKILL.md",
  "destination": ".claude/skills/rabbit-file/SKILL.md",
  "check_on_stop": true
}
```
And remove the targets for `skills/rabbit-bug/SKILL.md` and
`skills/rabbit-backlog/SKILL.md`.

- [ ] **Step 2: Run build to publish SKILL.md**

```bash
bash .claude/features/contract/scripts/build.sh
```
Expected output includes: `[built] skills/rabbit-file/SKILL.md`

- [ ] **Step 3: Verify .claude/skills/rabbit-file/SKILL.md exists**

```bash
test -f .claude/skills/rabbit-file/SKILL.md && echo "OK"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ .claude/features/contract/build-contract.json
git commit -m "contract: publish rabbit-file skill, retire rabbit-bug and rabbit-backlog"
```

---

## Task 8: Remove retired skill published copies

- [ ] **Step 1: Activate scope override**

```bash
touch .rabbit-scope-active
```

- [ ] **Step 2: Remove old published skill directories**

```bash
rm -rf .claude/skills/rabbit-bug
rm -rf .claude/skills/rabbit-backlog
```

- [ ] **Step 3: Commit**

```bash
git add -A .claude/skills/
git commit -m "retire: remove rabbit-bug and rabbit-backlog published skills"
```

- [ ] **Step 4: Remove scope override**

```bash
rm .rabbit-scope-active
```

---

## Task 9: Final verification

- [ ] **Step 1: Run full test suite**

```bash
bash .claude/features/rabbit-file/test/run.sh
```
Expected: `ALL SUITES PASSED`

- [ ] **Step 2: Verify skill is in .claude/skills/**

```bash
ls .claude/skills/rabbit-file/SKILL.md
```
Expected: file present

- [ ] **Step 3: Verify old skills absent**

```bash
ls .claude/skills/rabbit-bug 2>/dev/null && echo "FAIL: still present" || echo "OK: removed"
ls .claude/skills/rabbit-backlog 2>/dev/null && echo "FAIL: still present" || echo "OK: removed"
```
Expected: both print `OK: removed`

- [ ] **Step 4: Verify archive in place**

```bash
ls .claude/archive/bugs/ && ls .claude/archive/backlogs/
```
Expected: legacy directories present under archive

- [ ] **Step 5: Create PR**

```bash
gh pr create --title "feat: rabbit-file unified bug+backlog skill" \
  --body "$(cat <<'EOF'
## Summary
- Unified rabbit-bug and rabbit-backlog into single /rabbit-file skill
- Items stored on dedicated origin/bug-backlog-files branch via Python scripts
- Simplified status lifecycle: open ↔ close (bidirectional)
- Legacy data archived to .claude/archive/

## Test plan
- [ ] bash .claude/features/rabbit-file/test/run.sh → ALL SUITES PASSED
- [ ] .claude/skills/rabbit-file/SKILL.md exists and published by build
- [ ] .claude/skills/rabbit-bug and rabbit-backlog removed
- [ ] .claude/archive/bugs and backlogs present
EOF
)"
```
