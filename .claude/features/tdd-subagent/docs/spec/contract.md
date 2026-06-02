---
feature: tdd-subagent
version: 5.6.0
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
        "stdin": "none. Required flags: --scope <feature-name>, --spec <spec-path>. Optional: --impl-suggestion <path>, --code-review-full-loop, --max-iterations N (default 3, min 1).",
        "stdout": "assembled per-feature TDD-cycle prompt with the 8 labelled steps (LOCK, TEST-WRITE, TEST-RED, IMPLEMENT, SYNC-DEPLOYED, CODE-REVIEW, TEST-GREEN, UNLOCK). The script never invokes any agent; callers dispatch the agent with this prompt.",
        "exit": "0=success, 2=invocation error (missing/invalid flag, missing --spec file, unknown --scope feature)"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-step.py",
        "description": "Forward-only TDD state machine: show | next | transitions | transition. Honours _FORWARD_ALT branch test-green -> spec-update. stdout uses the centralized [🐇 rabbit 🐇] brand with ANSI green for accepted transitions; stderr uses ANSI red for forced/denied transitions."
      }
    ],
    "agents": [
      {
        "path": ".claude/features/tdd-subagent/agents/tdd-subagent.md",
        "description": "Named subagent dispatched by callers using the prompt assembled by dispatch-tdd-subagent.py. Runs the 8-step TDD cycle for ONE feature."
      }
    ],
    "files": [],
    "schemas": [],
    "templates": [],
    "skills": []
  },
  "reads": {
    "files": [
      ".claude/features/contract/scripts/rabbit_print.py",
      "<feature-dir>/feature.json",
      "<feature-dir>/docs/spec/spec.md",
      "<repo_root>/.rabbit-human-approval-bypass (presence check)"
    ],
    "external": [
      "env-var:RABBIT_ROOT"
    ]
  },
  "invokes": {
    "scripts": [
      ".claude/features/contract/scripts/find-feature.py (resolve --scope to feature directory)",
      ".claude/features/contract/scripts/policy-block.py (embed policy block in preamble)"
    ],
    "agents": []
  },
  "manages": {
    "runtime_markers": [
      ".rabbit-scope-active-<feature-name> (per-feature; written at LOCK and removed at UNLOCK by the dispatched subagent, not by dispatch-tdd-subagent.py)"
    ]
  },
  "never": [
    "Owns deployment of any script into .claude/agents/ — that is the contract feature's responsibility.",
    "Writes outside the dispatched subagent's declared scope directory.",
    "Calls an agent directly; dispatch-tdd-subagent.py emits a prompt only.",
    "Emits the bypass-marker preamble note via inline ANSI/brand strings (rabbit_print from contract.scripts.rabbit_print is the sole authorized emission path)."
  ]
}
```
