---
feature: rabbit-feature
version: 1.20.0
owner: rabbit-workflow team
deprecation_criterion: When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.
template_version: 2.0.0
---

# rabbit-feature — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.",
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/rabbit-feature/scripts/resolve-scope.py",
        "purpose": "Builds the Agent-dispatch prompt that maps a natural-language request to the list of rabbit features the request will modify. Emits the prompt to stdout for default-model Agent dispatch."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/format-feature-context.py",
        "purpose": "Reads find-feature.py list-json output from stdin and writes the formatted feature-context block to stdout. Consumed by resolve-scope.py."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/scaffold-feature.py",
        "purpose": "Feature-scaffolding script invoked by rabbit-feature-scaffold. Creates a conforming feature directory (feature.json, docs/spec/{spec,contract}.md, test/run.py) at any path."
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-touch/",
        "purpose": "Orchestration skill triggered on feature write/edit/delete/add. Authoritative source for the deployed .claude/skills/rabbit-feature-touch/SKILL.md via the feature.json manifest publish_skill API call."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scope/",
        "purpose": "General-purpose shared skill: resolves a natural-language request to the list of rabbit features whose files it will modify; emits a prompt for a default-model Agent dispatch."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-spec/",
        "purpose": "General-purpose spec-authoring skill: reads a feature's current spec, judges open vs specific request, invokes superpowers, updates the spec, and writes an impl-suggestion file for whoever invoked it."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scaffold/",
        "purpose": "Feature-scaffolding skill. Shells out to scaffold-feature.py to create a conforming feature dir, then validates via contract's validate-feature.py."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-audit/",
        "purpose": "Feature-audit skill. Validates a single feature or sweeps every feature directory via contract's validate-feature.py; returns structured per-feature pass/fail findings."
      }
    ]
  },
  "reads": {
    "files": [],
    "external": []
  },
  "invokes": {
    "scripts": [
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-step.py",
        "signature": "tdd-step.py {show|next|transitions|transition} <feature-dir> [<new-state>] [--force] [--spec-no-change-reason <reason>]",
        "exit": "0=success, 1=denied/invalid, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py",
        "signature": "dispatch-tdd-subagent.py --scope <feature-name> --spec <spec-path> [--impl-suggestion <path>] [--linked-item <item-dir> --item-type bug|backlog] [--linked-items <feature>:<type>:<id>[,...]] [--code-review-full-loop] [--max-iterations N]",
        "exit": "0=success, 1=feature not found, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      },
      {
        "path": ".claude/features/contract/scripts/find-feature.py",
        "signature": "find-feature.py <repo-root> list-json",
        "exit": "0=success, non-zero on invocation error",
        "lock": "test-scope-script-resolve-scope.py asserts resolve-scope.py invokes this script (Inv 18)"
      },
      {
        "path": ".claude/features/contract/scripts/validate-feature.py",
        "signature": "validate-feature.py <feature-dir>",
        "exit": "0=pass, 1=validation failure, 2=bad invocation",
        "lock": "test-audit-skill.py asserts rabbit-feature-audit invokes this script; test-new-skill.py asserts rabbit-feature-scaffold invokes this script (Inv 31, 33)"
      },
      {
        "path": ".claude/features/rabbit-spec/scripts/dispatch-spec-create.py",
        "signature": "dispatch-spec-create.py --feature-name <name> [--paths <glob1>,<glob2>,...]",
        "exit": "0=success, 1=invocation error, 2=build-prompt.py subprocess failure",
        "lock": "test-feature-new-plugin-mode.py asserts plugin-mode scaffold-feature.py prints this exact dispatch command to stdout (Inv 48); the command string is also referenced by name in scaffold-feature.py source so test-contract-md.py picks it up as a cross-feature reference."
      }
    ],
    "agents": []
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "modifies tdd-subagent spec, contract, feature.json, or scripts",
    "modifies workspace-structure.json"
  ]
}
```
