# RWF Features & Repository Hierarchy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the prompt counter, add a `/rwf-set-threshold` slash command, and migrate the repository to a `.claude/`-only workflow footprint.

**Architecture:** Three sequential tasks: (1) rename `.rwf-counter` → `.rwf-prompt-counter` everywhere, (2) add a Python3-backed slash command writing to `.claude/settings.local.json` and bump the default threshold from 10 to 20, (3) move governance and history files into `.claude/` (philosophy, work-guide, docs/) and into `archive/` (bootstrap specs/plans), leaving the repo root with only `CLAUDE.md`, `.claude/`, `archive/`, `.gitignore`. The tasks must run in order because the hierarchy migration moves files that the earlier tasks edit.

**Tech Stack:** bash, Python3 (inline), git, Claude Code slash command format

---

## Task 1: Rename `.rwf-counter` → `.rwf-prompt-counter`

**Files:**
- Modify `/home/cyxu/rabbit-workflow/.claude/settings.json`
- Modify `/home/cyxu/rabbit-workflow/.claude/hooks/rwf-refresh.sh`
- Modify `/home/cyxu/rabbit-workflow/.claude/commands/rwf-refresh.md`
- Modify `/home/cyxu/rabbit-workflow/.gitignore`
- Delete `/home/cyxu/rabbit-workflow/.rwf-counter` (if present at runtime)

### Steps

- [ ] **Step 1.1:** Edit `/home/cyxu/rabbit-workflow/.claude/settings.json` — update the `SessionStart` hook command.

  Before:
  ```json
            "command": "echo 0 > .rwf-counter"
  ```
  After:
  ```json
            "command": "echo 0 > .rwf-prompt-counter"
  ```

- [ ] **Step 1.2:** Edit `/home/cyxu/rabbit-workflow/.claude/hooks/rwf-refresh.sh` — update the `COUNTER_FILE` variable on line 15.

  Before:
  ```bash
  COUNTER_FILE="$REPO_ROOT/.rwf-counter"
  ```
  After:
  ```bash
  COUNTER_FILE="$REPO_ROOT/.rwf-prompt-counter"
  ```

- [ ] **Step 1.3:** Edit `/home/cyxu/rabbit-workflow/.claude/commands/rwf-refresh.md` — update the reset line.

  Before:
  ```
  !`echo 0 > .rwf-counter`
  ```
  After:
  ```
  !`echo 0 > .rwf-prompt-counter`
  ```

- [ ] **Step 1.4:** Edit `/home/cyxu/rabbit-workflow/.gitignore` — change the runtime entry.

  Before:
  ```
  # Rabbit Workflow runtime state
  .rwf-counter
  ```
  After:
  ```
  # Rabbit Workflow runtime state
  .rwf-prompt-counter
  ```

- [ ] **Step 1.5:** Remove the stale runtime counter file if present.

  Command:
  ```bash
  rm -f /home/cyxu/rabbit-workflow/.rwf-counter
  ```
  Expected output: (none — `rm -f` is silent)

- [ ] **Step 1.6 (verify):** Confirm no stale references to `.rwf-counter` remain anywhere in the tracked tree.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && git grep -n '\.rwf-counter' || echo "OK: no matches"
  ```
  Expected output:
  ```
  OK: no matches
  ```

- [ ] **Step 1.7 (verify):** Smoke-test the hook with a low threshold and confirm it writes to the new counter file.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && rm -f .rwf-prompt-counter && \
    RWF_REFRESH_EVERY=2 .claude/hooks/rwf-refresh.sh && \
    echo "--- counter after run 1: $(cat .rwf-prompt-counter)" && \
    RWF_REFRESH_EVERY=2 .claude/hooks/rwf-refresh.sh > /tmp/rwf-out.json && \
    echo "--- counter after run 2: $(cat .rwf-prompt-counter)" && \
    echo "--- json keys:" && python3 -c "import json,sys; d=json.load(open('/tmp/rwf-out.json')); print(sorted(d.keys()))"
  ```
  Expected output (key parts):
  ```
  --- counter after run 1: 1
  --- counter after run 2: 0
  --- json keys:
  ['additionalContext', 'systemMessage']
  ```

