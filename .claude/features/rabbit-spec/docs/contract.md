---
feature: rabbit-spec
version: 1.18.0
template_version: 2.0.0
---

# rabbit-spec — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "skills": [
      ".claude/features/rabbit-spec/skills/rabbit-spec-update/SKILL.md"
    ],
    "agents": [
      {
        "path": ".claude/features/rabbit-spec/agents/rabbit-spec-creator.md",
        "subagent_type": "rabbit-spec-creator",
        "tools": "Read, Grep, Glob, Write, Explore",
        "writes": ".claude/features/<feature-name>/docs/spec.md (or the plugin-mode feature root) — its SOLE write target",
        "handoff": "{path_written, summary} — JSON object; never the full spec body",
        "note": "drafts AND writes a newly-declared feature's initial docs/spec.md; dispatch directly after assembling the prompt with scripts/dispatch-spec-creator.py"
      }
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-spec/scripts/dispatch-spec-creator.py",
        "stdin": "none",
        "args": "--feature-name <name> [--paths <glob1>,<glob2>,...]",
        "stdout": "absolute path to the assembled prompt file (single line)",
        "stderr": "structured NOTE naming the dropped-file count when the resolved file count exceeds the 50-file cap (never a silent truncation); empty when count <= cap",
        "exit": "0=ok 1=invocation-error 2=assembler-failure",
        "note": "input assembler for the rabbit-spec-creator subagent prompt; invokes contract/scripts/build-prompt.py. The orchestrator runs this, then dispatches rabbit-spec-creator directly."
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
        "purpose": "drafts AND writes a newly-declared feature's initial docs/spec.md from feature name + optional code globs; returns a {path_written, summary} handoff"
      }
    ]
  },
  "never": [
    "introduces a surface artifact without first updating spec.md",
    "modifies another feature's files",
    "writes any file outside .claude/features/rabbit-spec/ except the target feature's canonical flat docs/spec.md (the rabbit-spec-creator subagent's deliverable)",
    "grants the rabbit-spec-creator agent any tool beyond Read, Grep, Glob, Write, Explore",
    "lets the rabbit-spec-creator subagent write any file other than the target feature's docs/spec.md"
  ]
}
```
