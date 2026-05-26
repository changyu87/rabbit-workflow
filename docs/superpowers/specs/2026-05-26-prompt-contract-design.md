---
date: 2026-05-26
status: design-draft
drives: CONTRACT-BACKLOG-1
authors: Changyu, Claude (brainstorm session)
---

# Prompt-Contract — Design

## Motivation

CONTRACT-BACKLOG-1 ("Prompt control: human interface to inspect and edit
subagent context prompt before dispatch") surfaced that every subagent
dispatch assembles a context prompt (policy docs, spec, TDD state, etc.)
opaquely — the human cannot see what was assembled or correct it before
dispatch. A history note on the item (2026-05-19) added a size-axis
observation: `dispatch-tdd-subagent.py` assembled a ~90KB prompt during
a recent TDD cycle, exceeding the Agent tool's effective inline limit,
forcing the orchestrator to construct an abbreviated equivalent
manually.

The original framing treated the two concerns as separate: an inspect /
edit interface for humans, and a size optimization for the dispatcher.
The brainstorming session reframed them as a single problem: the
**prompt payload has no declared shape**. Every dispatcher inlines an
ad-hoc assembly. There is no contract for what fixed sections go in,
what variable sections the caller fills, what the resulting artifact
looks like, or who is responsible for which piece.

The fix mirrors the meta-contract architecture
(`docs/superpowers/specs/2026-05-23-meta-contract-architecture-design.md`):
every feature declares a `prompts` section in its `feature.json`, listing
each skill or subagent it surfaces, the fixed policy files that prompt
must inject (the **invariable** part), and the named slots a dispatcher
must fill at run time (the **variable** part). The contract feature owns
the schema, the templates, the assembler script, and the PreToolUse hook.
The dispatcher (whoever is invoking the skill or subagent) supplies the
slot values from the current work's context. Human review of the
invariable part is editing the `prompts` section of `feature.json`
through the normal `rabbit-feature-touch` flow — no separate skill
surface needed.

This design proposes that mechanism.

## Architecture Overview

**Three structural pieces, all owned by the `contract` feature:**

1. **Schema** — `prompts.schema.json` describes the shape of the
   `prompts` section that any `feature.json` may carry. Validated by
   the existing `validate_meta_contract` library function and CLI shim
   (Inv 43 of contract spec).

2. **Templates** — one plain-text template per registered callable,
   named by callable id, stored at
   `.claude/features/contract/templates/prompts/<id>.txt`. Each carries
   `{{slot_name}}` placeholders. The templates live where the assembler
   lives (contract); cross-feature edits are managed via
   `rabbit-feature-touch` on contract as normal.

3. **Assembler script + PreToolUse hook** — `build-prompt.py` reads the
   matching `prompts` entry across all `feature.json` files, reads the
   declared policy files, reads the matching template, substitutes slot
   values, writes the assembled prompt to `.rabbit/prompts/<id>-<pid>-<ts>.txt`,
   and prints the file path. The PreToolUse hook fires on Skill calls
   and emits the assembled prompt as `additionalContext`. Subagent
   dispatcher scripts invoke `build-prompt.py` directly and use its
   output as the `prompt` arg to `Agent()`.

**Per-feature declaration** lives in each feature's `feature.json` as
a new `prompts` section, alongside the existing `manifest`, `runtime`,
and `configuration` sections. Each feature can declare as many
callables as it surfaces; every entry is independent, with its own
`inject` list and its own slots.

**Storage location for assembled prompts** is `.rabbit/prompts/`. Already
the established location for ephemeral runtime artifacts
(`.rabbit/tdd-report-*.json`), already gitignored, outside
`.claude/features/` so scope-guard does not block writes. Files are
pid-stamped and timestamped for concurrent-dispatch safety and
deterministic cleanup.

**Human management interface — no separate skill.** Inspect = read the
owner feature's `feature.json`. Edit = `rabbit-feature-touch` on the
owner feature, modifying the `prompts` entry. Template content is
similarly edited via `rabbit-feature-touch` on `contract`. This matches
how every other meta-contract section is managed today; no new skill
surface is introduced.

## Schema: `prompts` section

`.claude/features/contract/schemas/prompts.schema.json` (draft-07,
hand-rolled validator in `contract.lib.checks` — matches the existing
meta-contract pattern, no `jsonschema` dependency):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when prompt-contract assembly is native to Claude Code",
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["id", "kind", "inject", "slots"],
    "properties": {
      "id":     {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
      "kind":   {"type": "string", "enum": ["skill", "subagent"]},
      "inject": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "slots":  {"type": "array", "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}}
    }
  }
}
```

### Field semantics

| Field | Semantic |
|---|---|
| `id` | Lowercase + dashes only. Must equal the Skill tool's `skill` arg (for `kind: skill`) or the dispatcher's `--callable-id` flag (for `kind: subagent`). Globally unique across all `feature.json` files (enforced by lint). |
| `kind` | Closed enum `"skill" \| "subagent"`. Drives whether the PreToolUse hook fires or the subagent dispatcher handles it. |
| `inject` | Non-empty array of repo-relative policy file paths. Explicit per author choice; the lint check enforces `philosophy.md` appears in every entry (universal-policy invariant). |
| `slots` | Array of slot names. May be empty for callables with no variable input. Each name must match a `{{slot_name}}` placeholder in the resolved template; lint check enforces bidirectional correspondence. |

### What is NOT stored in the entry

- **`template` field** — resolved by convention as
  `.claude/features/contract/templates/prompts/<id>.txt`. One less
  drift point.
- **`owner_feature` field** — derivable. The entry's owner is whichever
  `feature.json` contains it.
- **`deprecation_criterion` per-entry** — entries inherit their owner
  feature's lifecycle (matches how `manifest` / `runtime` /
  `configuration` entries work today).

### Multiple callables per feature

The `prompts` section is a list, and every entry is fully independent.
A feature that surfaces five skills + one subagent declares six entries,
each with its own `inject` list and slot set:

```json
"prompts": [
  {"id": "rabbit-feature-touch", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/spec-rules.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["task_description", "feature_name"]},
  {"id": "rabbit-feature-spec", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/spec-rules.md"],
   "slots": ["feature_name", "request"]},
  {"id": "rabbit-feature-new", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["feature_name"]},
  {"id": "rabbit-feature-audit", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/coding-rules.md"],
   "slots": ["target"]},
  {"id": "rabbit-feature-scope", "kind": "skill",
   "inject": [".claude/features/policy/philosophy.md"],
   "slots": ["natural_language_request"]},
  {"id": "rabbit-feature-spec-author-subagent", "kind": "subagent",
   "inject": [".claude/features/policy/philosophy.md",
              ".claude/features/policy/spec-rules.md"],
   "slots": ["feature_name", "current_spec", "request", "judgement_type"]}
]
```

### Integration with existing meta-contract validation

- Extend the existing dispatch in `contract.lib.checks.validate_meta_contract`:
  if `feature.json` has a `prompts` key, validate against
  `prompts.schema.json` rules. Sections remain optional — a feature with
  no `prompts` key validates successfully.
- Add `prompts` as an OPTIONAL `$ref` property in
  `feature.json.schema.json` (matches how `manifest` / `runtime` /
  `configuration` are declared per Inv 43).
- The existing CLI shim `validate-meta-contract.py` picks up the new
  section automatically.

### Lint check

New script `.claude/features/contract/scripts/enforcement/check-prompts-section.py`
(CLI shim) + `check_prompts_section(features_root: str) -> CheckResult`
in `contract.lib.checks`. Walks all `feature.json` files, asserts:

- All `prompts` entries validate against `prompts.schema.json`.
- All `id` values are globally unique across features.
- Every `inject` path exists on disk and is readable.
- Every `inject` list includes
  `.claude/features/policy/philosophy.md` (universal-policy
  invariant).
- For every entry,
  `.claude/features/contract/templates/prompts/<id>.txt` exists.
- For every entry, every `{{slot_name}}` placeholder in the template
  appears in the entry's `slots` array, and vice versa (no orphan
  slots in either direction).
- For `kind: subagent` entries: `id` SHOULD start with the owner
  feature's name (warn-only).

Wired into the contract feature's `test/run.py` (matches the pattern of
the other 8 enforcement checks).

## Assembler script: `build-prompt.py`

**Location** — `.claude/features/contract/scripts/build-prompt.py`.
Python 3 stdlib only.

**CLI shape:**

```
build-prompt.py --callable-id <id> [--slot <name>=<value> ...]
```

**Behavior:**

1. Resolve repo root (env `RABBIT_ROOT` or
   `git rev-parse --show-toplevel`, matching `policy-block.py`'s
   pattern).
2. Walk `.claude/features/*/feature.json`, find the entry whose `id`
   matches `--callable-id`. Exit 2 with stderr diagnostic if no match
   (defensive — schema lint prevents duplicates).
3. Validate that every slot in the entry's `slots` array has a
   corresponding `--slot <name>=<value>` flag. Exit 1 with stderr
   listing missing slot names if any.
4. Read each file in the entry's `inject` array. Exit 1 with stderr
   diagnostic if any is unreadable.
5. Read the template at
   `.claude/features/contract/templates/prompts/<id>.txt`. Exit 1 if
   unreadable.
6. Substitute `{{slot_name}}` placeholders in the template with the
   supplied values. Any unsubstituted placeholder remaining after
   substitution is an error (exit 1, stderr listing orphans).
7. Concatenate: assembled prompt = `<policy block from inject files>`
   + `"\n\n"` + `<slot-substituted template body>`. The policy block
   format reuses the existing `policy-block.py` framing (sentinel line
   `RABBIT-POLICY-BLOCK-v1`, header banner, per-file section
   separators, footer banner) — extracted into
   `contract.lib.policy_block` and imported from both scripts.
8. Write the assembled prompt to
   `.rabbit/prompts/<id>-<pid>-<ts>.txt`. Create `.rabbit/prompts/`
   if missing. `<ts>` is `YYYYMMDD-HHMMSS-ms` for deterministic sort
   and uniqueness across pid recycles.
9. Print the absolute path of the written file to stdout. Exit 0.

**Concurrency** — stateless; uniquely-named outputs; concurrent
invocations never collide.

**Idempotency** — none. Each call writes a new snapshot file (the
snapshot is the point — every dispatch wants its own record of "what
was injected when").

**No mutation** of registry or templates: read-only against
`feature.json` files and templates; writes only to `.rabbit/prompts/`.

**Exit codes:**

| Code | Meaning |
|---|---|
| `0` | Success — prompt file written, path on stdout |
| `1` | Read error (registry / template / policy), missing slot, orphan placeholder |
| `2` | No entry matches `--callable-id`, or invocation error |

Module-level docstring includes Version, Owner
(`rabbit-workflow team (contract)`), and Deprecation criterion
(`when prompt-contract assembly is native to Claude Code`).

## PreToolUse hook: `prompt-injector.py`

**Source location** —
`.claude/features/contract/hooks/prompt-injector.py`. Deployed to
`.claude/hooks/prompt-injector.py` by contract's own `manifest` via a
new `publish_hook` entry (contract previously had no manifest; this is
its first manifest entry).

**Settings registration** — `publish_hook` is already migration-aware
and idempotent (Inv 50 of contract spec). It performs a read-modify-write
on `.claude/settings.json` to register the hook under the PreToolUse
event without disturbing `rabbit-cage`'s ownership of the settings
file. No coordination edit in `rabbit-cage` is needed.

**Hook input** — JSON on stdin (Claude Code PreToolUse contract) with
`tool_name` and `tool_input`.

**Behavior:**

1. Read JSON from stdin. Extract `tool_name` and `tool_input`.
2. If `tool_name != "Skill"`: return `{}`, exit 0. (Hook is a no-op
   for Agent and all other tools — subagent prompts are pre-assembled
   by their dispatcher script.)
3. From `tool_input`, extract the `skill` arg.
4. Walk `.claude/features/*/feature.json`, find the `prompts` entry
   with `kind: "skill"` and `id == <skill name>`. If no match: return
   `{}`, exit 0. (Skill is not registered for prompt injection — silent
   no-op, matching scope-guard's "no match = no action" pattern.)
5. **Slot resolution:** Skill tool args carry one free-text `args`
   field from the orchestrator. The hook treats the entire `args`
   string as the value of the slot named `args`. If the entry declares
   slots other than `args`, the entry is mis-declared; the hook logs a
   warning to the failure log and skips injection (does NOT block the
   call).
6. Invoke `build-prompt.py --callable-id <id> --slot args=<value>`.
   Capture stdout (file path).
7. Read the file contents.
8. Emit JSON on stdout: `{"hookSpecificOutput":
   {"hookEventName": "PreToolUse",
    "additionalContext": "<file contents>"}}`. Exit 0.

**On failure of `build-prompt.py`:** the hook appends a JSON line to
`.rabbit/prompts/.injection-failures.log`, then returns `{}` and exits
0 (best-effort: a broken prompt-contract must not block the user's
skill call). The Stop-event runtime surfaces failures via
`check_prompt_injection_failures` (see Runtime APIs below).

**Why subagents don't go through this hook:** Claude Code's PreToolUse
hook cannot mutate tool args, only emit `additionalContext`. For Agent
calls, `additionalContext` lands in the orchestrator's conversation but
not the subagent's first message — useless for the subagent itself.
Subagent dispatchers (e.g., `dispatch-tdd-subagent.py`) already build
the full prompt string and pass it as `Agent(prompt: ...)`; they
invoke `build-prompt.py` directly and use its output as the prompt.

## Runtime APIs: cleanup + failure alerts

Two new runtime APIs in `contract.lib.runtime` and the closed enum in
`runtime.schema.json` (adding a runtime API is a contract version bump
per Inv 41 of contract spec):

### `cleanup_old_prompts(max_age_days: int, *, repo_root: str) -> CheckResult`

Walks `.rabbit/prompts/`, deletes files older than `max_age_days`
(based on the `<ts>` prefix in the filename — no `stat` call needed,
deterministic). Returns `ok_result()` on success (sweeping is silent).
Idempotent. Returns `ok_result()` if `.rabbit/prompts/` doesn't exist.

### `check_prompt_injection_failures(log_path: str, *, repo_root: str) -> CheckResult`

Reads the structured failure log (one JSON line per failure:
`{ts, skill, callable_id, error}`). If the log has new entries since
the last Stop event (tracked by a sidecar
`.rabbit/prompts/.last-seen-ts`), returns `print_result(text, "📢", "red")`
with a one-line summary listing the failing skill names. Empties the log
file after surfacing. Returns `ok_result()` when the log is empty.
Matches the existing `check_marker_consume_alert` pattern (consumes
its trigger after surfacing).

### Contract's `runtime` section

```json
"runtime": {
  "Stop": [
    {"api": "check_prompt_injection_failures",
     "args": {"log_path": ".rabbit/prompts/.injection-failures.log"}},
    {"api": "cleanup_old_prompts",
     "args": {"max_age_days": 7}}
  ]
}
```

`max_age_days: 7` matches the 7-day expiration the workflow uses
elsewhere. Configurable per-installation by editing the args in
contract's `feature.json` (no separate configurable section needed).

### Schema updates

`runtime.schema.json` adds `check_prompt_injection_failures` and
`cleanup_old_prompts` to the closed API enum (Inv 41). Test fixture
`test-runtime-schema-shape.py` gains the two new entries.

### Spec amendment to contract feature

The "Meta-contract sections" paragraph of contract spec.md (which
currently asserts contract has no `manifest`/`runtime`/`configuration`)
needs updating: contract now legitimately has both `manifest` (one
`publish_hook` entry for the injector) and `runtime` (the two new Stop
calls). The paragraph changes from "the absence is the correct state"
to "contract owns the publish/observe surface for the prompt-injection
machinery only; no broader integration." A real spec change for
contract that the implementation TDD cycle codifies.

## Migration

The change is **additive for everyone except `tdd-subagent`**. Other
callables get their `prompts` entry without code changes; their
SKILL.md bodies stay as-is and just gain additional injected context
from the hook.

### tdd-subagent migration (the hard one)

`dispatch-tdd-subagent.py` currently builds the full prompt inline via
f-string (lines 339–596 of the existing script). The migration extracts
that body into a template and reduces the script to argument validation
+ slot-fill + assembler invocation.

**Step 1** — Create
`.claude/features/contract/templates/prompts/tdd-subagent.txt`. Copy
the f-string body from `dispatch-tdd-subagent.py` lines 339–596.
Replace every `{python_format_var}` with `{{python_format_var}}`. The
result is the existing TDD prompt frozen as a template.

**Step 2** — Declare `prompts` entry in `tdd-subagent`'s `feature.json`:

```json
"prompts": [
  {
    "id": "tdd-subagent",
    "kind": "subagent",
    "inject": [
      ".claude/features/policy/philosophy.md",
      ".claude/features/policy/spec-rules.md",
      ".claude/features/policy/coding-rules.md"
    ],
    "slots": [
      "feature_name", "spec_content", "impl_suggestion_block",
      "bypass_preamble_note", "feature_dir", "tdd_step_py",
      "repo_root", "max_iterations", "code_review_loop_note",
      "linked_item_value", "item_type_value",
      "close_calls_block", "handoff_closed_items_block",
      "handoff_closed_items_json"
    ]
  }
]
```

(Exact slot list derived mechanically from the existing f-string
variables — no semantic change.)

**Step 3** — Rewrite `dispatch-tdd-subagent.py`. The script keeps its
existing CLI shape (all the `--scope` / `--spec` / `--linked-item` /
etc. flags) and all its validation logic. The change is in the
assembly section. Replace the 250-line f-string with a ~15-line block
that builds a slot dict, invokes `build-prompt.py` via subprocess,
reads the resulting file, and writes its contents to stdout. The
script's existing stdout contract is preserved —
`rabbit-feature-touch` SKILL.md still does
`PROMPT=$(python3 dispatch-tdd-subagent.py ...)` and passes `$PROMPT`
to Agent. No caller-side change. The `policy-block.py` direct call is
removed (the assembler emits the policy block from the entry's
`inject` list).

**Step 4** — Delete the unused
`.claude/features/contract/templates/subagent-launch-template.txt`
(the dead template). Its placeholders are superseded by the
per-callable templates under `templates/prompts/`. Contract spec.md
Surface list gets a corresponding edit removing the template entry.

**Step 5** — `dispatch-tdd-subagent.py`'s existing invariants (Inv 7–23
of tdd-subagent spec, which describe the prompt's content rules)
become **template invariants** rather than script invariants. They
still apply — they're verified against the template file rather than
the f-string. Existing tests like `test-bypass-marker-note.py`
continue to work (the bypass note still flows through `rabbit_print`
from the script, slotted into the template via the
`bypass_preamble_note` slot).

### Other features — minimal additive migration

For `rabbit-feature`, `rabbit-file`, `rabbit-config`, and
`tdd-subagent` (its skill entries, distinct from the subagent entry
above): each gains a `prompts` entry in its `feature.json` declaring
its skills + each skill's `inject` list. The SKILL.md bodies
themselves require no edit — the PreToolUse hook injects the policy
via `additionalContext` alongside the existing skill body. Each
feature also gets a one-file template at
`.claude/features/contract/templates/prompts/<skill-id>.txt`. For
skills with no variable input beyond what the SKILL.md already covers,
the template can be a single-line passthrough (`{{args}}`). The lint
check tolerates near-empty templates.

Per-feature migration is roughly: edit `feature.json` to add the
`prompts` block + commit one template file under contract. Two file
edits per feature, one TDD cycle each via `rabbit-feature-touch`.

### Migration sequence

1. **contract** TDD cycle — add schema, templates dir convention,
   assembler script, hook source, runtime APIs, lint check. Update
   contract spec.md (meta-contract-sections paragraph amendment,
   manifest section, runtime section).
2. **tdd-subagent** TDD cycle — extract template, declare `prompts`
   entry, rewrite `dispatch-tdd-subagent.py` per Steps 1–3 above.
3. **Per-feature TDD cycles** (rabbit-feature, rabbit-file,
   rabbit-config, etc.) — each adds its `prompts` entries and minimal
   templates. Independent; can be parallelized via concurrent
   `rabbit-feature-touch` dispatches.
4. **Cleanup TDD cycle on contract** — delete
   `subagent-launch-template.txt`, remove from spec Surface list.

Each step is independently shippable. The system works as soon as
step 1 lands (no callable declares a `prompts` entry yet → no
behavior change). Step 2 onward each cuts over one callable at a
time with no global flag day.

## What Is Not in Scope

- **Per-dispatch human inspect/edit/bypass gate** — the user chose
  pre-registration configuration only. The original backlog's INSPECT
  / EDIT capabilities are satisfied by reading/editing the `prompts`
  section of `feature.json`; BYPASS is not needed because there is no
  per-call gate.
- **Auto-inferred `kind`-based policy bundles** — the user chose
  explicit `inject` lists per entry. No closed kind→policy mapping.
- **Affected-invariant subsetting** (CONTRACT-BACKLOG-35) — a separate
  optimization. The slots mechanism can carry an
  `affected_invariants_block` slot, but the dispatcher is responsible
  for filling it; this design adds no machinery for it.
- **Skill body assembly** — SKILL.md bodies are loaded from disk
  unchanged. The hook adds policy as `additionalContext` alongside;
  the body is not regenerated.
- **MCP tool calls** — the hook fires on Skill only. Agent goes through
  its dispatcher. Other tool types are not in scope.

## Open Questions / Deferred

- **Cross-feature subagent ids** — soft warning today (subagent `id`
  SHOULD start with owner feature name). If a use case for a
  legitimately cross-feature subagent emerges, the convention is
  documented but not enforced.
- **Slot value escaping** — the assembler does string substitution.
  If a slot value contains the literal text `{{other_slot}}`, the
  assembler will substitute it on the next pass. Today's templates
  don't exercise this; if it becomes an issue, switch to a single-pass
  substitution algorithm.
- **Prompt file retention** — 7 days is the default. If forensic /
  audit needs require longer retention, the value is editable in
  contract's `feature.json` per-installation.
