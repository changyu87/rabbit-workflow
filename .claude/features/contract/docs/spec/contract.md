---
feature: contract
version: 1.2.0
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
      ".claude/features/contract/schemas/workspace-map.json.schema.json"
    ],
    "scripts": [
      ".claude/features/contract/scripts/policy-block.sh",
      ".claude/features/contract/scripts/dispatch-feature-edit.sh",
      ".claude/features/contract/scripts/rebuild-registry.sh",
      ".claude/features/contract/scripts/relink.sh",
      ".claude/features/contract/scripts/render-template.sh",
      ".claude/features/contract/scripts/check-maps-consistent.sh",
      ".claude/features/contract/scripts/rabbit-triage.sh",
      ".claude/features/contract/scripts/validate-feature.sh",
      ".claude/features/contract/scripts/workspace-map.sh",
      ".claude/features/contract/scripts/enforcement/check-imports-resolve.sh",
      ".claude/features/contract/scripts/enforcement/check-naming.sh",
      ".claude/features/contract/scripts/enforcement/check-no-main-edits.sh",
      ".claude/features/contract/scripts/enforcement/check-opus-for-planning-agents.sh",
      ".claude/features/contract/scripts/enforcement/check-sentinel.sh",
      ".claude/features/contract/scripts/enforcement/check-symlinks-resolve.sh",
      ".claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.sh",
      ".claude/features/contract/scripts/enforcement/check-tests-non-interactive.sh"
    ],
    "skills": [
      ".claude/skills/rabbit-workspace-map/SKILL.md"
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
