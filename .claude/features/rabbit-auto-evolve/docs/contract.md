---
feature: rabbit-auto-evolve
version: 0.74.0
template_version: 2.0.0
---

# rabbit-auto-evolve — Contract

```json
{
  "provides": {
    "files": [
      {
        "path": ".rabbit/auto-evolve-tick-jitter.json",
        "schema_version": "1.0.0",
        "rationale": "the empirical CronCreate jitter offset (Inv 56), owned and persisted by rabbit-auto-evolve's tick-jitter.py from the recorded fire history in .rabbit/tick.log. Schema: {schema_version, observed_jitter_minutes (int >= 0), period_minutes, sample_count, cold_start (bool), computed_at, owner, deprecation_criterion}. Other features (the contract feature's Stop line) READ observed_jitter_minutes to render the exact-time next-tick ETA WITHOUT importing this feature"
      }
    ],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/tick-jitter.py",
        "subcommands": ["compute", "show"],
        "version": "1.0.0",
        "rationale": "Inv 56: computes the deterministic CronCreate jitter offset as the median of actual_fire_time - nearest_prior_cron_boundary over recent .rabbit/tick.log fires (cold-start fallback min(15, ceil(period*0.10)) when no history), and persists it to .rabbit/auto-evolve-tick-jitter.json. `show` emits the persisted/recomputed value as JSON on stdout; `compute` writes the artifact. The boundary-plus-offset value banner-status.py and the contract Stop line render"
      },
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/advise-restart.py",
        "subcommands": ["write", "status", "clear"],
        "version": "1.0.0",
        "rationale": "advisory-restart marker lifecycle (Inv 48). `status` emits {\"advised\": bool, \"reason\"?: str} on stdout (always exit 0) and `clear` removes the marker (idempotent); these are the INVOKE surfaces rabbit-cage's Stop/SessionStart dispatcher calls to surface and clear the advisory restart signal cross-feature. Distinct from the hard `.rabbit-auto-evolve-restart-needed` marker — advisory, never pauses the loop"
      },
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/record-decomposition.py",
        "subcommands": [],
        "version": "1.0.0",
        "rationale": "decomposition parent->children linkage recorder (Inv 53). The dispatcher invokes `record-decomposition.py <parent#> <child#>...` at decompose time to persist the machine-readable link under the state's `decomposition_parents` map. This is the INVOKE surface the SKILL.md decomposition path calls so the parent's children are enumerable deterministically (never from a prose table)"
      },
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/close-decomposed-parents.py",
        "subcommands": [],
        "version": "1.0.0",
        "rationale": "per-tick roll-up close of decomposed parents (Inv 53). Invoked by run-post-merge.py after the catch-up phase: for each tracked parent whose recorded children are ALL closed it closes the parent (`gh issue close --reason completed`) and drops its `decomposition_parents` key. Idempotent no-op when the map is empty or any child is still open"
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [{"name": "rabbit-auto-evolve", "version": "0.23.0"}]
  },
  "reads": {
    "files": [
      {
        "path": ".claude/scheduled_tasks.json",
        "operation": "read-heartbeat-cadence",
        "rationale": "banner-status.py reads the repo-root heartbeat registry (the tasks[] entry whose prompt references rabbit-auto-evolve) to compute the idle banner line's exact next-tick ETA (next cron boundary plus the Inv 56 observed jitter offset), mirroring contract Inv 55's cadence computation. Read-only of a repo-root runtime artifact; rabbit-auto-evolve already owns this file's lifecycle via install-cron.py / the CronCreate heartbeat"
      }
    ],
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
        "path": ".claude/features/rabbit-issue/scripts/_gh.py",
        "function": "ensure_labels|repo_slug",
        "rationale": "reconcile-labels.py (Inv 55) imports rabbit-issue/_gh.ensure_labels to idempotently bootstrap the sanctioned `in-progress` category label before stamping it, and _gh.repo_slug to resolve the target repo without a `git remote` shellout. This is a cross-scope INVOKE of rabbit-issue's gh helpers (the same _gh module fetch-queue.py / triage-issue.py already bridge to) — rabbit-auto-evolve never edits rabbit-issue"
      },
      {
        "path": ".claude/features/contract/lib/runtime.py",
        "function": "cleanup_old_prompts",
        "rationale": "prune-worktrees.py invokes contract.lib.runtime.cleanup_old_prompts(max_age_days=7, repo_root=...) at tick start (pre-dispatch) to bound .rabbit/prompts/ (Inv 49). This is a cross-scope INVOKE of the contract-owned cleanup API — rabbit-auto-evolve never edits the contract feature"
      },
      {
        "path": ".claude/features/contract/lib/publish.py",
        "function": "publish_skill|publish_hook|publish_file|publish_command|publish_*",
        "rationale": "republish-feature.py reads a feature's feature.json manifest and invokes contract.lib.publish.<api>(**args, feature_dir=..., repo_root=...) for every publish_* entry to refresh the deployed copies a version-bumping subagent cannot write (out-of-scope), so test-deployed-skills-match-source.py is green in the PR (Inv 50). This is a cross-scope INVOKE of the contract-owned publish API — rabbit-auto-evolve never edits the contract feature"
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
