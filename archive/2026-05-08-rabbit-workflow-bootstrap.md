# Rabbit Workflow Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the repository as an agent-aware Claude Code workspace where `philosophy.md` and `work-guide.md` load at session start and refresh periodically.

**Architecture:** A short `CLAUDE.md` at repo root uses `@./...` imports to pull both governing files into context at startup. A `UserPromptSubmit` hook (`.claude/hooks/rwf-refresh.sh`) re-injects them every N prompts (counter at `.rwf-counter`, default N=10 via env var `RWF_REFRESH_EVERY`). A `SessionStart` hook resets the counter on session begin. A `/rwf-refresh` slash command does the same on demand and resets the counter.

**Tech Stack:** Markdown, JSON, bash, Python3 (only for safe JSON encoding inside the hook script).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `CLAUDE.md` | Create | Sharp boundary statement + `@`-imports of governing files |
| `.claude/settings.json` | Create | Wires SessionStart + UserPromptSubmit hooks; declares `RWF_REFRESH_EVERY` env var |
| `.claude/hooks/rwf-refresh.sh` | Create (mode 755) | Counter increment; on threshold, parse CLAUDE.md @-imports, emit JSON `additionalContext` |
| `.claude/commands/rwf-refresh.md` | Create | `/rwf-refresh` slash command — manual refresh + counter reset |
| `.gitignore` | Modify (append) | Exclude `.rwf-counter` runtime state |
| `.rwf-counter` | Runtime artifact | Created on first hook invocation; never committed |
| `philosophy.md` | Untouched | Loaded by CLAUDE.md @ import |
| `work-guide.md` | Untouched | Loaded by CLAUDE.md @ import |

---

### Task 1: Create `CLAUDE.md`

**Files:**
- Create: `/home/cyxu/ai-workflow-philosophy/CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md**

Use the Write tool to write the following exact content to `/home/cyxu/ai-workflow-philosophy/CLAUDE.md`:

````markdown
# Rabbit Workflow

This repository is bounded by two source-of-truth files:

@./philosophy.md
@./work-guide.md

To add more, append `@./<filename>.md` below.
````

- [ ] **Step 2: Verify content**

Run: `cat /home/cyxu/ai-workflow-philosophy/CLAUDE.md`

Expected: the seven non-blank lines above appear in order, including the two `@./` lines verbatim.

---

### Task 2: Create `.claude/` tree and `settings.json`

**Files:**
- Create: `/home/cyxu/ai-workflow-philosophy/.claude/settings.json`
- Create directories: `/home/cyxu/ai-workflow-philosophy/.claude/hooks/`, `/home/cyxu/ai-workflow-philosophy/.claude/commands/`

- [ ] **Step 1: Create the directory tree**

Run: `mkdir -p /home/cyxu/ai-workflow-philosophy/.claude/hooks /home/cyxu/ai-workflow-philosophy/.claude/commands && ls -la /home/cyxu/ai-workflow-philosophy/.claude/`

Expected: directories `hooks/` and `commands/` exist under `.claude/`.

- [ ] **Step 2: Write settings.json**

Use the Write tool to write the following exact content to `/home/cyxu/ai-workflow-philosophy/.claude/settings.json`:

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
            "command": "echo 0 > .rwf-counter"
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

- [ ] **Step 3: Verify JSON is valid**

Run: `python3 -m json.tool < /home/cyxu/ai-workflow-philosophy/.claude/settings.json > /dev/null && echo OK`

Expected: `OK` on stdout, exit 0. If JSON is invalid, Python prints the error and exits non-zero — fix and re-run.

---

### Task 3: Update `.gitignore` (early — so counter file is ignored before validation creates it)

**Files:**
- Modify: `/home/cyxu/ai-workflow-philosophy/.gitignore`

- [ ] **Step 1: Append the runtime-state entry**

Read the current `.gitignore` first to see exact existing content:

Run: `cat /home/cyxu/ai-workflow-philosophy/.gitignore`

Expected current content (verbatim):
```
# Vim swap files
*.swp
*.swo
.*.swp
.*.swo
```

Then use the Edit tool to add the new section. Old string:
```
# Vim swap files
*.swp
*.swo
.*.swp
.*.swo
```
New string:
```
# Vim swap files
*.swp
*.swo
.*.swp
.*.swo

