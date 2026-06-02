---
feature: rabbit-auto-evolve
version: 0.6.0
template_version: 2.0.0
---

# rabbit-auto-evolve — Contract

```json
{
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [],
    "schemas": [],
    "templates": [],
    "skills": [{"name": "rabbit-auto-evolve", "version": "0.6.0"}]
  },
  "reads": {
    "files": [],
    "external": []
  },
  "invokes": {
    "scripts": [],
    "agents": [],
    "files": [
      {
        "path": ".claude/features/contract/workspace-structure.json",
        "operation": "add-child-entry",
        "rationale": "register rabbit-auto-evolve under features.children (resolved Open Question 5)"
      },
      {
        "path": ".claude/features/contract/templates/prompts/rabbit-auto-evolve.txt",
        "operation": "create-passthrough-template",
        "rationale": "passthrough template matching the prompts declaration (resolved Open Question 5)"
      }
    ]
  },
  "manages": {
    "runtime_markers": [
      ".rabbit-auto-evolve-active",
      ".rabbit-auto-evolve-running",
      ".rabbit-auto-evolve-stop-requested",
      ".rabbit-auto-evolve-restart-needed",
      ".rabbit-auto-evolve-aborted"
    ]
  },
  "never": []
}
```
