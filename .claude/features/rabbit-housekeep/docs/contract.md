---
feature: rabbit-housekeep
version: 0.9.1
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when housekeeping is provided natively by the rabbit CLI as a first-class measured-reduction subcommand
status: active
---

# rabbit-housekeep — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "provides": {
    "skills": [
      ".claude/features/rabbit-housekeep/skills/rabbit-housekeep/SKILL.md"
    ],
    "scripts": [
      ".claude/features/rabbit-housekeep/scripts/measure-reduction.py",
      ".claude/features/rabbit-housekeep/scripts/check-script-backed.py",
      ".claude/features/rabbit-housekeep/scripts/resolve-housekeep-scope.py",
      ".claude/features/rabbit-housekeep/scripts/wave-automerge.py",
      ".claude/features/rabbit-housekeep/scripts/resolve-project-remote.py"
    ],
    "agents": [],
    "files": [],
    "templates": [],
    "schemas": [],
    "commands": [
      ".claude/features/rabbit-housekeep/commands/rabbit-housekeep.md"
    ]
  },
  "reads": {
    "files": [
      ".claude/features/policy/coding-rules.md",
      ".claude/features/policy/spec-rules.md"
    ],
    "external": ["user-supplied housekeeping target: a feature, a set of features, or the repo root"]
  },
  "invokes": {
    "skills": [
      {
        "name": "rabbit-feature-touch",
        "purpose": "run each per-feature housekeeping unit through the governed TDD path; dispatches the tdd-subagent for the measured-reduction wave"
      },
      {
        "name": "rabbit-decompose",
        "purpose": "reuse the decomposition shape (one bounded per-feature unit each) when splitting cross-feature / repo-wide housekeeping scope into per-feature sub-issues in Step 2 of the skill"
      }
    ],
    "agents": [
      {
        "name": "tdd-subagent",
        "purpose": "executes the per-feature reduction wave under the TDD cycle (consumed via rabbit-feature-touch; the housekeeping test pattern asserts the behavior-preserved gate plus load-bearing-token survival)"
      },
      {
        "name": "code-simplifier",
        "purpose": "in-environment agent that simplifies and refines a target feature's src/ for clarity, consistency, and maintainability while preserving all functionality; the SIMPLIFY step of the opt-in code dimension (--code), run through the governed TDD path with the existing test suite as the zero-behavior-loss gate"
      }
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-issue/scripts/file-item.py",
        "purpose": "file one housekeeping-tagged per-feature sub-issue per decomposed unit, and file flagged-unverifiable items as housekeeping-tagged sub-issues"
      },
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/record-decomposition.py",
        "purpose": "record the parent->children linkage for a decomposed housekeeping mandate so the parent closes deterministically"
      },
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/close-decomposed-parents.py",
        "purpose": "close a decomposed housekeeping parent once all per-feature children close (parent-close machinery owned by rabbit-auto-evolve, reused here)"
      }
    ]
  },
  "manages": {
    "runtime_markers": []
  },
  "never": [
    "edits files outside the target feature's directory (doc dimension) or outside the target feature's src/ (code dimension)",
    "rewords doc surfaces or code to manufacture a diff (reduction is REPORTED not MANDATED; an already-clean target is an honest no-op SUCCESS; the MANDATORY gate is behavior preserved with the existing test suite green)",
    "deletes load-bearing tokens (script names, schema fields, exit codes, decision tables, cross-references) to inflate the line delta",
    "silently keeps an unverifiable claim or applies a risky/cross-scope rewrite instead of flagging it as a housekeeping-tagged sub-issue",
    "is invoked inside an Agent() call (it is a subagent-dispatching skill; doing so creates illegal two-level subagent nesting)"
  ]
}
```

Human view: the cross-feature reuses above are declared in the `invokes`
block; this prose is derived from it, not a second source of truth.
