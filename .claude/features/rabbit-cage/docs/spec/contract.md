---
feature: rabbit-cage
version: 5.13.0
template_version: 2.0.0
---

# rabbit-cage — Contract

```json
{
  "provides": {
    "files": [
      ".claude/hooks/scope-guard.py",
      ".claude/hooks/stop-dispatcher.py",
      ".claude/hooks/session-start-dispatcher.py",
      ".claude/hooks/user-prompt-submit-dispatcher.py",
      ".claude/settings.json",
      ".claude/commands/rabbit-refresh.md",
      ".claude/commands/rabbit-project.md",
      "CLAUDE.md",
      "README.md",
      "install.py"
    ],
    "commands": [],
    "scripts": [
      {"path": ".claude/features/rabbit-cage/install.py", "stdin": "none", "stdout": "install log", "exit": "0=ok 1=error 2=usage", "note": "bootstrap installer; copies tree and invokes run_publish_loop"},
      {"path": ".claude/features/rabbit-cage/scripts/scope-guard-on.py", "stdin": "none", "stdout": "confirmation message", "exit": "0=ok", "note": "deletes .rabbit-scope-override; canonical 'scope guard back on'"},
      {"path": ".claude/features/rabbit-cage/scripts/repo-permissions.py", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error", "note": "invoked via contract.lib.mutation.run_feature_script for /rabbit-config permissions lock|unlock"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project.py", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-set-path.py", "stdin": "none", "stdout": "none", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py set-path"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-map.py", "stdin": "none", "stdout": "none", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py map"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-consolidate.py", "stdin": "none", "stdout": "warnings to stderr", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py consolidate"},
      {"path": ".claude/features/rabbit-cage/scripts/workspace-tree.py", "stdin": "none", "stdout": "annotated workspace tree", "exit": "0=ok 1=error"},
      {"path": ".claude/features/rabbit-cage/lib/project_map_reader.py", "stdin": "none", "stdout": "none", "exit": "n/a (importable module)", "note": "plugin-mode project-map I/O + path matching; imported by scope-guard.py"}
    ],
    "schemas": [],
    "templates": [],
    "skills": []
  },
  "reads": {
    "files": [
      ".claude/features/*/feature.json",
      ".claude/features/policy/*.md",
      ".rabbit-scope-active",
      ".rabbit-scope-active-*",
      ".rabbit-scope-override",
      ".rabbit-scope-override-used",
      ".rabbit-human-approval-bypass",
      ".rabbit-skills-updated",
      ".rabbit/.runtime/mode",
      ".rabbit/.runtime/scope-active-*",
      ".rabbit/.runtime/scope-bypass-once",
      ".rabbit/rabbit-project/project-map.json"
    ],
    "external": ["env-var:RABBIT_ROOT", "env-var:RABBIT_REFRESH_EVERY"]
  },
  "invokes": {
    "modules": [
      {"path": ".claude/features/contract/lib/publish.py", "purpose": "install-time MANIFEST API calls"},
      {"path": ".claude/features/contract/lib/runtime.py", "purpose": "per-event RUNTIME API calls"},
      {"path": ".claude/features/contract/lib/producers.py", "purpose": "content producers invoked by publish_generated and check_drift_regenerate"},
      {"path": ".claude/features/contract/scripts/rabbit_print.py", "purpose": "dispatcher output rendering (rabbit_subline, rabbit_block)"}
    ],
    "scripts": [
      {"path": ".claude/features/contract/scripts/find-feature.py", "purpose": "scope-guard.py feature-name -> path resolution"}
    ]
  },
  "manages": {
    "runtime_markers": [
      {"path": ".rabbit-scope-override", "writer": "human or Claude (after explicit in-conversation user approval)", "reader": "scope-guard.py, stop-dispatcher.py (via check_marker_alert)", "lifecycle": "human or Claude creates; scope-guard.py deletes on one-time consumption; persists for session mode", "gitignored": true},
      {"path": ".rabbit-scope-override-used", "writer": "scope-guard.py", "reader": "stop-dispatcher.py (via check_marker_consume_alert)", "lifecycle": "created by scope-guard.py on one-time consumption; consumed (deleted) by check_marker_consume_alert", "gitignored": true},
      {"path": ".rabbit/.runtime/scope-bypass-once", "writer": "human or Claude (after explicit in-conversation user approval)", "reader": "scope-guard.py", "lifecycle": "human or Claude creates via touch; scope-guard.py consumes (deletes) before evaluating any decision so failed edits cannot leave a persistent bypass", "gitignored": true}
    ]
  },
  "never": [
    "writes .claude/settings.local.json except via /rabbit-config (owned by rabbit-config feature)",
    "modifies files inside another feature's directory",
    "writes outside its declared scope without an active scope marker or scope-guard override",
    "introduces a new .sh runtime script under hooks/ or scripts/"
  ]
}
```

## Tech Stack

Python 3 stdlib only. Imports `contract.lib.publish`, `contract.lib.runtime`,
`contract.lib.producers`, and `contract.scripts.rabbit_print`. No Bash
runtime dependency.

## Dispatcher Output Schema

Each event dispatcher emits at most one JSON object to stdout per
invocation, of shape:

```
{"systemMessage": "<aggregated rabbit_block string>",
 "additionalContext": "<concatenated inject content (optional)>"}
```

`systemMessage` and `additionalContext` are each omitted when the
corresponding partition is empty. When both are empty, no JSON is written
(exit 0, empty stdout).
