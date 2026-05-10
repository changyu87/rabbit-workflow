---
feature: tdd-state-machine
version: 1.0.0
template_version: 2.0.0
---

# tdd-state-machine — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "scripts": [
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-step.sh",
        "stdin": "none",
        "stdout": "current state (show), next state (next), allowed next states (transitions), or transition message",
        "exit": "0=success, 1=denied/invalid, 2=bad invocation"
      },
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-drift-check.sh",
        "stdin": "none",
        "stdout": "OK summary on consistent state",
        "exit": "0=ok, 1=drift, 2=bad invocation or missing files"
      },
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-context.sh",
        "stdin": "none",
        "stdout": "JSON block (default) or formatted text (--text)",
        "exit": "0=success, 2=bad invocation"
      }
    ],
    "files": [],
    "schemas": [],
    "templates": []
  },
  "reads": {
    "files": [
      "<feature-dir>/feature.json (tdd_state field)",
      "<feature-dir>/test/run.sh"
    ],
    "external": [
      "env-var:RABBIT_ROOT"
    ]
  },
  "invokes": {
    "scripts": [
      ".claude/features/contract/scripts/rebuild-registry.sh",
      ".claude/features/contract/scripts/enforcement/ (all scripts at test-green)",
      ".claude/features/rabbit-cage/scripts/rabbit-project.sh consolidate"
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
