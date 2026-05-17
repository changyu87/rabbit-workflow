---
name: rabbit-feature-touch
description: Use when any write, edit, delete, or add operation targets a feature directory, or when a new feature is being created. Not for read-only queries, and NOT for metadata-only writes (bug filing, backlog filing). Ensures the formal TDD state machine is advanced via tdd-step.py on every feature touch.
version: 3.0.0
owner: tdd-subagent
deprecation_criterion: when dispatch-feature-edit.py natively enforces tdd-step.py transitions
---

## Overview

The main session's role is **orchestration only**: resolve scope, create branch,
dispatch TDD subagents, verify HANDOFFs. It does NOT read feature code.

**Two modes:**
- **Normal mode** — invoked directly for a feature work request
- **B/B mode** — invoked by the bug or backlog skill, which passes a bug/item dir

## Unified Seven-Step Sequence

All modes follow these seven steps. Mode determines branch name and step 7 behaviour.

### Step 1 — Scope Resolution

**Normal mode:** Invoke `rabbit-feature-scope` via the Skill tool:
```
Skill("rabbit-feature-scope", args: "<request>")
# Parse JSON response: {"features": [...], "rationale": "..."}
```

**B/B mode:** Skip — feature name comes from `related_feature` in the bug/item JSON:
```bash
FEATURE=$(jq -r '.related_feature' "<bug-or-item-dir>/bug.json")
```

### Step 2 — Create Branch

Create before any dispatch. Never write to main.

| Mode | Branch pattern |
|---|---|
| Normal, single feature | `feat/<feature-name>-<keywords>` |
| Normal, multi-feature | `feat/<primary-feature>-multi-<keywords>` (primary = first feature in scope response) |
| Bug fix (B/B) | `fix/<bug-id>-<keywords>` |
| Backlog task (B/B) | `task/<backlog-id>-<keywords>` |

`<keywords>` = 2–4 words from the request, hyphenated, lowercase.

```bash
git checkout -b <branch-name>
```

### Step 3 — Spec Authoring

Invoke rabbit-spec inline:
```
Skill("rabbit-spec", args: "<feature-name> <request-or-item-description>")
```
In B/B mode, pass the bug/backlog item description as the request.

rabbit-spec reads the current spec, judges open vs. specific, invokes superpowers,
updates the feature spec, and writes `.rabbit/impl-suggestion-<feature-name>.json`.

### Step 4 — Human Approval

A full TDD cycle is about to run — tests will be written, code implemented, a PR
created. Catching a design mismatch now costs one conversation turn; catching it
after costs a full cycle. This gate lives here, in the main session, because
subagents run to completion and cannot pause for user input mid-execution.

For each feature, read `.rabbit/impl-suggestion-<feature-name>.json` and surface
to the user:
- **Request summary** — what was asked
- **Spec changes** — what changed in the spec and why
- **Affected files** — what will be written
- **Implementation approach** — how the subagent will tackle it

For multiple features, present all summaries together and collect one approval
decision before dispatching any subagent.

Wait for explicit user approval ("looks good", "go ahead", or equivalent). If the
user requests changes, invoke rabbit-spec again for the affected features, then
return to this step.

**Bypass:** when the user has indicated they want fully autonomous execution for
this session, skip the wait and pass `--no-human-approval` to the Step 5 dispatch
command. Do not silently bypass — only bypass when the user has explicitly asked
for it.

### Step 5 — Dispatch TDD Subagents

One subagent per feature. Dispatch all in parallel if multiple features.

```bash
PROMPT=$(python3 .claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py \
  --scope <feature-name> \
  --spec .claude/features/<feature-name>/docs/spec/spec.md \
  --impl-suggestion .rabbit/impl-suggestion-<feature-name>.json \
  [--linked-item <bug-or-item-dir> --item-type <bug|backlog>] \
  [--no-human-approval])
Agent(model: opus, prompt: PROMPT)
```

Each subagent runs its named steps (SPEC-READ → UNLOCK), writes
`.rabbit/tdd-report-<feature-name>.json`, and emits HANDOFF.

### Step 6 — Collect and Verify HANDOFFs

Verify each HANDOFF:
- `tdd_state: test-green` for every feature
- `test_result: pass` for every feature
- `spec_compliance: pass` (investigate if fail before proceeding)

If any feature fails: surface failure to user. Do NOT proceed to step 7.

Read `.rabbit/tdd-report-<feature-name>.json` for full details.

### Step 7 — PR / Hand Off

**Normal mode:**
```bash
gh pr create --title "<summary>" --body "<tdd report highlights>"
```
Summarize the TDD report to the user.

**B/B mode:** Commit code to branch. Hand off to calling skill:
```
{
  "mode": "bug|backlog",
  "linked_item": "<path>",
  "feature": "<name>",
  "branch": "<branch-name>",
  "tdd_report_path": "<repo-root>/.rabbit/tdd-report-<feature-name>.json",
  "status": "success|failed"
}
```

If `status: failed`, calling skill surfaces the failure before any item close.
PR creation is the calling skill's responsibility in B/B mode.


## Red Flags — STOP

- Reading feature code directly in the main session → STOP. Subagent's job.
- Skipping scope resolution in normal mode → STOP.
- Dispatching features sequentially when multiple → STOP. Use parallel.
- HANDOFF shows `tdd_state ≠ test-green` → STOP and investigate.

## Override Path

When user explicitly approves a lightweight edit (typo, comment-only), present
a confirm token with `one-time` or `session` scope. After approval, write
`.rabbit-scope-override`, make the edit directly. Does NOT reset `tdd_state`.
