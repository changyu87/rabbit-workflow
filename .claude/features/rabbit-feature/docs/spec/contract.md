---
feature: rabbit-feature
version: 1.0.0
owner: rabbit-workflow team
deprecation_criterion: When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.
template_version: 2.0.0
---

# rabbit-feature — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.",
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [],
    "schemas": [],
    "templates": [],
    "skills": [
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-touch/",
        "purpose": "rabbit-feature-touch orchestration skill — authoritative source for the deployed .claude/skills/rabbit-feature-touch/SKILL.md, populated via the build-contract.json copy-file entry (Inv 1)."
      }
    ]
  },
  "reads": {
    "files": [],
    "external": []
  },
  "invokes": {
    "scripts": [
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-step.py",
        "signature": "tdd-step.py {show|next|transitions|transition} <feature-dir> [<new-state>] [--force] [--spec-no-change-reason <reason>]",
        "exit": "0=success, 1=denied/invalid, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py",
        "signature": "dispatch-tdd-subagent.py --scope <feature-name> --spec <spec-path> [--impl-suggestion <path>] [--linked-item <item-dir> --item-type bug|backlog] [--linked-items <feature>:<type>:<id>[,...]] [--human-approval-gate true|false] [--code-review-full-loop] [--max-iterations N]",
        "exit": "0=success, 1=feature not found, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      }
    ],
    "agents": []
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "modifies tdd-subagent spec, contract, feature.json, or scripts",
    "modifies workspace-structure.json"
  ]
}
```