- [ ] **Step 1.8 (cleanup):** Remove the runtime counter (it is gitignored but should not be staged accidentally) and the temp file.

  Command:
  ```bash
  rm -f /home/cyxu/rabbit-workflow/.rwf-prompt-counter /tmp/rwf-out.json
  ```
  Expected output: (none)

- [ ] **Step 1.9 (commit):** Stage and commit the rename.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    git add .claude/settings.json .claude/hooks/rwf-refresh.sh .claude/commands/rwf-refresh.md .gitignore && \
    git commit -m "$(cat <<'EOF'
  Rename .rwf-counter to .rwf-prompt-counter

  The file counts UserPromptSubmit events; the new name says so.
  Updated settings.json SessionStart hook, rwf-refresh.sh COUNTER_FILE,
  the /rwf-refresh slash command, and the gitignore entry.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  EOF
  )"
  ```
  Expected output: a single commit on `main` touching the four files above.

---

## Task 2: Add `/rwf-set-threshold` and bump default threshold to 20

**Files:**
- Modify `/home/cyxu/rabbit-workflow/.claude/settings.json`
- Modify `/home/cyxu/rabbit-workflow/.gitignore`
- Create `/home/cyxu/rabbit-workflow/.claude/commands/rwf-set-threshold.md`

### Steps

- [ ] **Step 2.1:** Edit `/home/cyxu/rabbit-workflow/.claude/settings.json` — bump the default threshold.

  Before:
  ```json
      "RWF_REFRESH_EVERY": "10"
  ```
  After:
  ```json
      "RWF_REFRESH_EVERY": "20"
  ```

- [ ] **Step 2.2:** Edit `/home/cyxu/rabbit-workflow/.gitignore` — add `.claude/settings.local.json` so user-local overrides stay local.

  Before:
  ```
  # Rabbit Workflow runtime state
  .rwf-prompt-counter
  ```
  After:
  ```
  # Rabbit Workflow runtime state
  .rwf-prompt-counter
  .claude/settings.local.json
  ```

- [ ] **Step 2.3:** Create `/home/cyxu/rabbit-workflow/.claude/commands/rwf-set-threshold.md` with the EXACT content below (no leading/trailing whitespace, single trailing newline):

  ````markdown
  ---
  description: Set the auto-refresh threshold (prompts between policy re-injections). Writes to .claude/settings.local.json. Takes effect next session.
  allowed-tools: Bash
  ---

  Setting auto-refresh threshold to $ARGUMENTS prompts.

  !`python3 -c "
  import json, pathlib, sys
  val = '$ARGUMENTS'.strip()
  if not val.isdigit() or int(val) < 1:
      print('Error: argument must be a positive integer (e.g. /rwf-set-threshold 15)', file=sys.stderr)
      sys.exit(1)
  p = pathlib.Path('.claude/settings.local.json')
  cfg = json.loads(p.read_text()) if p.exists() else {}
  cfg.setdefault('env', {})['RWF_REFRESH_EVERY'] = val
  p.write_text(json.dumps(cfg, indent=2) + '\n')
  print('Written to .claude/settings.local.json')
  "`

  Threshold set to $ARGUMENTS prompts. Takes effect on next session start.
  ````

  Note: the file content begins with `---` (the frontmatter delimiter) and ends with the line `Threshold set to $ARGUMENTS prompts. Takes effect on next session start.` followed by a single newline. Do NOT include the four-backtick fence shown above — that fence is only for displaying the file content in this plan.

- [ ] **Step 2.4 (verify — valid input):** Test the inline Python3 block by simulating `$ARGUMENTS = "15"`. Run from a temporary working directory so we don't pollute the repo.

  Command:
  ```bash
  set -e
  TMP=$(mktemp -d)
  cd "$TMP" && mkdir -p .claude
  python3 -c "
  import json, pathlib, sys
  val = '15'.strip()
  if not val.isdigit() or int(val) < 1:
      print('Error: argument must be a positive integer (e.g. /rwf-set-threshold 15)', file=sys.stderr)
      sys.exit(1)
  p = pathlib.Path('.claude/settings.local.json')
  cfg = json.loads(p.read_text()) if p.exists() else {}
  cfg.setdefault('env', {})['RWF_REFRESH_EVERY'] = val
  p.write_text(json.dumps(cfg, indent=2) + '\n')
  print('Written to .claude/settings.local.json')
  "
  echo "--- file contents:"
  cat .claude/settings.local.json
  cd / && rm -rf "$TMP"
  ```
  Expected output:
  ```
  Written to .claude/settings.local.json
  --- file contents:
  {
    "env": {
      "RWF_REFRESH_EVERY": "15"
    }
  }
  ```

