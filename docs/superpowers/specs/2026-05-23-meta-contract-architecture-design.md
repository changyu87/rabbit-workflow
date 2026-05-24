---
date: 2026-05-23
status: design-draft
drives: CONTRACT-BACKLOG-36
authors: Changyu, Claude (brainstorm session)
---

# Meta-Contract Architecture — Design

## Motivation

CONTRACT-BACKLOG-36 surfaced concern about rabbit-cage's spec size (~20K tokens, 892 lines, 95 invariants) and TDD-subagent performance under large context. Initial framing was "should we split rabbit-cage into sub-features?"

Investigation reframed the problem. rabbit-cage's spec bloat is **symptomatic of an architectural gap**: the contract feature was never designed to absorb cross-feature coordination work, so that work piled into rabbit-cage as ad-hoc integration code. Splitting rabbit-cage would only multiply the integration points.

The right fix is to invert the relationship. Instead of rabbit-cage being omniscient about every feature's surface, every feature **declares** what it publishes, what it runs, and what it configures — through a meta-contract owned by the contract feature. rabbit-cage becomes a thin dispatcher service that enumerates features and invokes their declared API calls.

This design proposes that architecture.

## Architecture Overview

Three structural roles in the new model:

1. **contract** — architecture container. Owns: meta-contract schema, four API libraries (publish, runtime, mutation, content-producer), generic templates and schemas, the shared `rabbit_print` library, generic enforcement checks. **Knows nothing about any specific feature.**

2. **rabbit-cage** — service dispatcher. At install time, enumerates features and invokes their MANIFEST API calls. At each Claude Code event, invokes registered RUNTIME APIs and aggregates typed returns into one JSON. Sole owner of the PreToolUse `scope-guard` hook (the only Claude Code event with no plugin layer). **Knows nothing about any specific feature** beyond reading their meta-contract declarations.

3. **rabbit-config** (new feature) — configuration manager. Hosts the `/rabbit-config` skill (mutation surface). At Stop time iterates every feature's CONFIGURATION declarations and emits alerts for active overrides. **Knows nothing about any specific configurable** — operates purely on the declarations.

Every other feature (rabbit-feature, rabbit-file, tdd-state-machine, tdd-subagent, policy) is pure declarations plus auxiliary scripts. They have no integration code anywhere in rabbit-cage; their full behavior is described by their meta-contract declarations.

The unifying property: **every cross-feature operation collapses to "feature declares API call → contract-owned dispatcher executes → typed return is merged."**

## Meta-Contract Schema

Each feature's `feature.json` carries three sections beyond its existing metadata fields:

### MANIFEST — what the feature publishes

A declarative call list. Each entry is `{api: "<publish_api_name>", args: {...}}`. The install-time dispatcher invokes every call in declaration order. APIs are idempotent.

```json
"manifest": [
  {"api": "publish_skill", "args": {"source": "skills/my-skill/SKILL.md"}},
  {"api": "publish_command", "args": {"source": "commands/my-cmd.md"}}
]
```

### RUNTIME — what the feature runs at Claude Code events

Keyed by Claude Code event name. Each event maps to a list of `{api: "<runtime_api_name>", args: {...}}`. The per-event dispatcher invokes every call and collects typed returns.

```json
"runtime": {
  "Stop": [
    {"api": "check_marker_alert", "args": {"path": ".my-marker", "alert": {"text": "...", "icon": "...", "color": "..."}}}
  ],
  "SessionStart": [],
  "UserPromptSubmit": []
}
```

### CONFIGURATION — what the feature exposes for mutation

List of configurables. Each declares:

| Field | Purpose |
|---|---|
| `id` | Stable identifier |
| `subcommand` | Name used in `/rabbit-config <subcommand> <value>` |
| `storage` | Where the value lives (typed; see vocabulary below) |
| `values` OR `actions` | Mutation API calls. `values` for state-style (boolean / integer / enum); `actions` for verb-style (lock / unlock / add / remove) |
| `default` | Default state |
| `alert-on` (optional) | Which value triggers an active-override Stop alert |
| `alert-message` (optional) | Text + icon + color for the alert |
| `validation` (optional) | Input validation rules |

Example:

```json
{
  "id": "human-approval",
  "subcommand": "human-approval",
  "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
  "values": {
    "true":  {"api": "delete_marker", "args": {"path": ".rabbit-human-approval-bypass"}},
    "false": {"api": "write_marker",  "args": {"path": ".rabbit-human-approval-bypass", "content": "session"}}
  },
  "default": "true",
  "alert-on": "false",
  "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE — Step 4 skipped", "icon": "key", "color": "red"}
}
```

