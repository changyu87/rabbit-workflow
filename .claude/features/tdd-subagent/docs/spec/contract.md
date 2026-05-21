---
feature: tdd-subagent
version: 2.1.0
template_version: 2.1.0
owner: rabbit-workflow team
deprecation_criterion: When subagent dispatch is replaced by a different orchestration mechanism (e.g., direct rabbit-CLI orchestration without a dispatch-prompt assembler).
---

# tdd-subagent — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "When subagent dispatch is replaced by a different orchestration mechanism (e.g., direct rabbit-CLI orchestration without a dispatch-prompt assembler).",
  "provides": {
    "scripts": [
      {
        "path": ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py",
        "stdin": "none. Required flags: --scope <feature-name>, --spec <spec-path>. Optional: --impl-suggestion <path>, --linked-item <item-dir> + --item-type bug|backlog (primary item), --linked-items <feature>:<type>:<id>[,...] (secondary items), --human-approval-gate true|false (default true), --code-review-full-loop, --max-iterations N (default 3, min 1). Legacy bug-dispatch and backlog-dispatch positional flags have been removed; callers MUST use --linked-item / --linked-items.",
        "stdout": "per-feature full-TDD-cycle subagent prompt that runs spec-update → test-red → impl → test-green for ONE feature using .rabbit-scope-active-<feature-name> as scope marker (parallel-dispatch safe); after test-green the orchestrator closes the linked bug or marks the backlog item implemented using the impl commit SHA; the script itself does not call any agent",
        "exit": "0=success, 1=feature not found, 2=bad invocation (missing/invalid flag, malformed --linked-items triple, missing --spec file)"
      }
    ],
    "agents": [
      {
        "path": ".claude/features/tdd-subagent/agents/tdd-subagent.md",
        "description": "Named subagent dispatched by dispatch-tdd-subagent.py. Runs the 9-step TDD cycle (SPEC-READ, HUMAN-APPROVAL, LOCK, TEST-WRITE, TEST-RED, IMPLEMENT, CODE-REVIEW, TEST-GREEN, UNLOCK) for ONE feature."
      }
    ],
    "files": [],
    "schemas": [],
    "templates": [],
    "skills": []
  },
  "reads": {
    "files": [
      ".claude/features/tdd-state-machine/scripts/tdd-step.py",
      "<feature-dir>/feature.json (tdd_state field)",
      "<feature-dir>/test/run.py",
      "<feature-dir>/docs/spec/spec.md"
    ],
    "external": [
      "env-var:RABBIT_ROOT"
    ]
  },
  "invokes": {
    "scripts": [
      ".claude/features/rabbit-file/scripts/item-status.py (close primary --linked-item and each --linked-items entry after subagent reaches test-green)"
    ],
    "agents": [
      "tdd-subagent (the agent defined by this feature; dispatch is via the assembled prompt, not a direct API call)"
    ]
  },
  "manages": {
    "runtime_markers": [
      ".rabbit-scope-active-<feature-name> (per-feature scope marker — written at LOCK and removed at UNLOCK by the dispatched subagent, not by dispatch-tdd-subagent.py itself)"
    ]
  },
  "never": [
    "Modifies tdd-step.py — owned by tdd-state-machine.",
    "Vendors or copies state-machine scripts into this feature's scripts/ directory; the assembled prompt references them at their tdd-state-machine path.",
    "Owns deployment of any script into .claude/agents/ — that is build-contract.json's job.",
    "Writes outside the dispatched subagent's declared scope directory.",
    "Calls an agent directly; dispatch-tdd-subagent.py emits a prompt only."
  ]
}
```
