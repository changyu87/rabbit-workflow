---
feature: rabbit-decompose
version: 0.7.1
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
    "scripts": [
      ".claude/features/rabbit-decompose/scripts/handoff-scaffold.py"
    ],
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
        "purpose": "seed the initial docs/spec.md body for each accepted feature"
      }
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-feature/scripts/scaffold-feature.py",
        "purpose": "called via --batch <file> in plugin mode to scaffold N features in one project-map.json mutation"
      },
      {
        "path": ".claude/features/rabbit-meta/lib/mode_detection.py",
        "purpose": "handoff-scaffold.py lazy-imports detect_mode(cwd) to resolve plugin-vs-standalone mode deterministically (for both the Step 1 decomposition source root and the Step 4 scaffolder dispatch) instead of reading a single hard-coded mode path"
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
