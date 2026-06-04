---
feature: rabbit-auto-evolve
version: 0.48.5
template_version: 2.0.0
---

# rabbit-auto-evolve — Contract

```json
{
  "provides": {
    "files": [],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/advise-restart.py",
        "subcommands": ["write", "status", "clear"],
        "version": "1.0.0",
        "rationale": "advisory-restart marker lifecycle (Inv 52). `status` emits {\"advised\": bool, \"reason\"?: str} on stdout (always exit 0) and `clear` removes the marker (idempotent); these are the INVOKE surfaces rabbit-cage's Stop/SessionStart dispatcher calls to surface and clear the advisory restart signal cross-feature. Distinct from the hard `.rabbit-auto-evolve-restart-needed` marker — advisory, never pauses the loop"
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [{"name": "rabbit-auto-evolve", "version": "0.23.0"}]
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
        "rationale": "merge-prs.py explicitly closes issues referenced (Fixes/Closes/Resolves) by a PR merged to dev, since GitHub auto-close only fires for default-branch (main) merges; the close passes --reason completed --commit-sha <merge-sha>, since item-status.py requires --commit-sha for a completed closure"
      },
      {
        "path": ".claude/features/rabbit-issue/scripts/file-item.py",
        "subcommand": "",
        "rationale": "the dispatch_shape == decomposition path (Inv 26) files N per-feature sub-issues for a very-large cross-feature item; filing a sub-issue is a contract INVOKE of rabbit-issue, NOT a cross-feature edit, so every write stays inside one feature's scope"
      }
    ],
    "agents": [],
    "modules": [
      {
        "path": ".claude/features/contract/lib/runtime.py",
        "function": "cleanup_old_prompts",
        "rationale": "prune-worktrees.py invokes contract.lib.runtime.cleanup_old_prompts(max_age_days=7, repo_root=...) at tick start (pre-dispatch) to bound .rabbit/prompts/ (Inv 53). This is a cross-scope INVOKE of the contract-owned cleanup API — rabbit-auto-evolve never edits the contract feature"
      },
      {
        "path": ".claude/features/contract/lib/publish.py",
        "function": "publish_skill|publish_hook|publish_file|publish_command|publish_*",
        "rationale": "republish-feature.py reads a feature's feature.json manifest and invokes contract.lib.publish.<api>(**args, feature_dir=..., repo_root=...) for every publish_* entry to refresh the deployed copies a version-bumping subagent cannot write (out-of-scope), so test-deployed-skills-match-source.py is green in the PR (Inv 55). This is a cross-scope INVOKE of the contract-owned publish API — rabbit-auto-evolve never edits the contract feature"
      }
    ],
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
      ".rabbit-auto-evolve-aborted",
      ".rabbit-auto-evolve-restart-advised"
    ]
  },
  "never": []
}
```
