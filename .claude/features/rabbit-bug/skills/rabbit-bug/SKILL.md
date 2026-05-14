---
name: rabbit-bug
description: Use when Claude detects intent to file a bug, check bug status, list bugs, close/reopen/refuse a bug, or perform any bug lifecycle operation in this repository.
version: 2.0.0
owner: rabbit-bug
deprecation_criterion: when a unified tracking system replaces file-based bug management
---

## Overview

Two distinct protocols: **Filing** and **Working**. Scripts live at
`.claude/features/rabbit-bug/scripts/`. Bugs stored under `.claude/bugs/`.

---

## Filing Protocol

When the user confirms they want to file a bug:

1. Invoke `rabbit-feature-scope` to identify the related feature (or ask user if ambiguous).
2. Ask clarifying questions if bug description is insufficient for reproduction.
3. Run `file-bug.sh` to create the bug record and capture its directory path:
   ```bash
   BUG_DIR=$(bash .claude/features/rabbit-bug/scripts/file-bug.sh \
     --title "..." \
     --severity <low|medium|high|critical> \
     --description "..." \
     --related-feature <feature-name>)
   # BUG_DIR is e.g. .claude/bugs/rabbit-cage/RABBIT-BUG-5/
   BUG_ID=$(basename "$BUG_DIR")  # e.g. RABBIT-BUG-5
   ```
4. Create branch and commit:
   ```bash
   git checkout -b "filing/${BUG_ID}"
   git add "$BUG_DIR"
   git commit -m "filing: ${BUG_ID} — <title>"
   ```
5. Create **auto-merge PR** to main (metadata only, no code change).

---

## Working Protocol

When the user asks to work/fix a bug:

1. **Eval subagent** — dispatch a read-only default-model subagent:
   - Reads `bug.json` + current feature spec (`docs/spec/spec.md`)
   - Returns verdict: `valid` (bug still reproducible per spec) or `stale/invalid` with reason

2. **User-decision gate** — after the eval subagent returns its verdict, brief the user:
   - Summarize the eval findings (what the subagent found, why it reached its verdict).
   - State a clear recommendation: refuse (if stale/invalid) or work the bug (if valid).
   - Ask the user explicitly: "Should I **refuse** this bug or **work** it?" — do NOT dispatch
     `rabbit-feature-touch` or proceed with any status transition until the user confirms.

3. **If user decides: refuse (stale/invalid):**
   ```bash
   git checkout -b "filing/${BUG_ID}-invalidate"
   bash .claude/features/rabbit-bug/scripts/bug-status.sh set "$BUG_DIR" refused \
     --reason "<why it's invalid>"
   git add "$BUG_DIR/bug.json"
   git commit -m "refuse: ${BUG_ID} — <reason>"
   ```
   - Create **auto-merge PR** to main.

4. **If user decides: work (valid):**
   - Invoke `rabbit-feature-touch` in B/B mode, passing the bug dir.
     feature-touch reads `related_feature` from `bug.json` and creates the `fix/` branch.
   - Receive handoff: `{branch, tdd_report_path, status}` where `tdd_report_path` points to `tdd-report.json`
   - **If `status: failed`:** surface error to user. Stop.
   - **If `status: success`:**
     ```bash
     # TDD_REPORT_PATH = handoff["tdd_report_path"]
     bash .claude/features/rabbit-bug/scripts/bug-status.sh set "$BUG_DIR" closed \
       --reason "TDD cycle complete" \
       --tdd-report "$TDD_REPORT_PATH" \
       --fix-commits "$(python3 -c "import json; print(json.load(open('$TDD_REPORT_PATH'))['impl_commit'])")"
     git add "$BUG_DIR/bug.json"
     git commit -m "close: ${BUG_ID} — fix applied and verified"
     ```
   - Create **review PR** (same `fix/` branch — contains code fix + updated `bug.json`).

---

## Scripts Reference

| Script | Usage |
|---|---|
| `file-bug.sh` | `file-bug.sh --title T --severity S --description D [--related-feature F]` |
| `bug-status.sh get <dir>` | Print current status |
| `bug-status.sh set <dir> <status> --reason R [--tdd-report P] [--fix-commits C]` | Transition status |
| `list-bugs.sh [--status S] [--feature F] [--text]` | List bugs |

## Bug Close Requirements (R7)

Closing requires:
- `vet-triage.json` present in bug dir (run `rabbit-triage.sh` first, or use `--skip-vet-reason`)
- `--tdd-report <path>` flag provided to `bug-status.sh set closed`

## Status Lifecycle

```
open → closed | refused
closed → reopened
reopened → closed | refused
refused → reopened
```

## PR Tiers

| PR type | Branch | Merge |
|---|---|---|
| Filing | `filing/RABBIT-BUG-N` | Auto-merge |
| Refuse/invalidate | `filing/RABBIT-BUG-N-invalidate` | Auto-merge |
| Fix + close | `fix/<bug-id>-<keywords>` | Requires review |
