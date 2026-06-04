---
feature: rabbit-housekeep
version: 0.1.0
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
      ".claude/features/rabbit-housekeep/scripts/measure-reduction.py"
    ],
    "agents": [],
    "files": [],
    "templates": [],
    "schemas": [],
    "commands": []
  },
  "reads": {
    "files": [
      ".claude/features/policy/coding-rules.md"
    ],
    "external": ["user-supplied housekeeping target: a feature, a set of features, or the repo root"]
  },
  "invokes": {
    "skills": [
      {
        "name": "rabbit-feature-touch",
        "purpose": "run each per-feature housekeeping unit through the governed TDD path; dispatches the tdd-subagent for the measured-reduction wave"
      }
    ],
    "agents": [
      {
        "name": "tdd-subagent",
        "purpose": "executes the per-feature reduction wave under the TDD cycle (consumed via rabbit-feature-touch; the housekeeping test pattern asserts measured reduction plus load-bearing-token survival)"
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
    "edits files outside the target feature's directory (cross-feature scope is decomposed into per-feature units, each scoped to its own feature)",
    "rewords doc surfaces without measured line removal (a reduction wave removes; the measure-reduction.py diff reduced verdict is the gate)",
    "deletes load-bearing tokens (script names, schema fields, exit codes, decision tables, cross-references) to inflate the line delta",
    "silently keeps an unverifiable claim (it is flagged as a housekeeping-tagged sub-issue, never silently retained)",
    "is invoked inside an Agent() call (it is a subagent-dispatching skill; doing so creates illegal two-level subagent nesting)"
  ]
}
```

The decomposition dispatch shape is reused from rabbit-decompose; the
parent->children linkage and roll-up close are owned by rabbit-auto-evolve.
rabbit-housekeep consumes these via the INVOKE relationships above and never
edits those features' files.
