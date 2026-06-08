---
feature: rabbit-cage
version: 5.86.0
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
      ".claude/commands/rabbit-update.md",
      ".claude/commands/rabbit-cage-config.md",
      "CLAUDE.md",
      "README.md",
      "install.py"
    ],
    "commands": [],
    "scripts": [
      {"path": ".claude/features/rabbit-cage/install.py", "stdin": "none", "stdout": "install log", "exit": "0=ok 1=error 2=usage", "note": "bootstrap installer; copies tree and invokes run_publish_loop; supports --update for in-place refresh (spec Inv 22), emitting a post-update changelog summary sourced from the live vX.Y.Z git tags on success (spec Inv 46)"},
      {"path": ".claude/features/rabbit-cage/scripts/scope-guard-on.py", "stdin": "none", "stdout": "confirmation message", "exit": "0=ok", "note": "deletes .rabbit-scope-override; canonical 'scope guard back on'"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project.py", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-set-path.py", "stdin": "none", "stdout": "none", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py set-path"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project-map.py", "stdin": "none", "stdout": "none", "exit": "0=ok 1=error", "note": "helper invoked by rabbit-project.py map"},
      {"path": ".claude/features/rabbit-cage/scripts/workspace-tree.py", "stdin": "none", "stdout": "annotated workspace tree", "exit": "0=ok 1=error"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-update.py", "stdin": "none", "stdout": "check: current-vs-latest JSON; install: install.py log", "exit": "0=ok 1=error 2=usage", "note": "backs /rabbit-update; check reuses contract check-release-update.py probe (non-throttled), install invokes install.py --update (spec Inv 35)"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-cage-config.py", "stdin": "none", "stdout": "config messages + restart prompt", "exit": "0=ok 1=error 2=usage", "note": "backs /rabbit-cage-config; thin wrapper over contract.lib.config_dispatch.dispatch_config for rabbit-cage's 5 owned configurables (spec Inv 40)"},
      {"path": ".claude/features/rabbit-cage/lib/project_map_reader.py", "stdin": "none", "stdout": "none", "exit": "n/a (importable module)", "note": "plugin-mode project-map I/O + path matching; imported by scope-guard.py"},
      {"path": ".claude/features/rabbit-cage/lib/runtime_root.py", "stdin": "none", "stdout": "none", "exit": "n/a (importable module)", "note": "canonical single-.rabbit runtime-root resolver (spec Inv 52); imported by session-start-dispatcher.py's mode-marker reconciliation"},
      {"path": ".claude/features/rabbit-cage/scripts/show-mode.py", "stdin": "none", "stdout": "single-line JSON {mode,rabbit_root,project_root,feature_dir,evidence} + one human `Mode: …` summary line", "exit": "0=ok (both modes and the rabbit-meta-unavailable degenerate case)", "note": "deterministic plugin/standalone mode reporter; delegates detection to rabbit-meta.lib.mode_detection.detect_mode (spec Inv 45); runs from source (no deployed copy)"}
    ],
    "schemas": [],
    "templates": [],
    "skills": [],
    "functions": [
      {"path": ".claude/features/rabbit-cage/install.py", "function": "check_install_sources_exist", "signature": "check_install_sources_exist(repo_root) -> list[str]", "purpose": "install-closure integrity check: returns the closure source paths absent under repo_root (empty list = closure intact). Imported by the cross-feature contract gate so a surface retirement in ANY feature is screened against the install closure, not only when rabbit-cage is touched"}
    ]
  },
  "reads": {
    "files": [
      ".claude/features/*/feature.json",
      ".claude/features/policy/*.md",
      ".rabbit-scope-active",
      ".rabbit-scope-active-*",
      ".rabbit-scope-override",
      ".rabbit-scope-override-used",
      ".rabbit-skills-updated",
      ".rabbit/.runtime/mode",
      ".rabbit/.runtime/scope-active-*",
      ".rabbit/.runtime/scope-bypass-once",
      ".rabbit/.runtime/decompose-active",
      ".rabbit/rabbit-project/project-map.json",
      ".rabbit/agent-sentinel-bypass"
    ],
    "external": ["env-var:RABBIT_ROOT", "env-var:RABBIT_REFRESH_EVERY", "git-tags:vX.Y.Z (install.py post-update changelog summary; read-only `git -C <src_root> tag` over the live release track, spec Inv 46)"]
  },
  "invokes": {
    "modules": [
      {"path": ".claude/features/contract/lib/publish.py", "purpose": "install-time MANIFEST API calls"},
      {"path": ".claude/features/contract/lib/runtime.py", "purpose": "per-event RUNTIME API calls"},
      {"path": ".claude/features/contract/lib/producers.py", "purpose": "content producers invoked by publish_generated and check_drift_regenerate"},
      {"path": ".claude/features/contract/scripts/rabbit_print.py", "purpose": "dispatcher output rendering (rabbit_subline, rabbit_block)"},
      {"path": ".claude/features/contract/lib/config_dispatch.py", "purpose": "scripts/rabbit-cage-config.py delegates validation + mutation + restart-prompt rendering to dispatch_config (spec Inv 40)"}
    ],
    "scripts": [
      {"path": ".claude/features/contract/scripts/find-feature.py", "purpose": "scope-guard.py feature-name -> path resolution"},
      {"path": ".claude/features/rabbit-auto-evolve/scripts/check-auto-resume.py", "purpose": "session-start-dispatcher.py mechanical restart-resume detection; surfaces resume banner + action when resume:true (Inv 33 / rabbit-auto-evolve Inv 29)"},
      {"path": ".claude/features/rabbit-auto-evolve/scripts/advise-restart.py", "purpose": "stop-dispatcher.py + session-start-dispatcher.py ADVISORY-restart surfacing: `status` reports {advised, reason?} consumed by both (Stop + SessionStart surface the line), `clear` invoked by SessionStart to consume the advisory after surfacing (Inv 37 / rabbit-auto-evolve Inv 52)"},
      {"path": ".claude/features/contract/scripts/check-release-update.py", "purpose": "scripts/rabbit-update.py check reuses read_version / fetch_upstream_version / resolve_repo_root / probe_self_update for the non-throttled current-vs-latest probe (Inv 35 / contract Inv 63)"}
    ],
    "functions": [
      {"path": ".claude/features/contract/lib/checks.py", "function": "validate_agent_prompt_sentinel", "purpose": "scope-guard.py Agent-tool sentinel validation (Inv 29 / contract Inv 66)"},
      {"path": ".claude/features/contract/lib/runtime.py", "function": "emit_stop_timestamp", "purpose": "universal Stop-event turn-end timestamp marker (Inv 30 / contract Inv 67)"},
      {"path": ".claude/features/rabbit-meta/lib/mode_detection.py", "function": "detect_mode", "purpose": "scripts/show-mode.py delegates plugin/standalone detection to the canonical resolver so the reporter always agrees with the rest of the system (Inv 45 / rabbit-meta Inv 1)"}
    ]
  },
  "manages": {
    "runtime_markers": [
      {"path": ".rabbit-scope-override", "writer": "human or Claude (after explicit in-conversation user approval)", "reader": "scope-guard.py, stop-dispatcher.py (via check_marker_alert)", "lifecycle": "human or Claude creates; scope-guard.py deletes on one-time consumption; persists for session mode", "gitignored": true},
      {"path": ".rabbit-scope-override-used", "writer": "scope-guard.py", "reader": "stop-dispatcher.py (via check_marker_consume_alert)", "lifecycle": "created by scope-guard.py on one-time consumption; consumed (deleted) by check_marker_consume_alert", "gitignored": true},
      {"path": ".rabbit/.runtime/scope-bypass-once", "writer": "human or Claude (after explicit in-conversation user approval)", "reader": "scope-guard.py", "lifecycle": "human or Claude creates via touch; scope-guard.py consumes (deletes) before evaluating any decision so failed edits cannot leave a persistent bypass", "gitignored": true},
      {"path": ".rabbit/.runtime/decompose-active", "writer": "decompose/batch orchestration (e.g. rabbit-decompose)", "reader": "scope-guard.py", "lifecycle": "orchestration writes the JSON marker {operation, features, expires?} BEFORE batch work and deletes it AFTER; scope-guard.py honors it ONLY while present + un-expired to ALLOW writes inside the named feature dirs; an optional ISO-8601 expires bounds an orphaned marker (spec Inv 47)", "gitignored": true}
    ]
  },
  "never": [
    "writes .claude/settings.local.json except via the rabbit-cage-owned /rabbit-cage-config command (spec Inv 40), which routes the write through contract.lib.mutation",
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