### Storage type vocabulary (closed)

- `marker-file` — file presence (optionally content-matched)
- `json-key` — single value at a JSON path
- `json-array` — raw value inside a JSON array
- `json-array-templated` — value wrapped in a template before storage (e.g. `Bash({value}:*)`)

Adding a new storage type requires a contract version bump.

## Contract API Catalogs

### Publish APIs (`contract.lib.publish`)

| API | Purpose |
|---|---|
| `publish_skill(source)` | Deploy `SKILL.md` to `.claude/skills/<name>/` |
| `publish_command(source)` | Deploy to `.claude/commands/<name>.md` |
| `publish_agent(source)` | Deploy to `.claude/agents/<name>/` |
| `publish_hook(event, source)` | Deploy to `.claude/hooks/<name>.py` and register in `.claude/settings.json` under the named event |
| `publish_settings(source)` | Deploy to `.claude/settings.json` (rabbit-cage exclusive — only one feature may publish the shared settings file) |
| `publish_file(source, dest)` | Generic deploy (e.g. `README.md`, `install.py` at repo root) |
| `publish_generated(target, producer, args)` | Invoke a content producer; write output to `target` |

All publish APIs are idempotent: re-running with unchanged source is a no-op.

### Runtime APIs (`contract.lib.runtime`)

Each returns one or more typed values: `print | inject | ok | error`.

| API | Purpose | Returns |
|---|---|---|
| `check_drift_regenerate(target, producer, alert)` | If target diverges from regenerator output, regenerate + emit alert + inject expanded content | `print + inject` or `ok` |
| `check_manifest_drift(alert)` | Re-check all published artifacts; on drift, rebuild + emit alert listing drifted names | `print` or `ok` |
| `check_marker_alert(path, content, alert)` | If marker exists (optional content match), emit alert | `print` or `ok` |
| `check_marker_consume_alert(path, alert)` | If marker exists, consume + emit alert (interpolates marker content into alert text via `{marker-content}`) | `print` or `ok` |
| `check_counter_threshold_refresh(counter, env_var, source)` | If counter ≥ threshold, reset + inject policy from source | `inject` or `ok` |
| `welcome_with_policy(policy_source)` | Welcome banner + policy injection | `print + inject` |
| `iterate_configurables_alerts()` | Enumerate every feature's CONFIGURATION; for each whose value matches `alert-on`, emit `alert-message` | list of `print` |
| `iterate_configurables_banner()` | Like above but for SessionStart; emits structured per-flag display with icon + canonical revoke command | list of `print` |

Adding a new runtime API requires a contract version bump.

### Mutation APIs (`contract.lib.mutation`)

| API | Purpose |
|---|---|
| `write_marker(path, content)` | Write marker file |
| `delete_marker(path)` | Delete marker file (no-op if absent) |
| `set_json_key(file, key, value)` | Write value at JSON key path |
| `delete_json_key(file, key)` | Delete key from JSON (no-op if absent) |
| `append_json_array(file, key, value)` | Append to JSON array (idempotent on duplicates) |
| `remove_json_array_value(file, key, value)` | Remove value from JSON array (no-op if absent) |
| `run_feature_script(script, args)` | **ESCAPE HATCH**: invoke a feature-owned script for mutations outside standard primitives (e.g., chmod) |

The escape hatch exists for the small minority of mutations that don't fit standard primitives (e.g., `repo-permissions.py` chmod). New standard primitives should be preferred over escape-hatch reliance.

### Content Producer Library (`contract.lib.producers`)

Each producer takes named args, returns content as string or bytes.

| Producer | Purpose |
|---|---|
| `generate-claude-md(policy_source, header_source)` | Compose CLAUDE.md (header + @-imports for each policy file) |
| `expand-at-imports(file)` | Read file, expand `@path` lines to referenced file contents |
| `read-file(path)` | Raw file read |
| `compose-template(template, args)` | Template substitution (deferred — add when first needed) |

## Dispatcher Behavior

### Install-time publish loop

rabbit-cage's `install.py` (or equivalent service entry) enumerates `.claude/features/*/feature.json`, reads each `manifest` array, invokes every entry in declaration order. APIs are idempotent. On failure, the loop continues to give a full failure report; non-zero exit if any call failed.

### Per-event runtime dispatchers

rabbit-cage deploys one dispatcher hook per Claude Code event into `.claude/hooks/`:

