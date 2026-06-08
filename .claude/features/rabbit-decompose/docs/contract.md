---
feature: rabbit-decompose
version: 0.15.0
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
    "files": [
      {
        "path": ".rabbit/.runtime/decompose-active",
        "purpose": "the decompose-context scope-guard pass-through marker; handoff-scaffold.py --decompose-context set writes it (operation + the accepted feature NAMES) before the batch scaffold/spec-seed work and --decompose-context clear deletes it after, authorizing cross-feature writes for the named features without a per-feature scope marker (rabbit-cage scope-guard Inv 47 contract)"
      }
    ],
    "templates": [],
    "schemas": []
  },
  "reads": {
    "files": [
      ".rabbit/rabbit-project/project-map.json"
    ],
    "external": ["user-supplied spec text or codebase root"]
  },
  "invokes": {
    "skills": [
      {
        "name": "rabbit-feature-scaffold",
        "purpose": "scaffold each accepted feature's directory; plugin mode dispatches the skill's batch interface (scaffold-batch.py --batch), per-feature in standalone mode"
      }
    ],
    "agents": [
      {
        "subagent_type": "rabbit-spec-creator",
        "purpose": "seed each accepted feature's initial docs/spec.md; dispatched DIRECTLY at level-1 (Step 4-B) with a prompt assembled by rabbit-spec's dispatch-spec-creator.py; the subagent writes the spec itself and returns a {path_written, summary} handoff"
      }
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-spec/scripts/dispatch-spec-creator.py",
        "purpose": "rabbit-spec's input assembler for the rabbit-spec-creator subagent; Step 4-B runs it per accepted feature (--feature-name <name>, plus --paths <globs> or none for a greenfield skeleton) to print the assembled prompt-file path, then dispatches the subagent directly"
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scaffold/scripts/scaffold-batch.py",
        "purpose": "the rabbit-feature-scaffold skill's batch interface; handoff-scaffold.py invokes it via --batch <file> in plugin mode to scaffold N features in one project-map.json mutation (the declared skill interface, not a direct shell-out to scaffold-feature.py)"
      },
      {
        "path": ".claude/features/rabbit-meta/lib/mode_detection.py",
        "purpose": "handoff-scaffold.py lazy-imports detect_mode(cwd) to resolve plugin-vs-standalone mode deterministically (for the Step 1 decomposition source root, the existing-decomposition pre-check's project-map.json path, and the Step 4 scaffolder dispatch) instead of reading a single hard-coded mode path"
      }
    ]
  },
  "never": [
    "edits the user's source code",
    "writes feature-directory files directly (the skill's deliverable is structured handoff to other skills; its only direct write is the .rabbit/.runtime/decompose-active orchestration marker declared in provides.files)",
    "scaffolds features without explicit in-conversation user approval of the proposed list"
  ]
}
```
