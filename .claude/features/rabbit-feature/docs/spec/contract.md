---
feature: rabbit-feature
version: 1.4.0
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
        "purpose": "Absorbed from rabbit-feature-scope (Inv 15-19). Builds the prompt that maps a natural-language request to the list of rabbit features the request will modify; emits prompt to stdout for default-model Agent dispatch."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/format-feature-context.py",
        "purpose": "Absorbed from rabbit-feature-scope (Inv 20, 23). Reads find-feature.py list-json output from stdin and writes the formatted feature-context block to stdout."
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-touch/",
        "purpose": "rabbit-feature-touch orchestration skill — authoritative source for the deployed .claude/skills/rabbit-feature-touch/SKILL.md, populated via the build-contract.json copy-file entry (Inv 1)."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scope/",
        "purpose": "Absorbed from rabbit-feature-scope (Inv 21-22). General-purpose shared skill: resolves a natural-language request to the list of rabbit features whose files it will modify; emits a prompt for a default-model Agent dispatch."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-spec/",
        "purpose": "Absorbed from rabbit-spec, renamed to rabbit-feature-spec (Inv 25-32). General-purpose spec-authoring skill: reads a feature's current spec, judges open vs specific request, invokes superpowers, updates spec, and writes an impl-suggestion file for whoever invoked it."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-new/",
        "purpose": "Feature-scaffolding skill (Inv 33). Given a feature name, shells out to rabbit-cage's new-feature.py to scaffold a conforming feature dir, then validates via contract.lib.checks.validate_feature. Cross-feature shell-out to rabbit-cage is temporary (RABBIT-CAGE-BACKLOG-24)."
      }
    ]
  },
  "reads": {
    "files": [
      ".claude/features/contract/build-contract.json"
    ],
    "external": []
  },
  "invokes": {
    "scripts": [
      {
        "path": ".claude/features/tdd-state-machine/scripts/tdd-step.py",
        "signature": "tdd-step.py {show|next|transitions|transition} <feature-dir> [<new-state>] [--force] [--spec-no-change-reason <reason>]",
        "exit": "0=success, 1=denied/invalid, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py",
        "signature": "dispatch-tdd-subagent.py --scope <feature-name> --spec <spec-path> [--impl-suggestion <path>] [--linked-item <item-dir> --item-type bug|backlog] [--linked-items <feature>:<type>:<id>[,...]] [--human-approval-gate true|false] [--code-review-full-loop] [--max-iterations N]",
        "exit": "0=success, 1=feature not found, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
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