# Rabbit Workflow runtime state
.rwf-counter
```

- [ ] **Step 2: Verify**

Run: `cat /home/cyxu/ai-workflow-philosophy/.gitignore`

Expected: both sections present, the new one separated by a blank line.

---

### Task 4: Create the auto-refresh hook script

**Files:**
- Create: `/home/cyxu/ai-workflow-philosophy/.claude/hooks/rwf-refresh.sh` (mode 755)

- [ ] **Step 1: Write the hook script**

Use the Write tool to write the following exact content to `/home/cyxu/ai-workflow-philosophy/.claude/hooks/rwf-refresh.sh`:

````bash
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
COUNTER_FILE="$REPO_ROOT/.rwf-counter"
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
import json
with open('$payload_file', 'r') as f:
    payload = f.read()
print(json.dumps({'additionalContext': payload}))
"
````

- [ ] **Step 2: Make script executable**

Run: `chmod 755 /home/cyxu/ai-workflow-philosophy/.claude/hooks/rwf-refresh.sh && ls -la /home/cyxu/ai-workflow-philosophy/.claude/hooks/rwf-refresh.sh`

Expected: file mode shows `-rwxr-xr-x` (i.e., `755`).

- [ ] **Step 3: Bash syntax check**

Run: `bash -n /home/cyxu/ai-workflow-philosophy/.claude/hooks/rwf-refresh.sh && echo "syntax OK"`

Expected: `syntax OK` on stdout. Any stderr means a syntax error — fix before continuing.

- [ ] **Step 4: Functional test — silent mode (counter < threshold)**

Run: `cd /home/cyxu/ai-workflow-philosophy && rm -f .rwf-counter && RWF_REFRESH_EVERY=2 .claude/hooks/rwf-refresh.sh; echo "exit=$?"; cat .rwf-counter`

Expected output:
```
exit=0
1
```

(no JSON on stdout; counter became 1 because threshold=2 and this was the first call.)

- [ ] **Step 5: Functional test — refresh mode (counter hits threshold)**

Run: `cd /home/cyxu/ai-workflow-philosophy && RWF_REFRESH_EVERY=2 .claude/hooks/rwf-refresh.sh; echo "exit=$?"; cat .rwf-counter`

Expected: a JSON object printed to stdout with one key `additionalContext` whose value contains the literal strings `philosophy.md` and `work-guide.md` (because the payload includes their content). Then `exit=0` and counter `0`.

To confirm JSON validity, run: `cd /home/cyxu/ai-workflow-philosophy && rm -f .rwf-counter && RWF_REFRESH_EVERY=1 .claude/hooks/rwf-refresh.sh | python3 -m json.tool > /dev/null && echo "JSON valid"`

Expected: `JSON valid` on stdout, exit 0.

- [ ] **Step 6: Clean up runtime state**

Run: `rm -f /home/cyxu/ai-workflow-philosophy/.rwf-counter && ls /home/cyxu/ai-workflow-philosophy/.rwf-counter 2>&1`

Expected: `ls: cannot access ...: No such file or directory`. (Counter is gitignored anyway, but cleaning leaves a tidy working tree.)

---

### Task 5: Create the `/rwf-refresh` slash command

**Files:**
- Create: `/home/cyxu/ai-workflow-philosophy/.claude/commands/rwf-refresh.md`

- [ ] **Step 1: Write the slash command file**

Use the Write tool to write the following exact content to `/home/cyxu/ai-workflow-philosophy/.claude/commands/rwf-refresh.md`:

````markdown
---
description: Re-inject the rabbit-workflow policy files into context and reset the auto-refresh counter.
allowed-tools: Bash
---

Refreshing rabbit-workflow policy files.

!`echo 0 > .rwf-counter`

!`for p in $(grep -oE '^@[^[:space:]]+' CLAUDE.md | sed 's/^@//'); do echo "=== $p ==="; cat "$p"; echo; done`

In one sentence, confirm which files were refreshed.
````

- [ ] **Step 2: Verify**

Run: `cat /home/cyxu/ai-workflow-philosophy/.claude/commands/rwf-refresh.md`

Expected: the file content matches the block above, with the YAML frontmatter intact (between two `---` lines).

---

### Task 6: Sanity-check git status and commit

**Files staged:** `CLAUDE.md`, `.gitignore`, `.claude/settings.json`, `.claude/hooks/rwf-refresh.sh`, `.claude/commands/rwf-refresh.md`

**Files NOT staged:** `.rwf-counter` (gitignored; should not appear)

- [ ] **Step 1: View git status**

Run: `cd /home/cyxu/ai-workflow-philosophy && git status --short`

Expected output (order may vary):
```
 M .gitignore
