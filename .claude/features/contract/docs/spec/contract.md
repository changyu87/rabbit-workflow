---
feature: contract
version: 1.4.0
template_version: 2.0.0
---

# contract — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "templates": [
      ".claude/features/contract/templates/spec-template.md",
      ".claude/features/contract/templates/contract-template.md",
      ".claude/features/contract/templates/bug-template.json",
      ".claude/features/contract/templates/triage-template.md",
      ".claude/features/contract/templates/feature-json-template.json",
      ".claude/features/contract/templates/subagent-launch-template.txt",
      ".claude/features/contract/templates/project-map-template.json",
      ".claude/features/contract/templates/registry-template.json",
      ".claude/features/contract/templates/skill-template.md",
      ".claude/features/contract/templates/command-template.md"
    ],
    "schemas": [
      ".claude/features/contract/schemas/feature.json.schema.json",
      ".claude/features/contract/schemas/registry.json.schema.json",
      ".claude/features/contract/schemas/bug.json.schema.json",
      ".claude/features/contract/schemas/project-map.json.schema.json",
      ".claude/features/contract/schemas/rabbit-print.schema.json",
      ".claude/features/contract/schemas/rabbit-print-messages.json",
      ".claude/features/contract/schemas/workspace-map.json.schema.json",
      ".claude/features/contract/schemas/build-contract.schema.json"
    ],
    "data": [
      ".claude/features/contract/build-contract.json"
    ],
    "scripts": [
      ".claude/features/contract/scripts/policy-block.py",
      ".claude/features/contract/scripts/dispatch-feature-edit.py",
      ".claude/features/contract/scripts/dispatch-spec-update.py",
      ".claude/features/contract/scripts/render-template.py",
      ".claude/features/contract/scripts/check-maps-consistent.py",
      ".claude/features/contract/scripts/rabbit-triage.py",
      ".claude/features/contract/scripts/validate-feature.py",
      ".claude/features/contract/scripts/workspace-map.py",
      ".claude/features/contract/scripts/audit-orphan-storage.py",
      ".claude/features/contract/scripts/find-feature.py",
      ".claude/features/contract/scripts/rabbit_print.py",
      ".claude/features/contract/scripts/enforcement/check-imports-resolve.py",
      ".claude/features/contract/scripts/enforcement/check-naming.py",
      ".claude/features/contract/scripts/enforcement/check-no-main-edits.py",
      ".claude/features/contract/scripts/enforcement/check-opus-for-planning-agents.py",
      ".claude/features/contract/scripts/enforcement/check-sentinel.py",
      ".claude/features/contract/scripts/enforcement/check-symlinks-resolve.py",
      ".claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.py",
      ".claude/features/contract/scripts/enforcement/check-tests-non-interactive.py"
    ],
    "skills": [
      ".claude/features/contract/skills/rabbit-workspace-map/SKILL.md"
    ]
  },
  "reads": {
    "files": [
      ".claude/features/contract/feature.json",
      ".claude/features/contract/templates/*",
      ".claude/features/contract/schemas/*"
    ],
    "external": [
      "env-var:RABBIT_ROOT",
      "env-var:CLAUDE_PROJECT_DIR"
    ]
  },
  "invokes": {
    "scripts": [],
    "agents": []
  },
  "never": [
    "edits another feature's directory",
    "writes outside .claude/features/contract/",
    "modifies another feature's feature.json, specs, tests, or implementation files"
  ]
}
```
