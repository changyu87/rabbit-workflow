---
feature: policy
version: 1.5.0
template_version: 2.0.0
---

# policy — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "files": [
      ".claude/features/policy/philosophy.md",
      ".claude/features/policy/spec-rules.md",
      ".claude/features/policy/coding-rules.md"
    ],
    "scripts": [],
    "schemas": [],
    "templates": []
  },
  "reads": {
    "files": [],
    "external": []
  },
  "invokes": {
    "scripts": [],
    "agents": []
  },
  "never": [
    "generates code",
    "modifies files in other features",
    "produces output directly to callers",
    "writes outside its scope directory"
  ]
}
```