- `stop-dispatcher.py` (Stop)
- `session-start-dispatcher.py` (SessionStart)
- `user-prompt-submit-dispatcher.py` (UserPromptSubmit)
- `scope-guard.py` (PreToolUse — owned by rabbit-cage outright, NOT a dispatcher; no plugin layer)

Each dispatcher:

1. Enumerates features; collects every RUNTIME entry for its event.
2. Invokes each declared API call in deterministic order (across features: alphabetical by feature name; within a feature: declaration order).
3. Partitions typed returns:
   - All `print` returns → render via `rabbit_print()` → newline-join → `systemMessage`
   - All `inject` returns → concat → `additionalContext` (in practice only one feature contributes per event; the policy block)
   - `ok` returns → drop
   - `error` returns → log to stderr; do not surface to Claude
4. If any output exists, emit one JSON object to stdout. Otherwise exit 0 silently.

The single-JSON-per-invocation constraint (Claude Code Stop hook protocol) is satisfied automatically by this aggregation — features cannot bypass it; all output is mediated through declared API returns.

### Determinism

Aggregation order is fully deterministic from declaration order (alphabetical feature + array index). No priority field is required; if ordering needs change, features re-order their declarations.

## Concrete Migration: rabbit-cage

The canonical worked example. Every current rabbit-cage behavior maps cleanly:

### MANIFEST

```json
"manifest": [
  {"api": "publish_hook", "args": {"event": "Stop", "source": "hooks/stop-dispatcher.py"}},
  {"api": "publish_hook", "args": {"event": "SessionStart", "source": "hooks/session-start-dispatcher.py"}},
  {"api": "publish_hook", "args": {"event": "UserPromptSubmit", "source": "hooks/user-prompt-submit-dispatcher.py"}},
  {"api": "publish_hook", "args": {"event": "PreToolUse", "source": "hooks/scope-guard.py"}},
  {"api": "publish_settings", "args": {"source": "settings.json"}},
  {"api": "publish_generated", "args": {
    "target": "CLAUDE.md",
    "producer": "generate-claude-md",
    "args": {"policy_source": ".claude/features/policy/", "header_source": "policy-header.json"}
  }},
  {"api": "publish_file", "args": {"source": "README.md", "dest": "README.md"}},
  {"api": "publish_file", "args": {"source": "install.py", "dest": "install.py"}},
  {"api": "publish_command", "args": {"source": "commands/rabbit-refresh.md"}},
  {"api": "publish_command", "args": {"source": "commands/rabbit-project.md"}}
]
```

### RUNTIME

```json
"runtime": {
  "Stop": [
    {"api": "check_drift_regenerate", "args": {
      "target": "CLAUDE.md", "producer": "generate-claude-md",
      "alert": {"text": "CLAUDE.md regenerated from policy drift", "icon": "warn", "color": "red"}
    }},
    {"api": "check_manifest_drift", "args": {
      "alert": {"text": "Surface drift detected — rebuilt: {names}", "icon": "rebuild", "color": "red"}
    }},
    {"api": "check_marker_alert", "args": {
      "path": ".rabbit-scope-override", "content": "session",
      "alert": {"text": "SCOPE GUARD OFF (session override active)", "icon": "unlock", "color": "red"}
    }},
    {"api": "check_marker_consume_alert", "args": {
      "path": ".rabbit-scope-override-used",
      "alert": {"text": "SCOPE GUARD BYPASSED (one-time override consumed)", "icon": "unlock", "color": "red"}
    }},
    {"api": "check_marker_consume_alert", "args": {
      "path": ".rabbit-skills-updated",
      "alert": {"text": "Skills updated: {marker-content}", "icon": "sparkle", "color": "green"}
    }}
  ],
  "SessionStart": [
    {"api": "welcome_with_policy", "args": {"policy_source": ".claude/features/policy/"}}
  ],
  "UserPromptSubmit": [
    {"api": "check_counter_threshold_refresh", "args": {
      "counter": ".rabbit-prompt-counter",
      "env_var": "RABBIT_REFRESH_EVERY",
      "policy_source": ".claude/features/policy/"
    }}
  ]
}
```

### CONFIGURATION

