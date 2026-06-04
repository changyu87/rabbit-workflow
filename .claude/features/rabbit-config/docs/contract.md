---
feature: rabbit-config
version: 1.8.0
template_version: 2.0.0
---

# rabbit-config — Contract

```json
{
  "provides": {
    "files": [
      ".claude/skills/rabbit-config/SKILL.md"
    ],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/rabbit-config/skills/rabbit-config/scripts/rabbit-config.py",
        "stdin": "none",
        "stdout": "mutation result messages (one line per CheckResult.message)",
        "exit": "0=ok 1=mutation-failed 1=unknown-subcommand 1=invalid-input",
        "note": "interpreter invoked by the rabbit-config skill; dispatches CONFIGURATION declarations to contract.lib.mutation"
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": ["rabbit-config"]
  },
  "reads": {
    "files": [
      ".claude/features/*/feature.json",
      ".claude/features/contract/workspace-structure.json"
    ],
    "external": []
  },
  "invokes": {
    "modules": [
      {
        "path": ".claude/features/contract/lib/mutation.py",
        "purpose": "dispatches values/actions API calls declared in CONFIGURATION entries"
      },
      {
        "path": ".claude/features/contract/lib/runtime.py",
        "purpose": "iterate_configurables_alerts and iterate_configurables_banner invoked by event dispatchers at Stop and SessionStart; rabbit-config pins the externally observable emission shape of these APIs"
      }
    ],
    "scripts": []
  },
  "never": [
    "modifies another feature's CONFIGURATION declarations",
    "adds new APIs to contract.lib.mutation",
    "writes any file except via declared contract.lib.mutation API calls",
    "owns a configurable of its own (CONFIGURATION is always empty)",
    "mutates the live workspace from a test case"
  ]
}
```

## Tech Stack

Python 3 stdlib only. Imports `contract.lib.mutation` at runtime.
No Bash runtime dependency.
