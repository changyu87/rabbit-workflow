---
feature: rabbit-auto-evolve
version: 0.100.2
template_version: 2.0.0
---

# rabbit-auto-evolve — Contract

```json
{
  "provides": {
    "files": [
      {
        "path": ".rabbit/auto-evolve-tick-jitter.json",
        "schema_version": "1.1.0",
        "rationale": "the empirical CronCreate jitter offset AND the actual next scheduled fire (Inv 56), owned and persisted by rabbit-auto-evolve's tick-jitter.py from the recorded fire history in .rabbit/tick.log and the dispatcher-injected CronList snapshot. Schema: {schema_version, observed_jitter_minutes (int >= 0), period_minutes, sample_count, cold_start (bool), next_fire_at (ISO-8601 UTC | null), computed_at, owner, deprecation_criterion}. Other features (the contract feature's Stop line) READ observed_jitter_minutes to render the boundary-plus-offset ETA, and next_fire_at (when non-null and future) to snap the ETA to the live schedule (the pending immediate-refire) rather than a stale heartbeat cron edge (#1154) — WITHOUT importing this feature"
      }
    ],
    "commands": [],
    "scripts": [
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/tick-jitter.py",
        "subcommands": ["compute", "show"],
        "version": "1.1.0",
        "rationale": "Inv 56: computes the deterministic CronCreate jitter offset as the median of actual_fire_time - nearest_prior_cron_boundary over recent .rabbit/tick.log fires (cold-start fallback min(15, ceil(period*0.10)) when no history), AND derives next_fire_at — the actual next scheduled CronCreate event (the earliest upcoming fire across the dispatcher-injected CronList snapshot, the pending immediate-refire plus the heartbeat; #1154) — persisting both to .rabbit/auto-evolve-tick-jitter.json. `show` emits the recomputed record as JSON on stdout; `compute` writes the artifact. The boundary-plus-offset value and the next_fire_at edge banner-status.py and the contract Stop line render"
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
        "rationale": "per-tick roll-up close of decomposed parents (Inv 53). Invoked by run-post-merge.py after the catch-up phase: for each tracked parent it reads the AUTHORITATIVE close-source, the GitHub-native sub-issue rollup (`gh api repos/{slug}/issues/<parent>` -> `sub_issues_summary{total, completed}`), and closes the parent (`gh issue close --reason completed`) when `total > 0 and completed == total`, dropping its `decomposition_parents` key. COEXISTENCE: a recorded parent with no native sub-issues yet (`total == 0`) falls back to the legacy hand-rolled per-child `gh issue view` check. `decomposition_parents` is a deprecating mirror honored during the coexistence window; its deprecation criterion is to drop the field and the legacy fallback once no open parent carries an entry. Idempotent no-op when the map is empty or the close-source shows the parent incomplete"
      },
      {
        "path": ".claude/features/rabbit-auto-evolve/scripts/resolve-duplicate.py",
        "subcommands": ["resolve", "status"],
        "version": "1.0.0",
        "rationale": "native-duplicate resolution recorder (Inv 60). `resolve <dup> <canonical>` records the AUTHORITATIVE GitHub-native duplicate state by closing the duplicate with `gh api --method PATCH repos/{slug}/issues/<dup> -f state=closed -f state_reason=duplicate` and posting one cross-reference comment naming the canonical issue, so the native duplicate relationship is visible. `status <n>` reports whether an issue is recognized as a duplicate, with the native `state_reason=duplicate` authoritative and the reinvented `duplicate` label honored only on read as a deprecating coexistence mirror. The DETECTION heuristic stays in triage-issue.py rule 3 (unchanged confidence gate); this script owns only RESOLUTION. The close is a terminal convergence (Inv 25), never a label-strip-while-open de-queue. Reuses the `gh api repos/{slug}/issues/...` access pattern Inv 53/58/59 use; deprecation criterion: drop the `duplicate` label read once no open or recently-closed issue carries the label and native `state_reason=duplicate` is the sole expressed duplicate marker"
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [{"name": "rabbit-auto-evolve", "version": "0.27.0"}]
  },
  "reads": {
    "files": [
      {
        "path": ".claude/scheduled_tasks.json",
        "operation": "read-heartbeat-cadence",
        "rationale": "banner-status.py reads the repo-root heartbeat registry (the tasks[] entry whose prompt references rabbit-auto-evolve) to compute the idle banner line's exact next-tick ETA (next cron boundary plus the Inv 56 observed jitter offset), mirroring contract Inv 55's cadence computation. Read-only of a repo-root runtime artifact; rabbit-auto-evolve already owns this file's lifecycle via install-cron.py / the CronCreate heartbeat"
      }
    ],
    "external": [
      {
        "name": "github-issue-dependencies",
        "operation": "read-blocked-by",
        "rationale": "triage-issue.py rule 5 (Inv 59) reads the AUTHORITATIVE source of an issue's blocked state from the GitHub-native dependencies graph (`gh api repos/{slug}/issues/<n>/dependencies/blocked_by` -> array of blocker issues each `{number, state, title}`); when any listed blocker is still `open` the issue defers `blocked`. The dispatch path that records a discovered blocker WRITES the relationship (`gh api --method POST repos/{slug}/issues/<n>/dependencies/blocked_by -F issue_id=<blocker-id>`). The body `blocked-by: #N` text declaration and the legacy `blocked-by:` label are a deprecating coexistence mirror, consulted only when the native source reports no open blocker; deprecation criterion: drop the body parser and label once no open issue carries a `blocked-by:` body marker or label and native dependencies are the sole expressed ordering source. Reuses the `gh api repos/{slug}/issues/...` access pattern the sub-issue rollup (Inv 53/58) already uses"
      },
      {
        "name": "github-issue-duplicate-state",
        "operation": "write-state-reason-duplicate",
        "rationale": "resolve-duplicate.py (Inv 60) records the AUTHORITATIVE GitHub-native duplicate resolution by closing the duplicate with `gh api --method PATCH repos/{slug}/issues/<dup> -f state=closed -f state_reason=duplicate` and posting one cross-reference comment naming the canonical issue. `status <n>` READS `gh issue view <n> --json state,stateReason,labels` to report whether an issue is a recognized duplicate: native `stateReason == duplicate` is authoritative, the reinvented `duplicate` label is honored only on read as a deprecating coexistence mirror. The DETECTION heuristic is unchanged (triage-issue.py rule 3); this is RESOLUTION only. Deprecation criterion: drop the `duplicate` label read once no open or recently-closed issue carries the label and native `state_reason=duplicate` is the sole expressed duplicate marker. Reuses the `gh api repos/{slug}/issues/...` access pattern Inv 53/58/59 already use"
      }
    ]
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
        "rationale": "the dispatch_shape == decomposition path (Inv 26/53) files N per-feature sub-issues for a very-large cross-feature item; each child is filed with `--parent <parent#>` so it is born linked to the parent as a GitHub-native sub-issue (a derivative human-readable view; the authoritative linkage stays in the state's `decomposition_parents` map). Filing a sub-issue with `--parent` is a contract INVOKE of rabbit-issue, NOT a cross-feature edit, so every write stays inside one feature's scope"
      },
      {
        "path": ".claude/features/rabbit-cage/install.py",
        "subcommand": "",
        "rationale": "install-smoke.py (Inv 63 pre-merge install smoke) invokes rabbit-cage's install.py as a BLACK BOX subprocess — a fresh install plus an `--update`, both with explicit `--src <repo-root>` so the smoke is network-free — to catch install/closure/publish breakage before a PR merges. Running install.py as a subprocess is a contract INVOKE of rabbit-cage, NOT a cross-feature edit; install.py itself is never modified"
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
