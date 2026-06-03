---
feature: rabbit-spec
version: 1.8.0
template_version: 2.0.0
---

# rabbit-spec — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "skills": [
      ".claude/features/rabbit-spec/skills/rabbit-spec-create/SKILL.md"
    ],
    "agents": [
      ".claude/features/rabbit-spec/agents/rabbit-spec-creator.md"
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-spec/scripts/dispatch-spec-create.py",
        "stdin": "none",
        "stdout": "absolute path to the assembled prompt file",
        "exit": "0=ok 1=invocation-error 2=assembler-failure",
        "note": "prompt assembler for the rabbit-spec-creator subagent; invokes contract/scripts/build-prompt.py"
      }
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
    "external": []
  },
  "invokes": {
    "scripts": [
      {
        "path": ".claude/features/contract/scripts/build-prompt.py",
        "purpose": "assemble the rabbit-spec-creator subagent prompt from the registered template + slot values"
      }
    ],
    "agents": [
      {
        "subagent_type": "rabbit-spec-creator",
        "purpose": "read-only spec drafting from feature name + optional code globs"
      }
    ]
  },
  "never": [
    "introduces a surface artifact without first updating spec.md",
    "modifies another feature's files",
    "writes any file outside .claude/features/rabbit-spec/ except the target feature's spec.md (resolved layout: flat docs/spec.md preferred, then specs/spec.md, then legacy docs/spec/spec.md — the skill's deliverable)",
    "grants the rabbit-spec-creator agent any tool beyond Read, Grep, Glob"
  ]
}
```

## Tech Stack

Python 3 stdlib only.