- [ ] **Step 2.5 (verify — invalid input):** Confirm the script rejects non-positive-integer input with a non-zero exit.

  Command:
  ```bash
  TMP=$(mktemp -d)
  cd "$TMP" && mkdir -p .claude
  set +e
  python3 -c "
  import json, pathlib, sys
  val = 'abc'.strip()
  if not val.isdigit() or int(val) < 1:
      print('Error: argument must be a positive integer (e.g. /rwf-set-threshold 15)', file=sys.stderr)
      sys.exit(1)
  p = pathlib.Path('.claude/settings.local.json')
  cfg = json.loads(p.read_text()) if p.exists() else {}
  cfg.setdefault('env', {})['RWF_REFRESH_EVERY'] = val
  p.write_text(json.dumps(cfg, indent=2) + '\n')
  print('Written to .claude/settings.local.json')
  "
  ec=$?
  set -e
  echo "--- exit code: $ec"
  cd / && rm -rf "$TMP"
  ```
  Expected output (stderr is interleaved):
  ```
  Error: argument must be a positive integer (e.g. /rwf-set-threshold 15)
  --- exit code: 1
  ```

- [ ] **Step 2.6 (verify — gitignore works):** Drop a test `.claude/settings.local.json` into the repo and confirm `git status` ignores it; then remove it.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    echo '{"env":{"RWF_REFRESH_EVERY":"7"}}' > .claude/settings.local.json && \
    git status --porcelain .claude/settings.local.json && \
    echo "--- ignored check:" && \
    git check-ignore -v .claude/settings.local.json && \
    rm -f .claude/settings.local.json
  ```
  Expected output (the `git status` line should be empty; `check-ignore` confirms the rule):
  ```
  --- ignored check:
  .gitignore:9:.claude/settings.local.json	.claude/settings.local.json
  ```
  (Line number `9` may differ depending on whether the gitignore had trailing blank lines; what matters is that `.gitignore` matches `.claude/settings.local.json`.)

- [ ] **Step 2.7 (cleanup):** Make sure no test artifact is staged.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && ls -la .claude/settings.local.json 2>&1 | grep -v 'No such' || echo "OK: gone"
  ```
  Expected output:
  ```
  OK: gone
  ```

- [ ] **Step 2.8 (commit):** Stage and commit.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    git add .claude/settings.json .gitignore .claude/commands/rwf-set-threshold.md && \
    git commit -m "$(cat <<'EOF'
  Add /rwf-set-threshold and bump default refresh threshold to 20

  New slash command writes RWF_REFRESH_EVERY into .claude/settings.local.json
  (gitignored, user-local), so each user can pick their own cadence without
  editing the shared settings.json. Default threshold raised from 10 to 20
  prompts.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  EOF
  )"
  ```
  Expected output: one commit touching `settings.json`, `.gitignore`, and the new `rwf-set-threshold.md`.

---

## Task 3: Repository hierarchy migration

**Files:**
- Move `/home/cyxu/rabbit-workflow/philosophy.md` → `/home/cyxu/rabbit-workflow/.claude/philosophy.md`
- Move `/home/cyxu/rabbit-workflow/work-guide.md` → `/home/cyxu/rabbit-workflow/.claude/work-guide.md`
- Modify `/home/cyxu/rabbit-workflow/CLAUDE.md`
- Move `/home/cyxu/rabbit-workflow/docs/superpowers/specs/2026-05-08-rabbit-workflow-bootstrap-design.md` → `/home/cyxu/rabbit-workflow/archive/`
- Move `/home/cyxu/rabbit-workflow/docs/superpowers/specs/2026-05-08-philosophy-split-design.md` → `/home/cyxu/rabbit-workflow/archive/`
- Move `/home/cyxu/rabbit-workflow/docs/superpowers/plans/2026-05-08-rabbit-workflow-bootstrap.md` → `/home/cyxu/rabbit-workflow/archive/`
- Move `/home/cyxu/rabbit-workflow/docs/superpowers/plans/2026-05-08-philosophy-split.md` → `/home/cyxu/rabbit-workflow/archive/`
- Create `/home/cyxu/rabbit-workflow/.claude/docs/plans/.gitkeep`
- Create `/home/cyxu/rabbit-workflow/.claude/docs/meta/.gitkeep`
- Create `/home/cyxu/rabbit-workflow/.claude/docs/bugs/.gitkeep`
- Delete `/home/cyxu/rabbit-workflow/docs/` (the old empty tree)

### Steps

- [ ] **Step 3.1:** `git mv` the two governance files into `.claude/`.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    git mv philosophy.md .claude/philosophy.md && \
    git mv work-guide.md .claude/work-guide.md
  ```
  Expected output: (none on success)

