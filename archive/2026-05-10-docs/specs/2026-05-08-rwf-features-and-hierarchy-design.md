# RWF Features & Repository Hierarchy — Design

**Date:** 2026-05-08
**Status:** Ready for implementation
**Owner:** rabbit-workflow team
**Deprecation criterion:** Superseded when a major repo restructure changes the layout again

---

## 1. Motivation

Three improvements to the `rabbit-workflow` agent workspace:

1. **Counter rename** — `.rwf-counter` is vague; the file counts user prompts, so the name should say so.
2. **Threshold slash command** — `RWF_REFRESH_EVERY` is only configurable by hand-editing `settings.json`. A slash command lets users set their personal threshold without touching a shared file.
3. **Repository hierarchy** — the current layout (governance files at root, `docs/` at root, `archive/` at root) violates bounded scope. As the workflow grows and users install it into their own workspaces, a clear structural contract is needed: one owner per directory, one install footprint, no ambiguity about what is workflow-internal vs. user-owned.

---

## 2. Decisions

### 2.1 Counter rename

**`.rwf-counter` → `.rwf-prompt-counter`**

The file counts `UserPromptSubmit` events. The name `.rwf-prompt-counter` matches the event it counts. `rwf-refresh-counter` was considered but rejected — it names the downstream effect (refresh), not the measured input (prompts). Accurate naming at the source is preferred.

### 2.2 Threshold slash command

**Command name:** `/rwf-set-threshold`
**Write target:** `.claude/settings.local.json` (user-local, gitignored)
**Implementation:** Python3 inline (consistent with `rwf-refresh.sh`; safer than jq for JSON mutation)
**Default change:** `RWF_REFRESH_EVERY` in `settings.json` bumped from `10` → `20`

Rationale for `settings.local.json`: threshold preference is personal, not project-wide. Committing it would force all collaborators onto the same cadence. `settings.local.json` is gitignored so each user's override stays local.

The command takes effect on the **next session start** (Claude Code reads env vars from settings files at launch, not mid-session).

### 2.3 Repository hierarchy

**Core principle:** `.claude/` is the workflow's only footprint. Everything the workflow owns lives there. The workspace root contains only `CLAUDE.md` (required by Claude Code) and user-owned content. `archive/` is a dev-only artifact — it ships with the source repo but never with an install.

**Install contract:**
```
copy .claude/ + CLAUDE.md → user's workspace-home/
```
Everything else in the source repo is not part of the install.

**Why `.claude/` as ground truth layer:**
- Bounded scope: one directory, one owner (the workflow), one purpose (agent configuration + policy)
- Minimal root footprint: users open their workspace and see their own files, not the workflow's
- Multi-project support: users can structure `workspace-home/project-a/`, `workspace-home/project-b/` freely — the workflow never touches those paths

**Why `archive/` stays at dev repo root (not in `.claude/`):**
- Not installable: archive is historical record for workflow developers, irrelevant to users
- Not governed by the workflow's bounded scope: it's a passive record, not an active artifact
- Structural exclusion: by not living in `.claude/`, it is naturally excluded from any install

---

## 3. Final Structure

### 3.1 Dev repo (source of truth)

```
rabbit-workflow/
├── .claude/                         ← entire workflow footprint
│   ├── commands/
│   │   ├── rwf-refresh.md           (existing)
│   │   └── rwf-set-threshold.md     (NEW)
│   ├── docs/                        ← workflow design records
│   │   ├── specs/                   (this file lives here)
│   │   ├── plans/
│   │   ├── meta/                    ← changelog, version, rwf identity
│   │   └── bugs/
│   ├── hooks/
│   │   └── rwf-refresh.sh           (existing, updated)
│   ├── philosophy.md                (MOVED from root)
│   ├── work-guide.md                (MOVED from root)
│   ├── settings.json                (updated: default 10→20, counter name)
│   └── settings.local.json          (gitignored, user-local)
├── CLAUDE.md                        ← only workflow-owned file at root
├── archive/                         ← dev-only, never installed
│   ├── philosophy-CN.md
│   ├── philosophy-brainstorm.md
│   ├── philosophy-debate.md
│   ├── philosophy-holes.md
│   ├── 2026-05-08-rabbit-workflow-bootstrap-design.md   (MOVED from docs/)
│   ├── 2026-05-08-rabbit-workflow-bootstrap.md          (MOVED from docs/)
│   ├── 2026-05-08-philosophy-split-design.md            (MOVED from docs/)
│   └── 2026-05-08-philosophy-split.md                   (MOVED from docs/)
└── .gitignore                       (updated)
```

