---
feature: rabbit-feature
version: 1.40.0
owner: rabbit-workflow team
deprecation_criterion: When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.
template_version: 2.0.0
---

# rabbit-feature — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "When feature-touch orchestration is natively handled by the rabbit CLI or by Claude Code's native workflow mechanism.",
  "provides": {
    "files": [],
    "commands": [
      {
        "path": ".claude/commands/rabbit-tdd-autonomous.md",
        "purpose": "Per-feature config command /rabbit-tdd-autonomous true|false. Toggles TDD-autonomous mode — the approval gate over the feature-touch TDD cycle Step 4. true writes the .rabbit-tdd-autonomous bypass marker (gate skipped); false (default) deletes it (gate active). Thin wrapper over contract.lib.config_dispatch via scripts/rabbit-tdd-autonomous-config.py. Deployed from commands/rabbit-tdd-autonomous.md via the feature.json manifest publish_command call. Sole supported surface for this configurable."
      }
    ],
    "scripts": [
      {
        "path": ".claude/features/rabbit-feature/scripts/rabbit-tdd-autonomous-config.py",
        "purpose": "THIN wrapper backing the /rabbit-tdd-autonomous command. Reads rabbit-feature's own feature.json configuration[] tdd-autonomous entry and delegates validation + mutation + restart-prompt rendering to contract.lib.config_dispatch.dispatch_config. Owns only argv parsing and IO; never re-implements the interpreter."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/resolve-scope.py",
        "purpose": "Builds the Agent-dispatch prompt that maps a natural-language request to the list of rabbit features the request will modify. Emits the prompt to stdout for default-model Agent dispatch."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/format-feature-context.py",
        "purpose": "Reads find-feature.py list-json output from stdin and writes the formatted feature-context block to stdout. Consumed by resolve-scope.py."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/scaffold-feature.py",
        "purpose": "Feature-scaffolding script invoked by rabbit-feature-scaffold. Creates a conforming feature directory (feature.json, flat docs/{spec,contract}.md, docs/bugs/, test/run.py) at the ratified flat docs/ layout, at any path. Plugin mode additionally supports --batch <features.json> to scaffold N features in one project-map.json mutation."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scaffold/scripts/scaffold-batch.py",
        "purpose": "Companion script for the rabbit-feature-scaffold skill (spec-rules.md §4 Script-Backed Orchestration). The declared skill-level interface for BOTH single and batch scaffolding: '--batch <features.json>' or '--list \"<name> [glob ...]; ...\"' normalize a batch input and delegate to scaffold-feature.py --batch; a bare '<name> [glob ...]' delegates byte-for-byte to scaffold-feature.py's single-feature surface. Callers (rabbit-decompose included) invoke the skill — which runs this script — rather than shelling out to scaffold-feature.py --batch directly (#921). No-arg/-h prints usage; exit codes mirror scaffold-feature.py (0/1/2)."
      },
      {
        "path": ".claude/features/rabbit-feature/scripts/audit-owner.py",
        "purpose": "Standalone team-owner enforcement script, run directly (script-tier). Validates that a feature's feature.json owner equals 'rabbit-workflow team'; exits 0 on pass (or for a feature exempted by contract Inv 36's status short-circuit), 1 on individual-owner mismatch (message names feature + current owner), 2 on bad invocation."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-touch/scripts/feature-touch.py",
        "purpose": "Companion script for the rabbit-feature-touch skill (spec-rules.md §4 Script-Backed Orchestration). Owns the skill's computed / mode-aware orchestration: 'resolve-spec-path <feature-name>' prints the resolved spec path (flat docs/spec.md preferred, then legacy docs/spec/spec.md; mode-aware via .rabbit/.runtime/mode); 'resolve-contract-path <feature-name>' mirrors that order for contract.md; 'commit-spec <feature-name> <summary>' stages (mode-aware git add / git add -f), skips on empty diff, else commits 'spec(<name>): update spec for <summary>'. No-arg invocation prints usage and exits 2."
      }
    ],
    "schemas": [],
    "templates": [],
    "skills": [
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-touch/",
        "purpose": "Orchestration skill triggered on feature write/edit/delete/add. Authoritative source for the deployed .claude/skills/rabbit-feature-touch/SKILL.md via the feature.json manifest publish_skill API call."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scope/",
        "purpose": "General-purpose shared skill: resolves a natural-language request to the list of rabbit features whose files it will modify; emits a prompt for a default-model Agent dispatch."
      },
      {
        "path": ".claude/features/rabbit-feature/skills/rabbit-feature-scaffold/",
        "purpose": "Feature-scaffolding skill — the user-facing scaffold primitive for adding one feature (single mode) or N features (plugin batch mode). Single mode shells out to scaffold-feature.py then validates via contract's validate-feature.py; batch mode routes through the companion scaffold-batch.py script (declared skill-level interface for both modes, #921)."
      }
    ]
  },
  "reads": {
    "files": [],
    "external": []
  },
  "invokes": {
    "scripts": [
      {
        "path": ".claude/features/contract/lib/config_dispatch.py",
        "signature": "dispatch_config(cfg, value, *, repo_root, feature_dir=None, template_value=None) -> {ok, messages, restart_prompt, error}",
        "exit": "returns a structured dict; never prints, never sys.exit",
        "lock": "test-tdd-autonomous-command.py asserts scripts/rabbit-tdd-autonomous-config.py imports dispatch_config and does not re-implement the interpreter (Inv 58)"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/tdd-step.py",
        "signature": "tdd-step.py {show|next|transitions|transition} <feature-dir> [<new-state>] [--force] [--spec-no-change-reason <reason>]",
        "exit": "0=success, 1=denied/invalid, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      },
      {
        "path": ".claude/features/tdd-subagent/scripts/dispatch-tdd-subagent.py",
        "signature": "dispatch-tdd-subagent.py --scope <feature-name> --spec <spec-path> [--impl-suggestion <path>] [--affected-invariants <n,n,...>] [--code-review-full-loop] [--max-iterations N]",
        "exit": "0=success, 1=feature not found, 2=bad invocation",
        "lock": "test/test-cross-feature-interface.py asserts --help exits 0 with 'usage:' text (Inv 3)"
      },
      {
        "path": ".claude/features/contract/scripts/find-feature.py",
        "signature": "find-feature.py <repo-root> list-json",
        "exit": "0=success, non-zero on invocation error",
        "lock": "test-scope-scripts.py asserts resolve-scope.py invokes this script (Inv 19)"
      },
      {
        "path": ".claude/features/contract/scripts/validate-feature.py",
        "signature": "validate-feature.py <feature-dir>|all",
        "exit": "0=pass, 1=validation failure, 2=bad invocation",
        "lock": "test-new-skill.py asserts rabbit-feature-scaffold invokes this script (Inv 33)"
      },
      {
        "path": ".claude/features/rabbit-spec/scripts/dispatch-spec-create.py",
        "signature": "dispatch-spec-create.py --feature-name <name> [--paths <glob1>,<glob2>,...]",
        "exit": "0=success, 1=invocation error, 2=build-prompt.py subprocess failure",
        "lock": "test-feature-new-plugin-mode.py asserts plugin-mode scaffold-feature.py prints this exact dispatch command to stdout (Inv 48); the command string is also referenced by name in scaffold-feature.py source so test-contract-md.py picks it up as a cross-feature reference."
      }
    ],
    "agents": []
  },
  "manages": {
    "runtime_markers": [
      {
        "path": ".rabbit-tdd-autonomous",
        "writer": "/rabbit-tdd-autonomous (scripts/rabbit-tdd-autonomous-config.py), via contract.lib.mutation write_marker/delete_marker",
        "reader": "dispatch-tdd-subagent.py (Step-4 gate, read alongside .rabbit-human-approval-bypass); Stop/SessionStart dispatcher via check_marker_alert (Inv 59)",
        "lifecycle": "written on `tdd-autonomous true` (bypass active); deleted on `tdd-autonomous false` (default, gate active)",
        "gitignored": true
      }
    ]
  },
  "never": [
    "modifies tdd-subagent spec, contract, feature.json, or scripts",
    "modifies workspace-structure.json"
  ]
}
```