- [ ] **Step 3.2:** Update `/home/cyxu/rabbit-workflow/CLAUDE.md` to point at the new locations.

  Before (full file content):
  ```markdown
  # Rabbit Workflow

  This repository is bounded by two source-of-truth files:

  @./philosophy.md
  @./work-guide.md

  To add more, append `@./<filename>.md` below.
  ```
  After (full file content):
  ```markdown
  # Rabbit Workflow

  This repository is bounded by two source-of-truth files:

  @./.claude/philosophy.md
  @./.claude/work-guide.md

  To add more, append `@./<filename>.md` below.
  ```

- [ ] **Step 3.3:** `git mv` the four bootstrap docs from `docs/superpowers/` into `archive/`.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    git mv docs/superpowers/specs/2026-05-08-rabbit-workflow-bootstrap-design.md archive/ && \
    git mv docs/superpowers/specs/2026-05-08-philosophy-split-design.md archive/ && \
    git mv docs/superpowers/plans/2026-05-08-rabbit-workflow-bootstrap.md archive/ && \
    git mv docs/superpowers/plans/2026-05-08-philosophy-split.md archive/
  ```
  Expected output: (none on success)

- [ ] **Step 3.4:** Create `.gitkeep` placeholders for the three new doc subdirectories. (`.claude/docs/specs/` already exists and is non-empty.)

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    mkdir -p .claude/docs/plans .claude/docs/meta .claude/docs/bugs && \
    touch .claude/docs/plans/.gitkeep .claude/docs/meta/.gitkeep .claude/docs/bugs/.gitkeep
  ```
  Expected output: (none)

  Note: this plan file itself (`.claude/docs/plans/2026-05-08-rwf-features-and-hierarchy.md`) was already written into `.claude/docs/plans/` before Task 3 began, so the `.gitkeep` is technically redundant for `plans/` once the plan is committed. Create it anyway for symmetry, and leave cleanup as a future concern (not in scope here).

