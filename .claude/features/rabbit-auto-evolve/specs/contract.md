---
feature: rabbit-auto-evolve
version: 0.15.0
template_version: 2.0.0
---

# rabbit-auto-evolve — Contract

```json
{
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [],
    "schemas": [],
    "templates": [],
    "skills": [{"name": "rabbit-auto-evolve", "version": "0.15.0"}]
  },
  "reads": {
    "files": [],
    "external": []
  },
  "invokes": {
    "scripts": [
      {
        "path": ".claude/features/rabbit-issue/scripts/item-status.py",
        "subcommand": "close",
        "rationale": "merge-prs.py explicitly closes issues referenced (Fixes/Closes/Resolves #N) by a PR merged to dev, since GitHub auto-close only fires for default-branch (main) merges (issue #392); the close passes --reason completed --commit-sha <merge-sha>, since item-status.py requires --commit-sha for a completed closure (issue #423)"
      },
      {
        "path": ".claude/features/rabbit-issue/scripts/file-item.py",
        "subcommand": "",
        "rationale": "the dispatch_shape == decomposition path (Inv 26 / issue #435) files N per-feature sub-issues for a very-large cross-feature item; filing a sub-issue is a contract INVOKE of rabbit-issue, NOT a cross-feature edit, so every write stays inside one feature's scope"
      }
    ],
    "agents": [],
    "files": [
      {
        "path": ".claude/features/contract/workspace-structure.json",
        "operation": "add-child-entry",
        "rationale": "register rabbit-auto-evolve under features.children (resolved Open Question 5)"
      },
      {
        "path": ".claude/features/contract/templates/prompts/rabbit-auto-evolve.txt",
        "operation": "create-passthrough-template",
        "rationale": "passthrough template matching the prompts declaration (resolved Open Question 5)"
      }
    ]
  },
  "manages": {
    "runtime_markers": [
      ".rabbit-auto-evolve-active",
      ".rabbit-auto-evolve-running",
      ".rabbit-auto-evolve-stop-requested",
      ".rabbit-auto-evolve-restart-needed",
      ".rabbit-auto-evolve-aborted"
    ]
  },
  "never": []
}
```
