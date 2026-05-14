---
name: rabbit-backlog
description: Invoke when the user intends to file a backlog item, check backlog item status, transition a backlog item, or manage any backlog lifecycle in this repository. Use this skill whenever the user mentions filing, creating, or adding a backlog item; asking about a backlog item's status; moving a backlog item to in-progress, done, or cancelled; or any other backlog lifecycle operation — even if they phrase it as "log a todo", "track an issue", "mark that backlog as done", or similar casual language.
version: 2.0.0
owner: rabbit-backlog
deprecation_criterion: when a unified tracking system replaces file-based backlog management
---

## Overview

Two distinct protocols: **Filing** and **Working**. Scripts live at
`.claude/features/rabbit-backlog/scripts/`. Items stored under `.claude/backlogs/`.

---

## Filing Protocol

When the user confirms they want to file a backlog item:

1. Invoke `rabbit-feature-scope` to identify the related feature (or ask user if ambiguous).
2. Ask clarifying questions if item description is unclear.
3. Run `file-backlog-item.sh` to create the item and capture its directory path:
   ```bash
   ITEM_DIR=$(bash .claude/features/rabbit-backlog/scripts/file-backlog-item.sh \
     --related-feature <feature-name> \
     --title "..." \
     [--priority <low|medium|high|critical>])
   # ITEM_DIR is e.g. .claude/backlogs/rabbit-cage/RABBIT-CAGE-BACKLOG-5/
   ITEM_ID=$(basename "$ITEM_DIR")
   ```
4. Create branch and commit:
   ```bash
   git checkout -b "filing/${ITEM_ID}"
   git add "$ITEM_DIR"
   git commit -m "filing: ${ITEM_ID} — <title>"
   ```
5. Create **auto-merge PR** to main (metadata only).

---

## Working Protocol

When the user asks to work a backlog item:

1. **Eval subagent** — dispatch a read-only default-model subagent:
   - Reads `item.json` + current feature spec (`docs/spec/spec.md`)
   - Returns verdict: `valid` (still relevant and correctly scoped) or `stale/invalid` with reason

2. **User-decision gate** — after the eval subagent returns its verdict, BEFORE taking any action:
   - Present the user with a brief summary of the verdict and any recommendation.
   - If verdict is `stale/invalid`: summarize why and recommend refusing/cancelling the item.
   - If verdict is `valid`: confirm the item is still relevant and recommend proceeding.
   - Explicitly ask: **"Refuse/cancel this item, or proceed to work it?"**
   - **Do NOT dispatch `rabbit-feature-touch` until the user confirms.**

3. **If user chooses to refuse/cancel (or eval returned stale/invalid and user agrees):**
   ```bash
   git checkout -b "filing/${ITEM_ID}-cancel"
   bash .claude/features/rabbit-backlog/scripts/backlog-item-status.sh set "$ITEM_DIR" cancelled \
     --reason "<why it's no longer relevant>"
   git add "$ITEM_DIR/item.json"
   git commit -m "cancel: ${ITEM_ID} — <reason>"
   ```
   - Create **auto-merge PR** to main.

4. **If user confirms to proceed (and eval returned valid):**
   - Invoke `rabbit-feature-touch` in B/B mode, passing the item dir.
     feature-touch reads `related_feature` from `item.json` and creates the `task/` branch.
   - Receive handoff: `{branch, tdd_report_path, status}`
   - **If `status: failed`:** surface error to user. Stop.
   - **If `status: success`:**
     ```bash
     # TDD_REPORT_PATH = handoff["tdd_report_path"] (where tdd-report.json path is given)
     bash .claude/features/rabbit-backlog/scripts/backlog-item-status.sh set "$ITEM_DIR" implemented \
       --reason "TDD cycle complete" \
       --tdd-report "$TDD_REPORT_PATH" \
       --fix-commits "$(python3 -c "import json; print(json.load(open('$TDD_REPORT_PATH'))['impl_commit'])")"
     git add "$ITEM_DIR/item.json"
     git commit -m "implement: ${ITEM_ID} — done"
     ```
   - Create **review PR** (same `task/` branch — contains implementation + updated `item.json`).

---

## Scripts Reference

| Script | Usage |
|---|---|
| `file-backlog-item.sh` | `file-backlog-item.sh --related-feature F --title T [--priority P]` |
| `backlog-item-status.sh get <dir>` | Print current status |
| `backlog-item-status.sh set <dir> <status> [--reason R] [--tdd-report P] [--fix-commits C]` | Transition |
| `list-backlog.sh [--status S] [--feature F] [--text]` | List items |

## Status Lifecycle

```
open → in-progress | cancelled
in-progress → implemented | cancelled
```

## PR Tiers

| PR type | Branch | Merge |
|---|---|---|
| Filing | `filing/RABBIT-BACKLOG-N` | Auto-merge |
| Cancel | `filing/RABBIT-BACKLOG-N-cancel` | Auto-merge |
| Implement + close | `task/<backlog-id>-<keywords>` | Requires review |