```json
"configuration": [
  {
    "id": "human-approval",
    "subcommand": "human-approval",
    "storage": {"type": "marker-file", "path": ".rabbit-human-approval-bypass"},
    "values": {
      "true":  {"api": "delete_marker", "args": {"path": ".rabbit-human-approval-bypass"}},
      "false": {"api": "write_marker",  "args": {"path": ".rabbit-human-approval-bypass", "content": "session"}}
    },
    "default": "true",
    "alert-on": "false",
    "alert-message": {"text": "HUMAN APPROVAL BYPASS ACTIVE — Step 4 skipped", "icon": "key", "color": "red"}
  },
  {
    "id": "bypass-permissions",
    "subcommand": "bypass-permissions",
    "storage": {"type": "json-key", "file": ".claude/settings.local.json", "key": "permissions.defaultMode"},
    "values": {
      "true":  {"api": "set_json_key",   "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode", "value": "bypassPermissions"}},
      "false": {"api": "delete_json_key", "args": {"file": ".claude/settings.local.json", "key": "permissions.defaultMode"}}
    },
    "default": "false",
    "alert-on": "true",
    "alert-message": {"text": "BYPASS-PERMISSIONS MODE ACTIVE — scope-guard is sole write-auth gate", "icon": "siren", "color": "red"}
  },
  {
    "id": "prompt-threshold",
    "subcommand": "prompt-threshold",
    "storage": {"type": "json-key", "file": ".claude/settings.local.json", "key": "env.RABBIT_REFRESH_EVERY"},
    "default": "20"
  },
  {
    "id": "allowed-tools",
    "subcommand": "allowed-tools",
    "storage": {"type": "json-array", "file": ".claude/settings.local.json", "key": "permissions.allow"},
    "actions": {
      "add":    {"api": "append_json_array",        "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "{tool}"}},
      "remove": {"api": "remove_json_array_value",  "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "{tool}"}}
    },
    "validation": {"reject_prefix": "Bash("}
  },
  {
    "id": "bash-allow",
    "subcommand": "bash-allow",
    "storage": {"type": "json-array-templated", "file": ".claude/settings.local.json", "key": "permissions.allow", "template": "Bash({value}:*)"},
    "actions": {
      "add":    {"api": "append_json_array",        "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "Bash({command}:*)"}},
      "remove": {"api": "remove_json_array_value",  "args": {"file": ".claude/settings.local.json", "key": "permissions.allow", "value": "Bash({command}:*)"}}
    },
    "validation": {"reject_chars": "():\\s"}
  },
  {
    "id": "permissions",
    "subcommand": "permissions",
    "actions": {
      "lock":   {"api": "run_feature_script", "args": {"script": "scripts/repo-permissions.py", "args": ["lock"]}},
      "unlock": {"api": "run_feature_script", "args": {"script": "scripts/repo-permissions.py", "args": ["unlock"]}}
    }
  }
]
```

## What Lives Where After Migration

### contract feature (~5–8K tokens spec, was ~7.5K)

- Meta-contract schema (feature.json + MANIFEST + RUNTIME + CONFIGURATION JSON schemas)
- API library modules: `lib/publish.py`, `lib/runtime.py`, `lib/mutation.py`, `lib/producers.py`
- Shared library: `scripts/rabbit_print.py` (simplified — see "What's Dropped")
- Generic CLI utilities: `find-feature.py`, `validate-feature.py`, `policy-block.py`
- Generic enforcement checks: 8 existing scripts under `scripts/enforcement/`, `lib/checks.py`
- Generic schemas: workspace-structure, bug, project-map, rabbit-print wire format
- Generic templates: spec, contract, feature.json, skill, command, etc.
- CHANGELOG.md (own tombstone log)

### rabbit-cage feature (~4–5K tokens spec, was ~20K)

- Service dispatchers: `hooks/stop-dispatcher.py`, `hooks/session-start-dispatcher.py`, `hooks/user-prompt-submit-dispatcher.py`
- PreToolUse owned hook: `hooks/scope-guard.py` + supporting `scripts/scope-guard-on.py`
- Bootstrap installer: `install.py`
- Generated-content producer source: `scripts/generate-claude-md.py` (registered as a `contract.lib.producers` entry; lives in rabbit-cage)
- Auxiliary user-facing scripts: `scripts/rabbit-project*.py`, `scripts/workspace-tree.py`
- Mutation-script: `scripts/repo-permissions.py` (invoked via `run_feature_script`)
- Settings source: `settings.json` (team-wide defaults)
- Meta-contract: full MANIFEST + RUNTIME + CONFIGURATION as shown above

### rabbit-config feature (new, ~1–2K tokens spec)

- Skill: `skills/rabbit-config/SKILL.md` (interpreter — `/rabbit-config <subcommand> <value-or-action>`)
- Skill script: `scripts/rabbit-config.py` (reads CONFIGURATION declarations across all features; dispatches to mutation APIs)
- Meta-contract: RUNTIME calls `iterate_configurables_alerts` (Stop) and `iterate_configurables_banner` (SessionStart)
- No CONFIGURATION of its own — operates on others' declarations