?? .claude/
?? CLAUDE.md
```

(`.claude/` shows untracked because no files inside are tracked yet. The `.rwf-counter` file should NOT appear; if it does, Task 4 Step 6 was skipped.)

- [ ] **Step 2: Verify the runtime counter is not present**

Run: `git status --short | grep -F '.rwf-counter'; echo "exit=$?"`

Expected: `exit=1` (no matches). If exit=0, the counter file is being tracked or shown — clean it up before continuing.

- [ ] **Step 3: Stage only the intended files**

Run: `cd /home/cyxu/ai-workflow-philosophy && git add CLAUDE.md .gitignore .claude/settings.json .claude/hooks/rwf-refresh.sh .claude/commands/rwf-refresh.md`

- [ ] **Step 4: Verify staging**

Run: `git status --short`

Expected:
```
M  .gitignore
A  .claude/commands/rwf-refresh.md
A  .claude/hooks/rwf-refresh.sh
A  .claude/settings.json
A  CLAUDE.md
```

(no untracked files; `.rwf-counter` is gitignored and absent.)

- [ ] **Step 5: Commit**

Run:

```bash
cd /home/cyxu/ai-workflow-philosophy && git commit -m "$(cat <<'EOF'
Bootstrap rabbit-workflow as agent-aware Claude Code workspace

CLAUDE.md is the sharp boundary statement: it declares the workspace
is governed by philosophy.md and work-guide.md, loads both via @-imports
(auto-loaded at session start, auto-reloaded after compaction), and
teaches users to extend with one more @-import line.

.claude/settings.json wires two hooks:
  - SessionStart resets the auto-refresh counter on every session begin.
  - UserPromptSubmit runs .claude/hooks/rwf-refresh.sh on every prompt,
    which re-injects all @-imported files every RWF_REFRESH_EVERY
    prompts (default 10).

The /rwf-refresh slash command does a manual reload + counter reset.

The runtime counter file (.rwf-counter) is gitignored.

Design spec: docs/superpowers/specs/2026-05-08-rabbit-workflow-bootstrap-design.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Verify commit landed and tree is clean**

Run: `git status && git log -1 --stat`

Expected: working tree clean (or only the gitignored `.rwf-counter` if it got recreated by some other means); the commit shows 5 files changed.

---

## Self-Review Checklist (run mentally before declaring done)

1. **Spec coverage:**
   - Spec §3.1 CLAUDE.md → Task 1 ✓
   - Spec §3.2 settings.json → Task 2 ✓
   - Spec §3.3 hook script → Task 4 ✓
   - Spec §3.4 slash command → Task 5 ✓
   - Spec §3.5 .gitignore → Task 3 ✓
   - Spec §5 acceptance: gitignored counter → Task 3 + Task 6 Step 2 ✓
   - Spec §5 acceptance: hook chmod 755 → Task 4 Step 2 ✓
   - Spec §6 validation steps 1-4 → Task 4 Steps 3-5 ✓

2. **No placeholders:** Every step contains exact code or commands. No "fill in", no "similar to", no "TBD".

3. **Type/name consistency:** `RWF_REFRESH_EVERY`, `.rwf-counter`, `rwf-refresh.sh`, `/rwf-refresh` all spelled identically across files and tasks.

4. **Order safety:** `.gitignore` (Task 3) is created before the hook is functionally tested (Task 4) so the counter file generated by validation is already excluded; commit (Task 6) happens last after explicit sanity checks.
