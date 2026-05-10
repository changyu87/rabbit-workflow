---
feature: rabbit-cage
version: 2.0.0
template_version: 2.0.0
---

# rabbit-cage — Contract

```json
{
  "provides": {
    "files": [".claude/agents", ".claude/commands", ".claude/hooks", ".claude/skills", ".claude/settings.json", ".claude/policy", ".claude/contract", "CLAUDE.md", "README.md", "install.sh"],
    "scripts": [
      {"path": ".claude/features/rabbit-cage/scripts/file-bug.sh", "stdin": "none", "stdout": "bug dir path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/bug-status.sh", "stdin": "none", "stdout": "status", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/list-bugs.sh", "stdin": "none", "stdout": "bug list", "exit": "0=ok"},
      {"path": ".claude/features/rabbit-cage/scripts/new-feature.sh", "stdin": "none", "stdout": "scaffold path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/validate-all.sh", "stdin": "none", "stdout": "validation report", "exit": "0=all pass 1=failures"},
      {"path": ".claude/features/rabbit-cage/scripts/rabbit-project.sh", "stdin": "none", "stdout": "operation result", "exit": "0=ok 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/file-backlog-item.sh", "stdin": "none", "stdout": "item dir path", "exit": "0=created 1=error 2=usage"},
      {"path": ".claude/features/rabbit-cage/scripts/backlog-item-status.sh", "stdin": "none", "stdout": "status", "exit": "0=ok 1=error 2=usage"}
    ],
    "schemas": [{"name": "backlog-item", "path": "docs/backlog/backlog-contract.md", "version": "1.0.0"}],
    "templates": [],
    "skills": [{"name": "rabbit-feature-touch", "path": ".claude/features/rabbit-cage/skills/rabbit-feature-touch/SKILL.md", "purpose": "orchestrates TDD state transitions in main session around every feature dispatch"}]
  },
  "reads": {
    "files": [".claude/features/registry.json", "project-*/project-map.json", ".claude/features/contract/templates/"],
    "external": ["env-var:RABBIT_ROOT", "env-var:BUG_ROOT"]
  },
  "invokes": {
    "scripts": [
      ".claude/features/contract/scripts/relink.sh",
      {"path": ".claude/features/contract/scripts/dispatch-feature-edit.sh", "stdin": "feature-name task-description", "stdout": "agent prompt", "exit": "0=ok 1=not-found 2=usage"}
    ],
    "agents":   []
  },
  "never": [
    "writes .claude/settings.local.json",
    "modifies files inside another feature's directory",
    "writes outside its declared scope without an active scope marker"
  ]
}
```

## Skill–Template Boundary

The `rabbit-feature-touch` skill and the `subagent-launch-template` are complementary, not redundant:

- **Skill** (main session) — controls *when* dispatches happen and *which leg* (test-only vs impl-only); calls `tdd-step.sh` at each boundary to advance the formal TDD state machine.
- **Template** (subagent payload) — provides the policy block (R6), scope declaration, and feature context for each dispatch leg. Subagents do not call `tdd-step.sh`; the main session orchestrates all state transitions via the skill.

This division is intentional: retiring the template would remove R6 compliance and scope-guard support; retiring the skill would leave TDD state machine advancement ungoverned.