### Other features (no structural change)

rabbit-feature, rabbit-file, tdd-state-machine, tdd-subagent, policy — each gains explicit MANIFEST / RUNTIME / CONFIGURATION declarations for whatever they currently publish, observe, or configure. No integration code anywhere in rabbit-cage anymore.

## What's Dropped

- **Backward compatibility** — every feature is rewritten to the new schema. No coexistence window. (Explicit user decision: drop the burden.)
- **`build-contract.json`** — federated into per-feature MANIFEST declarations. The data file is deleted; its schema in contract is repurposed as the publish-call schema.
- **`rabbit-print-messages.json`** — federated into per-feature RUNTIME and CONFIGURATION declarations (text + icon + color in args). The data file is deleted; its schema in contract is repurposed as the rabbit-print wire-format spec.
- **Message-ids** — gone. Messages are first-class strings in declarations.
- **Named message wrappers** in `rabbit_print.py` (`welcome()`, `policy_drift()`, `scope_guard_off()`, etc.) — replaced by direct `rabbit_print(text, icon, color, format)` calls.
- **rabbit-cage's 95 invariants** — collapse to roughly 10–20 invariants covering only behaviors specific to rabbit-cage's own surface (scope-guard semantics, install behavior, dispatcher merge rules, content-producer registration).
- **rabbit-cage's `/rabbit-config` skill ownership** — moves to rabbit-config feature.

Estimated total spec-token reduction across the workflow: **~15–20K tokens** (rabbit-cage drops ~15K; contract drops ~3K; rabbit-config adds ~2K; rabbit-print message wrapper invariants removed ~2K).

## Open Questions / Deferred

- **MCP server publishing** — not in current scope. If MCP servers become published surface, add `publish_mcp_server` to the publish API set.
- **Cross-feature configurables** — today every configurable belongs to exactly one feature. If a configurable logically spans features, the design needs a rule. Defer until use case arises.
- **Hot reload** — configurables apply at next session start; the new model preserves this. No plan to add hot reload.
- **Mutator validation vocabulary** — first pass starts with `reject_prefix` and `reject_chars`; extend as needed.
- **Workspace-tree and rabbit-project scripts** — stay unchanged; not affected by this migration.

## Migration Sequence (high-level)

Detailed implementation plan is the next step (writing-plans skill). High-level ordering:

1. **Contract foundation** — meta-contract JSON schemas; API library skeletons (interfaces, no behavior); schema validator
2. **Contract API implementations** — publish, runtime, mutation, content-producer libraries with full behavior
3. **rabbit-cage dispatcher rewrite** — three new dispatcher hooks; `install.py` updated to enumerate features; full meta-contract declaration written
4. **rabbit-config feature scaffolding** — skill source, runtime declaration, mutation interpreter (reads CONFIGURATION declarations)
5. **Per-feature migration sweep** — each remaining feature (rabbit-feature, rabbit-file, tdd-state-machine, tdd-subagent, policy) gets its meta-contract written; old integration code removed
6. **Cleanup** — drop `build-contract.json`, `rabbit-print-messages.json`, message wrappers; remove old rabbit-cage invariants superseded by declarations
7. **Validation** — full test suite, end-to-end install + Stop + SessionStart + UserPromptSubmit cycle, scope-guard validation

Steps 1–5 land additively. Step 6 is the breaking cleanup. Step 7 is the final acceptance gate.

## Why This Works

The architecture's core property: **every workflow operation is a declarative API call against a contract-owned library, executed by a contract-aware dispatcher, returning a typed value.**

That single mechanism replaces:

- The build-contract.json catalog (now: per-feature MANIFEST)
- The rabbit-print-messages.json registry (now: per-feature inline)
- rabbit-cage's per-feature integration code (now: dispatcher loop)
- `/rabbit-config`'s per-configurable subcommand handlers (now: declaration interpreter)
- Cross-feature Stop alert orchestration (now: federated declarations + iterate API)
- The `surface_drift` / `skills-updated` / `human-approval-bypass` per-condition logic (now: runtime API calls)

The result: contract grows modestly (API library specs), rabbit-cage shrinks dramatically (no per-feature knowledge), and the workflow becomes statically inspectable end-to-end (every behavior is declared in JSON, validatable against schema).

The cost is a closed API vocabulary that grows as the workflow grows. Each new API method is an architectural change deserving contract review — which is exactly the right friction level for cross-feature mechanism.
