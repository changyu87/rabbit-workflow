---
feature: tdd-state-machine
version: 1.2.0
template_version: 2.0.0
owner: rabbit team
deprecation_criterion: when TDD state machine is replaced by a fundamentally different orchestration approach
---

# tdd-state-machine — Contract

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit team",
  "deprecation_criterion": "when TDD state machine is replaced by a fundamentally different orchestration approach",
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-step.py",
        "description": "Forward-only TDD state machine: show | next | transitions | transition. Honours _FORWARD_ALT branch test-green -> spec-update. stdout uses the centralized [🐇 rabbit 🐇] brand with ANSI green for accepted transitions; stderr uses ANSI red for forced/denied transitions."
      },
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-context.py",
        "description": "Emits machine-first JSON describing a feature's current TDD state, allowed_next_states, guidance text, deprecation_criterion, and contract; --text flag emits human-readable view."
      },
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-drift-check.py",
        "description": "Verifies a feature's claimed tdd_state matches reality by running test/run.py. Exit 0 ok; 1 drift; 2 invocation error."
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": []
  },
  "reads": {
    "files": [
      "<feature-dir>/feature.json",
      "<feature-dir>/test/run.py",
      "<feature-dir>/docs/spec/spec.md",
      ".claude/features/contract/scripts/rabbit_print.py",
      ".claude/features/contract/lib/checks.py",
      ".claude/features/contract/templates/bug-template.json",
      ".claude/features/rabbit-cage/scripts/rabbit-project.py",
      "<project-dir>/project-map.json"
    ],
    "external": []
  },
  "invokes": {
    "scripts": [
      "<feature-dir>/test/run.py",
      ".claude/features/rabbit-cage/scripts/rabbit-project.py"
    ],
    "agents": []
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "Modify any file outside the feature-dir passed on the command line.",
    "Allow backward transitions without --force.",
    "Allow any transition out of the deprecated terminal state.",
    "Own deployment of the scripts into .claude/agents/ (that is build-contract.json's job)."
  ]
}
```
