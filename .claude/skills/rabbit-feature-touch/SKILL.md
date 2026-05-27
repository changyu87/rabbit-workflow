---
name: rabbit-feature-touch
description: Use when any write, edit, delete, or add operation targets a feature directory, or when a new feature is being created. Not for read-only queries, and NOT for metadata-only writes (bug filing, backlog filing). Ensures the formal TDD state machine is advanced via tdd-step.py on every feature touch.
version: 3.0.2
owner: rabbit-feature
deprecation_criterion: when feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code workflow primitives
---

## Overview

The main session's role is **orchestration only**: resolve scope, create branch,
dispatch TDD subagents, verify HANDOFFs. It does NOT read feature code.

**Two modes:**
- **Normal mode** — invoked directly for a feature work request
- **B/B mode** — invoked by the bug or backlog skill, which passes a bug/item dir

## Dispatcher Continuity

Once you begin Step 1, you (the dispatcher) **MUST NOT end** your turn until
you have completed **Step 7** (PR / Hand Off) or you have an explicit failure
to report to the user. The seven-step sequence is a single dispatcher
transaction. A subagent returning a HANDOFF is a **phase boundary** inside
your own ongoing turn — it is **not a turn boundary**. Continue to the next
step immediately.

## Unified Seven-Step Sequence

All modes follow these seven steps. Mode determines branch name and step 7 behaviour.

### Step 1 — Scope Resolution

**Normal mode:** Invoke `rabbit-feature-scope` via the Skill tool:
```
Skill("rabbit-feature-scope", args: "<request>")
# Parse JSON response: {"features": [...], "rationale": "..."}
```

**B/B mode:** Skip — feature name comes from `related_feature` in the bug/item JSON.
Use Python 3 (always available) rather than `jq` (not a declared dependency):
```bash
FEATURE=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('related_feature',''))" "<item-dir>/item.json")
```
The rabbit-file schema stores both bug and backlog items as `item.json`
(unified storage).

#### B/B item materialization

The canonical bug/backlog items live on the dedicated `bug-backlog-files`
branch, which is **never checked out** in the dispatcher's working tree.
The canonical `item.json` is therefore not reachable as a plain
working-tree path. Before passing a path to
`dispatch-tdd-subagent.py --linked-item`, the caller MUST materialize the
item into a local working-tree mirror.

- **Local mirror path layout** — mirror the rabbit-file storage layout
  (`rabbit/features/<feature>/<type>s/<id>/`) under a `.rabbit/` prefix:
  `.rabbit/rabbit/features/<feature>/<type>s/<id>/item.json`. The
  `.rabbit/` prefix is gitignored by contract, so the mirror never
  pollutes commits.
- **Fetch `item.json` from `origin/bug-backlog-files`** into the local
  mirror path with `git show`:

```bash
mkdir -p .rabbit/rabbit/features/<feature>/<type>s/<id>
git show origin/bug-backlog-files:rabbit/features/<feature>/<type>s/<id>/item.json \
  > .rabbit/rabbit/features/<feature>/<type>s/<id>/item.json
```

- **Pass to `--linked-item`** — the local mirror **directory** path
  (the directory containing the freshly materialized `item.json`), NOT
  the canonical `rabbit/features/<feature>/<type>s/<id>/` path on the
  dedicated branch:

```
--linked-item .rabbit/rabbit/features/<feature>/<type>s/<id>
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

Invoke rabbit-feature-spec inline:
```
Skill("rabbit-feature-spec", args: "<feature-name> <request-or-item-description>")
```
In B/B mode, pass the bug/backlog item description as the request.

rabbit-feature-spec reads the current spec, judges open vs. specific, invokes superpowers,
updates the feature spec, and writes `.rabbit/impl-suggestion-<feature-name>.json`.

**Commit spec changes BEFORE Step 5.** After rabbit-feature-spec returns, stage and
commit any modifications under `.claude/features/<feature-name>/` (the spec
and any other files rabbit-feature-spec touched). If no changes were made (empty
diff), skip the commit.

```bash
git add .claude/features/<feature-name>/
if ! git diff --cached --quiet -- .claude/features/<feature-name>/docs/spec/spec.md; then
  git commit -m "spec(<feature-name>): update spec for <one-line request summary>"