- [ ] **Step 3.5:** Remove the now-empty old `docs/` tree.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    rm -rf docs/
  ```
  Expected output: (none)

- [ ] **Step 3.6 (verify — root contents):** Confirm the repo root contains only the expected entries.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && ls -A1 | sort
  ```
  Expected output (the runtime `.rwf-prompt-counter` may or may not exist; `.work-guide.md.swp` is a stale vim swap from the user's editor and is gitignored — its presence is acceptable):
  ```
  .claude
  .git
  .gitignore
  CLAUDE.md
  archive
  ```
  Acceptable additions (gitignored runtime/editor cruft): `.rwf-prompt-counter`, `.work-guide.md.swp`, `.*.swp`. If anything else appears, stop and investigate.

- [ ] **Step 3.7 (verify — imports resolve):** Confirm both files referenced by `CLAUDE.md` exist at the new path.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    for p in $(grep -oE '^@[^[:space:]]+' CLAUDE.md | sed 's/^@//'); do \
      if [ -f "$p" ]; then echo "OK: $p"; else echo "MISSING: $p"; exit 1; fi; \
    done
  ```
  Expected output:
  ```
  OK: ./.claude/philosophy.md
  OK: ./.claude/work-guide.md
  ```

- [ ] **Step 3.8 (verify — hook still emits valid JSON with refreshed policy):** Run the hook past its threshold and confirm `additionalContext` contains content from both moved governance files.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && rm -f .rwf-prompt-counter && \
    RWF_REFRESH_EVERY=1 .claude/hooks/rwf-refresh.sh > /tmp/rwf-out.json && \
    python3 -c "
  import json
  d = json.load(open('/tmp/rwf-out.json'))
  assert 'additionalContext' in d, 'missing additionalContext'
  assert 'systemMessage' in d, 'missing systemMessage'
  ac = d['additionalContext']
  assert '.claude/philosophy.md' in ac, 'philosophy path missing from payload'
  assert '.claude/work-guide.md' in ac, 'work-guide path missing from payload'
  assert 'Machine First' in ac, 'philosophy content missing'
  assert 'Tool-Choice Tier' in ac, 'work-guide content missing'
  print('OK: hook emits valid JSON with both files inlined')
  " && rm -f .rwf-prompt-counter /tmp/rwf-out.json
  ```
  Expected output:
  ```
  OK: hook emits valid JSON with both files inlined
  ```

- [ ] **Step 3.9 (verify — no stray `docs/`):** Confirm the old top-level `docs/` directory is gone.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    if [ -e docs ]; then echo "FAIL: docs/ still exists"; exit 1; else echo "OK: docs/ removed"; fi
  ```
  Expected output:
  ```
  OK: docs/ removed
  ```

- [ ] **Step 3.10 (verify — git status looks right):** Quick sanity check.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && git status
  ```
  Expected output (essentials):
  - Renames: `philosophy.md → .claude/philosophy.md`, `work-guide.md → .claude/work-guide.md`, four bootstrap docs from `docs/superpowers/{specs,plans}/` to `archive/`.
  - Modified: `CLAUDE.md`.
  - New (untracked) files: `.claude/docs/plans/.gitkeep`, `.claude/docs/meta/.gitkeep`, `.claude/docs/bugs/.gitkeep`, and the plan file `.claude/docs/plans/2026-05-08-rwf-features-and-hierarchy.md` (and the spec `.claude/docs/specs/2026-05-08-rwf-features-and-hierarchy-design.md` if not already committed).

- [ ] **Step 3.11 (commit):** Stage everything (including the new `.gitkeep`s, the moved spec, and this plan) and commit.

  Command:
  ```bash
  cd /home/cyxu/rabbit-workflow && \
    git add -A && \
    git commit -m "$(cat <<'EOF'
  Migrate to .claude/-only workflow footprint

  Move philosophy.md and work-guide.md into .claude/, update CLAUDE.md
  imports to match. Move the four bootstrap specs/plans from
  docs/superpowers/ into archive/ and delete the now-empty docs/ tree.
  Seed .claude/docs/{plans,meta,bugs}/ with .gitkeep so the structure is
  visible to fresh clones.

  Repo root now contains only CLAUDE.md, .claude/, archive/, .gitignore.
  This establishes the install contract: copy .claude/ + CLAUDE.md into a
  user's workspace-home/ and nothing else.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  EOF
  )" && \
    git status
  ```
  Expected output: one commit; final `git status` should report `nothing to commit, working tree clean` (modulo any gitignored runtime files).

---

## Acceptance Criteria (from spec §6)

After all three tasks are committed, verify by inspection:

- [ ] `philosophy.md` and `work-guide.md` are absent from repo root; present at `.claude/philosophy.md` and `.claude/work-guide.md`.
- [ ] `CLAUDE.md` imports resolve correctly: `@./.claude/philosophy.md` and `@./.claude/work-guide.md`.
- [ ] `.rwf-prompt-counter` is gitignored; `.rwf-counter` name is gone from all tracked files (`git grep '\.rwf-counter'` returns nothing).
- [ ] `/rwf-set-threshold 5` would write `{"env": {"RWF_REFRESH_EVERY": "5"}}` to `.claude/settings.local.json` (verified via the standalone Python3 test in Step 2.4).
- [ ] `settings.json` default is `"20"`; `.claude/settings.local.json` is gitignored.
- [ ] `docs/superpowers/` is gone; the four bootstrap specs/plans live in `archive/`.
- [ ] `.claude/docs/{specs,plans,meta,bugs}/` all exist (with `.gitkeep` or initial content).
- [ ] Only `CLAUDE.md`, `archive/`, `.gitignore`, and `.claude/` exist at repo root (plus `.git/` and gitignored runtime/editor files).
- [ ] `git status` is clean after Task 3 commits.
