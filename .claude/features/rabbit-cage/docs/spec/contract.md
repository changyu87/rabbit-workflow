---
feature: rabbit-cage
version: 4.5.0
template_version: 2.0.0
---

# rabbit-cage — Contract

```json
{
  "provides": {
    "files": [".claude/commands", ".claude/hooks", ".claude/skills", ".claude/settings.json", ".claude/policy", ".claude/contract", "CLAUDE.md", "README.md", "install.py"],
    "commands": [],
    "scripts": [
      {"path": ".claude/features/rabbit-cage/scripts/new-feature.py", "stdin": "none", "stdout": "scaffold path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project.py", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/generate-claude-md.py", "stdin": "none", "stdout": "CLAUDE.md content", "exit": "0=ok 1=error"},
      {"path": ".claude/features/rabbit-cage/scripts/build.py", "stdin": "none", "stdout": "build log", "exit": "0=ok 1=error", "note": "reads build-contract.json and builds all declared targets"},
      {"path": ".claude/features/rabbit-cage/scripts/scope-guard-on.py", "stdin": "none", "stdout": "confirmation message", "exit": "0=ok", "note": "deletes .rabbit-scope-override; canonical 'scope guard back on'"},
      {"path": ".claude/features/rabbit-cage/scripts/workspace-tree.py", "stdin": "none", "stdout": "annotated workspace tree", "exit": "0=ok 1=error", "note": "workspace tree rendering"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-set-path.py", "stdin": "none", "stdout": "none", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py set-path"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-map.py", "stdin": "none", "stdout": "none", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py map"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-consolidate.py", "stdin": "none", "stdout": "warnings to stderr", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py consolidate"},
      {"path": ".claude/features/rabbit-cage/scripts/build-targets.py", "stdin": "none", "stdout": "build log", "exit": "0=ok 1=error", "note": "helper invoked by build.py"},
      {"path": ".claude/features/rabbit-cage/scripts/generate-claude-md-header.py", "stdin": "none", "stdout": "CLAUDE.md header line", "exit": "0=ok 1=error", "note": "helper invoked by generate-claude-md.py"}
    ],
    "schemas": [
      {
        "name": "sync-check-output",
        "version": "1.0.0",
        "description": "JSON emitted by sync-check.py to stdout on Stop. At most one object per invocation (aggregation strategy — BACKLOG-18). systemMessage is the newline-joined concatenation of every pending condition's ANSI-colored [rabbit] line, ordered by priority. additionalContext (optional) is present only when CLAUDE.md drift/first-run is among the pending conditions.",
        "strategy": "aggregation",
        "priority_order": ["CLAUDE.md-drift-or-first-run", "surface-drift", "scope-guard-off", "human-approval-bypass", "skills-updated"]
      }
    ],
    "templates": [],
    "skills": [
      {"path": ".claude/features/rabbit-cage/skills/rabbit-config/", "subcommands": ["prompt-threshold [value]", "allowed-tools [add|remove <tool>]", "bash-allow [add|remove <command>]", "permissions [lock|unlock]", "human-approval [true|false]", "bypass-permissions [true|false]"]}
    ]
  },
  "reads": {
    "files": ["project-*/project-map.json", ".claude/features/contract/templates/", ".rabbit-scope-override", ".rabbit-scope-override-used"],
    "external": ["env-var:RABBIT_ROOT"]
  },
  "invokes": {
    "scripts": [],
    "agents":   []
  },
  "manages": {
    "runtime_markers": [
      {"path": ".rabbit-scope-override", "writer": "human or Claude (after explicit in-conversation user approval via confirm-token flow)", "reader": "scope-guard.py, sync-check.py", "lifecycle": "human or Claude creates (after in-conversation approval); scope-guard.py deletes on one-time consumption; persists for session mode", "gitignored": true},
      {"path": ".rabbit-scope-override-used", "writer": "scope-guard.py", "reader": "sync-check.py", "lifecycle": "created by scope-guard.py on one-time consumption; deleted by sync-check.py after one alert", "gitignored": true}
    ]
  },
  "never": [
    "writes .claude/settings.local.json except via the /rabbit-config command on explicit user request",
    "modifies files inside another feature's directory",
    "writes outside its declared scope without an active scope marker or scope-guard override",
    "exposes /rabbit-set-threshold (replaced by /rabbit-config prompt-threshold)",
    "introduces a new .sh runtime script under hooks/ or scripts/ (Python is the sole runtime tech stack)"
  ]
}
```

## Tech Stack

Python 3 is the sole runtime scripting language for rabbit-cage. Every
runtime script under `hooks/` and `scripts/` is a standalone executable
Python file (`#!/usr/bin/env python3`); each preserves the
stdin/stdout/exit-code contract of the `.sh` predecessor it replaces. Bash
is not a runtime dependency for any rabbit-cage hook or script. The sole
The bootstrap installer is `install.py` at the rabbit-cage root (stdlib-only Python).

## CLAUDE.md Drift-Check Behavior

`CLAUDE.md` at the repo root is a committed artifact produced by
`generate-claude-md.py`. It is not gitignored.

On every Stop event, `sync-check.py` computes the expected `CLAUDE.md`
content from the current policy source files and compares it byte-for-byte
against the committed `CLAUDE.md`. If they differ, the hook regenerates
`CLAUDE.md` in place and emits a deep-green `[rabbit]` `systemMessage`
indicating that the committed copy drifted from the policy sources and that
the human should commit the regenerated file. If the committed file is
absent, the hook treats it as the first-run scenario and creates it.

## Skills-Directory Build Behavior

`build.py` populates `.claude/skills/` by recursively copying each
registered feature's skill source directory using shutil (preserving mode
and timestamps via `shutil.copy2`). It does not create or follow symlinks
for skill content. This functionality is driven by the `copy-file` targets
in `build-contract.json` (the standalone `generate-skills-dir.py` does not
exist; see Spec Inv 27).

`build.py --check` mode compares the sha256 of every source `SKILL.md`
directly against the sha256 of the corresponding copy at
`.claude/skills/<name>/SKILL.md`. No baseline hash file is read or written.
Exit `1` indicates drift in check mode; exit `0` indicates the copy tree
matches source (or, in non-check mode, that the copy operation completed
successfully).
