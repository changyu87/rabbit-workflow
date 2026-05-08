# Rabbit Workflow Bootstrap — Design

**Date:** 2026-05-08
**Status:** Ready for implementation
**Goal:** Bootstrap the repository (newly named `rabbit-workflow`) into an
agent-aware Claude Code workspace where the two governing files
(`philosophy.md` and `work-guide.md`) are loaded at session start and
periodically refreshed against drift.

---

## 1. Motivation

The repo holds two source-of-truth files (`philosophy.md`, `work-guide.md`)
that define how AI agents should operate inside this workspace. For these
files to actually govern Claude Code sessions, they must be:

1. **Loaded into every session at startup** (so policies are present from
   prompt 1).
2. **Re-loaded after compaction** (so summarization doesn't dilute them).
3. **Periodically re-injected during long sessions** (so attention drift
   doesn't quietly erase the policy).
4. **Refreshable on demand** (so the user can force a reset when drift is
   noticed).

Claude Code natively covers (1) and (2) via `CLAUDE.md` plus `@`-import
syntax. (3) and (4) require a small custom layer: a `UserPromptSubmit` hook
with a counter, plus a slash command. The system must remain **extensible** —
adding another governing file should require only a one-line edit to
`CLAUDE.md`, never a change to the hook script or slash command.

## 2. Decisions

The following decisions were settled through bounded brainstorming with the
user (full Q&A log in §7):

1. **CLAUDE.md is the single source of truth** for which files govern the
   workspace. The hook and slash command both read CLAUDE.md to discover the
   list — no separate config file.
2. **Loading uses `@./<filename>.md` imports inside CLAUDE.md.** Auto-loaded
   at startup, auto-reloaded after compaction (Claude Code native behavior).
3. **Mid-session drift is mitigated by two complementary mechanisms:**
   manual `/rwf-refresh` slash command (user-invoked), and a
   `UserPromptSubmit` hook (automatic, every N prompts).
4. **Manual refresh resets the counter** so the auto mechanism doesn't
   double-fire immediately after.
5. **Refresh interval is configurable** via env var `RWF_REFRESH_EVERY` in
   `.claude/settings.json`. Default: 10 prompts.
6. **All user-facing artifacts are prefixed `rwf-` / `RWF_`** (slash command
   `/rwf-refresh`, env var `RWF_REFRESH_EVERY`, runtime file
   `.claude/.rwf-counter`, hook script `rwf-refresh.sh`). Prefix avoids
   collision with the `rw` (read-write) and `rm` (remove) shell mnemonics.
7. **GitHub repo renamed** from `changyu87/ai-workflow-philosophy` to
   `changyu87/rabbit-workflow`. Local origin URL updated. Local directory
   rename is the user's manual follow-up.
8. **CLAUDE.md is sharp:** boundary statement + `@` imports + a one-liner
   teaching extension. No mention of the hook or slash command (those are
   operational, not policy).
9. **The hook re-parses CLAUDE.md on each refresh** — so a new
   `@./xxx.md` line in CLAUDE.md takes effect at the next refresh without
   any restart, hook edit, or counter reset.
10. **JSON output of the hook uses Python** for safe escaping of arbitrary
    file content; bash heredocs are too brittle on quotes/backticks. Python
    is a workspace-level dependency assumption.
11. **The injected payload starts with a one-line preamble** ("Periodic
    policy refresh (every N prompts). Re-stating governing files:") so
    Claude understands why the same content reappears.
12. **`SessionStart` hook resets the counter to 0** on any session-begin
    event (startup, resume, clear, compact). Avoids redundant refresh
    immediately after a fresh CLAUDE.md load.

## 3. Files

### 3.1 `CLAUDE.md` (new, repo root)

```markdown
# Rabbit Workflow

This repository is bounded by two source-of-truth files:

@./philosophy.md
@./work-guide.md

To add more, append `@./<filename>.md` below.
```

### 3.2 `.claude/settings.json` (new)

```json
{
  "env": {
    "RWF_REFRESH_EVERY": "10"
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "echo 0 > .claude/.rwf-counter"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/rwf-refresh.sh"
          }
        ]
      }
    ]
  }
}
```

### 3.3 `.claude/hooks/rwf-refresh.sh` (new, executable)

```bash
#!/usr/bin/env bash
# rwf-refresh.sh — periodic re-injection of CLAUDE.md @-imports.
#
# Wired to UserPromptSubmit. Each prompt: increment counter; if counter
# reaches RWF_REFRESH_EVERY (default 10), emit JSON additionalContext
# containing the full content of every file that CLAUDE.md @-imports,
# then reset the counter to 0.
#
# Stays silent (exits 0 with no stdout) when not refreshing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
COUNTER_FILE="$REPO_ROOT/.claude/.rwf-counter"
THRESHOLD="${RWF_REFRESH_EVERY:-10}"

# Initialize counter on first run
[ -f "$COUNTER_FILE" ] || echo 0 > "$COUNTER_FILE"

count=$(cat "$COUNTER_FILE")
count=$((count + 1))

if [ "$count" -lt "$THRESHOLD" ]; then
    echo "$count" > "$COUNTER_FILE"
    exit 0
fi

# Threshold reached: gather @-imports from CLAUDE.md, emit additionalContext
echo 0 > "$COUNTER_FILE"

# Parse lines like '@./foo.md' or '@/abs/path.md' from CLAUDE.md
imports=$(grep -oE '^@[^[:space:]]+' "$CLAUDE_MD" | sed 's/^@//' || true)

if [ -z "$imports" ]; then
    exit 0
fi

# Build the injected context
payload_file="$(mktemp)"
trap 'rm -f "$payload_file"' EXIT

{
    printf 'Periodic policy refresh (every %s prompts). Re-stating governing files:\n\n' "$THRESHOLD"
    while IFS= read -r path; do
        # Resolve relative paths against repo root
        case "$path" in
            /*) full="$path" ;;
            *)  full="$REPO_ROOT/${path#./}" ;;
        esac
        if [ -f "$full" ]; then
            printf -- '--- %s ---\n' "$path"
            cat "$full"
            printf '\n'
        fi
    done <<< "$imports"
} > "$payload_file"

# Emit JSON for Claude Code: additionalContext is read from stdout
python3 -c "
import json, sys
with open('$payload_file', 'r') as f:
    payload = f.read()
print(json.dumps({'additionalContext': payload}))
"
```

### 3.4 `.claude/commands/rwf-refresh.md` (new)

```markdown
---
description: Re-inject the rabbit-workflow policy files into context and reset the auto-refresh counter.
allowed-tools: Bash
---

Refreshing rabbit-workflow policy files.

!`echo 0 > .claude/.rwf-counter`

!`for p in $(grep -oE '^@[^[:space:]]+' CLAUDE.md | sed 's/^@//'); do echo "=== $p ==="; cat "$p"; echo; done`

In one sentence, confirm which files were refreshed.
```

### 3.5 `.gitignore` (modify)

Append:

```
# Rabbit Workflow runtime state
.claude/.rwf-counter
```

## 4. Out of Scope

- **Subagent loading.** This spec only ensures the **main** session loads
  the governing files. Each subagent (launched via the `Agent` tool with a
  `subagent_type`) has its own configuration; making subagents load
  `philosophy.md` is a separate, future task.
- **Slash command for editing CLAUDE.md.** The user's earlier idea of a
  `/policy` configuration command was dropped — adding a governing file is
  a one-line edit to `CLAUDE.md`, simple enough that a slash command would
  add more friction than it removes.
- **Subagent prefixing.** The user stated "every command, subagent, skill
  shall start with rwf-". This spec covers the slash command. There are no
  custom subagents or skills *being created* in this round; future
  custom artifacts must follow the prefix convention.
- **Telemetry / metrics.** No counter dashboard, no refresh log, no proof
  the hook is firing — diagnosis is via running the hook manually if
  needed.
- **Translation.** No Chinese mirrors of CLAUDE.md or any new file.

## 5. Acceptance Criteria

A new clone of the repo, after running a Claude Code session in its root,
must satisfy:

- `CLAUDE.md` is auto-loaded; both `philosophy.md` and `work-guide.md`
  contents are visible to the model from prompt 1.
- After 10 user prompts in a session, the model receives a re-injection of
  both files (verifiable by inspecting the counter file `.claude/.rwf-counter`
  resetting to 0 and the hook payload appearing in the conversation).
- `/rwf-refresh` invoked at any time prints both files' contents into the
  conversation, resets the counter to 0, and Claude responds with a
  one-sentence acknowledgement.
- After `/compact`, `CLAUDE.md` is reloaded automatically (Claude Code
  native behavior) AND the counter is reset to 0 (via SessionStart hook).
- Adding a new line `@./extra.md` to `CLAUDE.md` makes that file appear in
  the next refresh payload (auto or manual) without restarting the session
  or editing any other file.
- Setting `RWF_REFRESH_EVERY` to `5` in `.claude/settings.json` and
  starting a new session causes refresh to fire every 5 prompts.
- `.claude/.rwf-counter` is gitignored — `git status` never shows it.
- All committed artifacts:
  - `CLAUDE.md`
  - `.claude/settings.json`
  - `.claude/hooks/rwf-refresh.sh` (executable, mode 755)
  - `.claude/commands/rwf-refresh.md`
  - `.gitignore` (modified, with the new entry)
- No changes to `philosophy.md`, `work-guide.md`, or any file under
  `archive/` or `docs/`.

## 6. Validation Plan

After implementation, verify by:

1. `cat CLAUDE.md` — confirm content matches §3.1.
2. `bash -n .claude/hooks/rwf-refresh.sh` — confirm script syntax is valid.
3. `RWF_REFRESH_EVERY=2 .claude/hooks/rwf-refresh.sh; cat .claude/.rwf-counter`
   — should print no JSON (counter increments to 1), then `echo 1`.
4. Run again: `RWF_REFRESH_EVERY=2 .claude/hooks/rwf-refresh.sh; cat .claude/.rwf-counter`
   — should print JSON with `additionalContext` field containing both
   `philosophy.md` and `work-guide.md` contents, and counter resets to 0.
5. `jq . <(echo '<output of step 4>')` — confirm valid JSON.
6. `git status` — confirm no untracked or modified files beyond what is
   expected for this commit.

## 7. Appendix — Brainstorm decision log

| # | Question | Resolution |
|---|---|---|
| 1 | Mid-session drift mitigation mechanism? | Both A (manual `/rwf-refresh`) and B (auto hook every N), with manual reset of counter |
| 2 | Configuration scope? | Dropped — extensibility is one-line edit to CLAUDE.md, no JSON config or `/policy` command |
| 3 | Default refresh interval? | Configurable via env var `RWF_REFRESH_EVERY`, default 10 |
| 4 | Prefix? | `rwf-` (was `rw-`, expanded to disambiguate from `rw`/`rm`) |
| 5 | GitHub repo rename? | Yes, to `rabbit-workflow`; local origin updated; local directory rename deferred to user |
| 6 | CLAUDE.md title? | `# Rabbit Workflow` — kept |
| 7 | CLAUDE.md audience commentary? | Dropped — each file declares its own audience in its first line |
| 8 | CLAUDE.md extension instruction? | One-liner: "To add more, append `@./<filename>.md` below." |
| 9 | JSON encoding in hook? | Python (safer than bash heredoc for arbitrary file content) |
| 10 | Refresh payload preamble? | Included — gives Claude context for why the same content reappears |
