---
feature: rabbit-cage
version: 2.0.0
template_version: 2.0.0
---

# rabbit-cage — Contract

```json
{
  "provides": {
    "files": [".claude/agents", ".claude/commands", ".claude/hooks", ".claude/skills", ".claude/settings.json", ".claude/policy", ".claude/contract", "CLAUDE.md", "README.md", "install.sh"],
    "scripts": [
      {"path": ".claude/features/rabbit-cage/scripts/file-bug.sh", "stdin": "none", "stdout": "bug dir path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/bug-status.sh", "stdin": "none", "stdout": "status", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/list-bugs.sh", "stdin": "none", "stdout": "bug list", "exit": "0=ok"},
      {"path": ".claude/features/rabbit-cage/scripts/new-feature.sh", "stdin": "none", "stdout": "scaffold path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/validate-all.sh", "stdin": "none", "stdout": "validation report", "exit": "0=all pass 1=failures"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project.sh", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error 2=usage"}
    ],
    "schemas": [],
    "templates": []
  },
  "reads": {
    "files": [".claude/features/registry.json", "project-*/project-map.json", ".claude/features/contract/templates/"],
    "external": ["env-var:RABBIT_ROOT", "env-var:BUG_ROOT"]
  },
  "invokes": {
    "scripts": [".claude/features/contract/scripts/relink.sh"],
    "agents":   []
  },
  "never": [
    "writes .claude/settings.local.json",
    "modifies files inside another feature's directory",
    "writes outside its declared scope without an active scope marker"
  ]
}
```
