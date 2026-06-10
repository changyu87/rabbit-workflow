---
feature: contract
version: 2.48.0
template_version: 2.0.0
---

# contract — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "templates": [
      ".claude/features/contract/templates/spec-template.md",
      ".claude/features/contract/templates/contract-template.md",
      ".claude/features/contract/templates/bug-template.json",
      ".claude/features/contract/templates/triage-template.md",
      ".claude/features/contract/templates/feature-json-template.json",
      ".claude/features/contract/templates/project-map-template.json",
      ".claude/features/contract/templates/registry-template.json",
      ".claude/features/contract/templates/skill-template.md",
      ".claude/features/contract/templates/command-template.md"
    ],
    "schemas": [
      ".claude/features/contract/schemas/feature.json.schema.json",
      ".claude/features/contract/schemas/bug.json.schema.json",
      ".claude/features/contract/schemas/project-map.json.schema.json",
      ".claude/features/contract/schemas/rabbit-print.schema.json",
      ".claude/features/contract/schemas/prompts.schema.json",
      ".claude/features/contract/schemas/configuration.schema.json"
    ],
    "declarations": [
      ".claude/features/contract/workspace-structure.json"
    ],
    "scripts": [
      ".claude/features/contract/scripts/policy-block.py",
      ".claude/features/contract/scripts/build-prompt.py",
      ".claude/features/contract/scripts/check-release-update.py",
      ".claude/features/contract/scripts/validate-feature.py",
      ".claude/features/contract/scripts/validate-meta-contract.py",
      ".claude/features/contract/scripts/find-feature.py",
      ".claude/features/contract/scripts/reflow-invariants.py",
      ".claude/features/contract/scripts/rabbit_print.py",
      ".claude/features/contract/scripts/enforcement/check-imports-resolve.py",
      ".claude/features/contract/scripts/enforcement/check-naming.py",
      ".claude/features/contract/scripts/enforcement/check-sentinel.py",
      ".claude/features/contract/scripts/enforcement/check-symlinks-resolve.py",
      ".claude/features/contract/scripts/enforcement/check-template-schema-producer-consistency.py",
      ".claude/features/contract/scripts/enforcement/check-tests-non-interactive.py",
      ".claude/features/contract/scripts/enforcement/check-numbered-lists.py",
      ".claude/features/contract/scripts/enforcement/check-invariant-monotonic-order.py",
      ".claude/features/contract/scripts/enforcement/check-prompts-section.py"
    ],
    "lib": [
      ".claude/features/contract/lib/__init__.py",
      ".claude/features/contract/lib/checks.py",
      ".claude/features/contract/lib/publish.py",
      ".claude/features/contract/lib/policy_block.py",
      ".claude/features/contract/lib/mutation.py",
      ".claude/features/contract/lib/config_dispatch.py",
      ".claude/features/contract/lib/feature_suites.py"
    ],
    "hooks": [],
    "skills": [],
    "functions": [
      "contract.lib.checks.validate_agent_prompt_sentinel",
      "contract.lib.runtime.emit_stop_timestamp",
      "contract.lib.config_dispatch.dispatch_config"
    ]
  },
  "reads": {
    "files": [
      ".claude/features/contract/feature.json",
      ".claude/features/contract/templates/*",
      ".claude/features/contract/schemas/*",
      ".rabbit-auto-evolve-active",
      ".rabbit-auto-evolve-aborted",
      ".rabbit-auto-evolve-restart-needed",
      ".rabbit-auto-evolve-stop-requested",
      ".rabbit-auto-evolve-running",
      ".rabbit/auto-evolve-state.json",
      ".claude/scheduled_tasks.json",
      ".rabbit/auto-evolve-tick-jitter.json"
    ],
    "external": [
      "env-var:RABBIT_ROOT",
      "env-var:CLAUDE_PROJECT_DIR"
    ]
  },
  "invokes": {
    "scripts": [
      ".claude/features/rabbit-auto-evolve/scripts/banner-status.py",
      ".claude/features/rabbit-cage/install.py",
      ".claude/features/rabbit-cage/lib/runtime_root.py",
      ".claude/features/*/test/run.py"
    ],
    "agents": []
  },
  "never": [
    "edits another feature's directory",
    "writes outside .claude/features/contract/",
    "modifies another feature's feature.json, specs, tests, or implementation files"
  ]
}
```