### 3.2 User's installed workspace

```
workspace-home/
├── .claude/
│   ├── commands/
│   ├── docs/{specs,plans,meta,bugs}/   ← grows during workflow use
│   ├── hooks/
│   ├── philosophy.md
│   ├── work-guide.md
│   └── settings.json
├── CLAUDE.md
└── (user's projects — entirely unrestricted)
```

---

## 4. File-by-file changes

### 4.1 Counter rename — `.rwf-counter` → `.rwf-prompt-counter`

| File | Change |
|---|---|
| `.claude/settings.json` | `SessionStart` command: `echo 0 > .rwf-counter` → `echo 0 > .rwf-prompt-counter` |
| `.claude/hooks/rwf-refresh.sh` | `COUNTER_FILE` var: `.rwf-counter` → `.rwf-prompt-counter` |
| `.claude/commands/rwf-refresh.md` | reset command: `echo 0 > .rwf-counter` → `echo 0 > .rwf-prompt-counter` |
| `.gitignore` | `.rwf-counter` → `.rwf-prompt-counter` |

### 4.2 New file: `.claude/commands/rwf-set-threshold.md`

```markdown
---
description: Set the auto-refresh threshold (prompts between policy re-injections). Writes to settings.local.json. Takes effect next session.
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
```

### 4.3 `settings.json` changes

- `RWF_REFRESH_EVERY`: `"10"` → `"20"`
- `SessionStart` command: counter name updated (see 4.1)

### 4.4 `CLAUDE.md` import updates

```markdown
@./.claude/philosophy.md
@./.claude/work-guide.md
```

### 4.5 `.gitignore` additions

```
.claude/settings.local.json
```

(In addition to the counter rename from `.rwf-counter` to `.rwf-prompt-counter`.)

### 4.6 Migration — git mv operations

```bash
git mv philosophy.md .claude/philosophy.md
git mv work-guide.md .claude/work-guide.md
git mv docs/superpowers/specs/2026-05-08-rabbit-workflow-bootstrap-design.md archive/
git mv docs/superpowers/specs/2026-05-08-philosophy-split-design.md archive/
git mv docs/superpowers/plans/2026-05-08-rabbit-workflow-bootstrap.md archive/
git mv docs/superpowers/plans/2026-05-08-philosophy-split.md archive/
```

Then remove the old `docs/` tree and create `.claude/docs/{specs,plans,meta,bugs}/` with `.gitkeep` files.

---

## 5. Out of Scope

- **Install mechanism** — how the workflow gets from this repo into a user's `workspace-home/` (script, git submodule, manual copy) is a future task
- **Multi-project conventions** — how users structure projects within their workspace is entirely their business; the workflow does not dictate it
- **Subagent hierarchy** — loading policy into subagent sessions is a prior open item, unchanged by this spec
- **`docs/meta/` initial content** — creating `CHANGELOG.md` or `VERSION` is a follow-up; this spec only establishes the directory

---

## 6. Acceptance Criteria

- `philosophy.md` and `work-guide.md` are absent from repo root; present at `.claude/philosophy.md` and `.claude/work-guide.md`
- `CLAUDE.md` imports resolve correctly: `@./.claude/philosophy.md` and `@./.claude/work-guide.md`
- `.rwf-prompt-counter` is gitignored; `.rwf-counter` name is gone from all files
- `/rwf-set-threshold 5` writes `{"env": {"RWF_REFRESH_EVERY": "5"}}` to `.claude/settings.local.json`
- `settings.json` default is `"20"`, `settings.local.json` is gitignored
- `docs/superpowers/` is gone; bootstrap specs/plans are in `archive/`
- `.claude/docs/{specs,plans,meta,bugs}/` exist (`.gitkeep` or initial content)
- Only `CLAUDE.md`, `archive/`, `.gitignore`, and `.claude/` exist at repo root (plus `.git/`)
- `git status` shows clean after all migrations committed