fi
```

This prevents spec edits from falling through uncommitted and ensures the
TDD subagent reads a clean committed baseline.

### Step 4 — Human Approval

A full TDD cycle is about to run — tests will be written, code implemented, a PR
created. Catching a design mismatch now costs one conversation turn; catching it
after costs a full cycle. This gate lives here, in the main session, because
subagents run to completion and cannot pause for user input mid-execution.

**FIRST: check for `.rabbit-human-approval-bypass` marker at repo root.**

The marker file is the sole authorization mechanism for bypass. In-conversation
acknowledgements ("you have permission to bypass") are NOT sufficient on their
own — the marker is the system of record, managed via
`/rabbit-config human-approval true|false` (owned by rabbit-cage;
`false` writes the marker — bypass ACTIVE — and `true` removes it — gate
ACTIVE, the default).

- **If `.rabbit-human-approval-bypass` exists:**
  - Source the alert text from the centrally-declared `human-approval`
    configurable in `rabbit-cage/feature.json` by invoking
    `contract.lib.runtime.emit_configurable_alert('rabbit-cage',
    'human-approval', repo_root=<repo-root>)`, e.g.:
    ```bash
    python3 -c "import sys; sys.path.insert(0, '.claude/features/contract'); from lib.runtime import emit_configurable_alert; r = emit_configurable_alert('rabbit-cage', 'human-approval', repo_root='.'); print(r)"
    ```
    Surface the returned `print_result` (its `text`, `icon`, and `color`
    fields come from the configurable's `alert-message`, so this prose
    stays in sync with the Stop-hook emission). Do NOT duplicate the
    alert text in this SKILL.md — the configurable's `alert-message` is
    the sole source of truth, and the brand prefix is owned by
    `rabbit_print` (contract Inv 48).
  - Operational guidance for the user: the bypass marker is
    `.rabbit-human-approval-bypass` at the repo root, and it is revoked
    by running `/rabbit-config human-approval true` (which removes the
    marker and re-activates this gate).
  - Proceed to Step 5 immediately. Do NOT surface the impl-suggestion summary.
- **If the marker file does NOT exist (default):**
  - For each feature, read `.rabbit/impl-suggestion-<feature-name>.json` and
    surface to the user:
    - **Request summary** — what was asked
    - **Spec changes** — what changed in the spec and why
    - **Affected files** — what will be written
    - **Implementation approach** — how the subagent will tackle it
  - For multiple features, present all summaries together and collect one
    approval decision before dispatching any subagent.
  - Wait for explicit in-conversation user approval ("looks good", "go ahead",
    or equivalent). If the user requests changes, invoke rabbit-feature-spec again for
    the affected features, then return to this step.
  - Proceed to Step 5.

### Step 5 — Dispatch TDD Subagents

One subagent per feature. Dispatch all in parallel if multiple features.

Shell (assemble the prompt — deterministic):

```bash
PROMPT=$(python3 .claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py \
  --scope <feature-name> \
  --spec .claude/features/<feature-name>/docs/spec/spec.md \
  --impl-suggestion .rabbit/impl-suggestion-<feature-name>.json \
  [--linked-item <bug-or-item-dir> --item-type <bug|backlog>])
```

Agent tool call (dispatch the assembled prompt — main session only):

```
Agent(model: opus, prompt: $PROMPT)
```

Each subagent runs its named steps (LOCK → UNLOCK), writes
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
- Main session uses Write or Edit on any file under `.claude/features/` → STOP.
  All feature-code edits are the TDD subagent's job, performed under an active
  scope marker. Main session role is orchestration only: resolve scope, create
  branch, invoke rabbit-feature-spec, surface impl-suggestion, dispatch subagent, verify
  HANDOFF. The only main-session writes permitted are: the confirm-token
  override flow (see Override Path), and rabbit-feature-spec's writes to
  `docs/spec/spec.md` under the scope-guard path-pattern allowlist invoked
  during Step 3.
- Main session creates `.rabbit-scope-active` (global) or
  `.rabbit-scope-active-<feature>` (per-feature) scope markers at the repo
  root → STOP. Scope markers are exclusively the TDD subagent's responsibility,
  written as the first action at LOCK (Step 3 of the subagent's named steps).
  Main-session-authored markers bypass scope-guard's intended boundary and
  have caused constitution violations (PR #93).

## Override Path

When user explicitly approves a lightweight edit (typo, comment-only), present
a confirm token with `one-time` or `session` scope. After approval, write
`.rabbit-scope-override`, make the edit directly. Does NOT reset `tdd_state`.
