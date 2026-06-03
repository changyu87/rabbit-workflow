---
feature: rabbit-decompose
version: 0.2.0
template_version: 2.0.0
---

# rabbit-decompose — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "skills": [
      ".claude/features/rabbit-decompose/skills/rabbit-decompose/SKILL.md"
    ],
    "agents": [],
    "scripts": [],
    "files": [],
    "templates": [],
    "schemas": []
  },
  "reads": {
    "files": [
      ".rabbit/.runtime/mode",
      ".rabbit/rabbit-project/project-map.json"
    ],
    "external": ["user-supplied spec text or codebase root"]
  },
  "invokes": {
    "skills": [
      {
        "name": "rabbit-feature-scaffold",
        "purpose": "scaffold each accepted feature's directory; uses --batch form in plugin mode"
      },
      {
        "name": "rabbit-spec-create",
        "purpose": "seed the initial specs/spec.md body for each accepted feature"
      }
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-feature/scripts/scaffold-feature.py",
        "purpose": "called via --batch <file> in plugin mode to scaffold N features in one project-map.json mutation"
      }
    ]
  },
  "never": [
    "edits the user's source code",
    "writes files outside .claude/features/rabbit-decompose/ (the skill's deliverable is structured handoff to other skills, not direct file writes)",
    "scaffolds features without explicit in-conversation user approval of the proposed list"
  ]
}
```

## Tech Stack

Dispatcher-orchestrated; no scripting tech stack of its own in the MVP.
