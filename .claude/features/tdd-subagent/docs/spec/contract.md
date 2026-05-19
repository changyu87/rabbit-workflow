---
feature: tdd-subagent
version: 1.6.0
template_version: 2.0.0
---

# tdd-subagent — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "scripts": [
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-step.py",
        "stdin": "none",
        "stdout": "show/next/transitions=plain-text (parser-stable); transition=ANSI-colored '[rabbit] ━━━ ... ━━━' format (green on stdout for normal, red on stderr for FORCED/WARNING/ERROR)",
        "exit": "0=success, 1=denied/invalid, 2=bad invocation"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-drift-check.py",
        "stdin": "none",
        "stdout": "OK summary on consistent state",
        "exit": "0=ok, 1=drift, 2=bad invocation or missing files"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-context.py",
        "stdin": "none",
        "stdout": "JSON block (default) or formatted text (--text)",
        "exit": "0=success, 2=bad invocation"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py",
        "stdin": "none. Required flags: --scope <feature-name>, --spec <spec-path>. Optional: --impl-suggestion <path>, --linked-item <item-dir> + --item-type bug|backlog (primary item), --linked-items <feature>:<type>:<id>[,...] (secondary items), --human-approval-gate true|false (default true), --code-review-full-loop, --max-iterations N (default 3, min 1). Legacy bug-dispatch and backlog-dispatch positional flags have been removed; callers MUST use --linked-item / --linked-items.",
        "stdout": "per-feature full-TDD-cycle subagent prompt that runs spec-update → test-red → impl → test-green for ONE feature using .rabbit-scope-active-<feature-name> as scope marker (parallel-dispatch safe); after test-green the orchestrator closes the linked bug or marks the backlog item implemented using the impl commit SHA; the script itself does not call any agent",
        "exit": "0=success, 1=feature not found, 2=bad invocation (missing/invalid flag, malformed --linked-items triple, missing --spec file)"
      }
    ],
    "files": [],
    "schemas": [],
    "templates": [],
    "skills": []
  },
  "reads": {
    "files": [
      "<feature-dir>/feature.json (tdd_state field)",
      "<feature-dir>/test/run.py",
      ".claude/backlogs/<feature-name>/ (in-progress items, scanned at test-green)"
    ],
    "external": [
      "env-var:RABBIT_ROOT"
    ]
  },
  "invokes": {
    "scripts": [
      ".claude/features/contract/scripts/enforcement/ (all scripts at test-green)",
      ".claude/features/rabbit-cage/scripts/rabbit-project.py consolidate (when project-map.json present)",
      ".claude/features/rabbit-file/scripts/item-status.py (conditional: only on test-green, best-effort, replaces deleted backlog-item-status.py)"
    ],
    "agents": []
  },
  "never": [
    "modifies feature files directly outside tdd_state and updated fields",
    "skips enforcement scripts without explicit || true",
    "writes outside its scope directory"
  ]
}
```
