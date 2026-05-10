# Rabbit-Cage Template Redesign — Drift-Resistance Design Doc

**Owner:** rabbit-workflow team
**Version:** 1.0.0
**Status:** brainstorm deliverable — input for step 8.5 (template refresh + TDD)
**Deprecation criterion:** superseded once templates land and a post-step-9 audit shows no observed drift across two consecutive feature TDD cycles.

---

## Core principle

> A spec is a typed lookup table for a subagent. The contract is its boundary fence. Everything else is policy, lives in the policy block, and never appears in the per-feature artifact.

---

## Priority changes (apply first — covers 80% of drift surface)

| # | Change | Impact |
|---|---|---|
| 1 | YAML frontmatter on every spec/contract | Machine-parseable header |
| 2 | `contract.md` becomes fenced JSON block | Eliminates cross-feature prose ambiguity |
| 3 | Subagent launch template adds SUCCESS_CRITERIA + HANDOFF block | Closes R7 verification loop |
| 4 | Strip restated policy from spec.md (every feature) | Removes largest noise source |
| 5 | Bug schema adds `resolution`, `triage`, `closed.commit/pr` | Audit becomes pure JSON query |
| 6 | feature.json adds `contract_version`, `spec_version` | Detects schema drift |
| 7 | registry/project-map add `built_at`/`built_by` | Staleness detection |
| 8 | Triage template adds `vet_id`/`vetted_by`/`vetted_at` | Multi-triage ordering |

---

## Drift-resistance rules (apply to every spec)

1. **Never restate policy.** If a sentence appears in `policy/`, delete it from the spec.
2. **Every invariant is testable.** If you cannot write a 0/1 script for it, it is not an invariant — move to `docs/notes.md`.
3. **One sentence per claim.** No clauses, no parentheticals.
4. **No "should," "may," "typically."** Use imperative (`MUST`) or declarative present tense.
5. **No examples in spec.** Examples live in `docs/notes.md` with their own version stamp.

---

## Recommended template structures

### `spec-template.md` v2.0.0

```markdown
---
feature: {{feature_name}}
version: {{version}}
owner: {{owner}}
template_version: 2.0.0
deprecation_criterion: {{deprecation_criterion}}
status: active
---

# {{feature_name}} — Spec

## Purpose

<One sentence. Imperative or declarative. No clauses.>

## Surface

- <path or interface>

## Invariants

1. <invariant — testable by script>
2. <invariant — testable by script>

## Out of Scope (optional — include only when misreadings have occurred)

- <thing this feature does NOT do>
```

**Removed:** `Reads`, `Invokes` — these belong in `contract.md`, not `spec.md`.

---

### `contract-template.md` v2.0.0

```markdown
---
feature: {{feature_name}}
version: {{version}}
template_version: 2.0.0
---

# {{feature_name}} — Contract

Boundary contract for cross-feature consumers. Read the JSON block; ignore prose.

\`\`\`json
{
  "provides": {
    "files":    ["path/relative/to/repo/root"],
    "scripts":  [{"path": "...", "stdin": "...", "stdout": "...", "exit": "..."}],
    "schemas":  [],
    "templates":[]
  },
  "reads": {
    "files":    [],
    "external": ["env-var:NAME", "claude-tool:Bash"]
  },
  "invokes": {
    "scripts":  [],
    "agents":   []
  },
  "never": [
    "writes outside its scope directory",
    "modifies another feature's files",
    "writes settings.local.json"
  ]
}
\`\`\`
```

**The `never` array is mandatory** — must include universal scope-guard forbiddances inline.

---

### `subagent-launch-template.txt` v2.0.0

```
# template_version: 2.0.0
RABBIT-POLICY-BLOCK-v1
{{POLICY_BLOCK}}

═══════════════════════════════════════════════════════════════════════════════
SCOPE
═══════════════════════════════════════════════════════════════════════════════
feature:    {{feature_name}}
scope_dir:  {{scope_dir}}
tdd_state:  {{tdd_state}}

You may write ONLY inside scope_dir. Any other write is a policy violation
and will be blocked by scope-guard.

═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
{{task_one_sentence}}

═══════════════════════════════════════════════════════════════════════════════
SUCCESS_CRITERIA
═══════════════════════════════════════════════════════════════════════════════
{{success_criteria_bulleted}}
(Each bullet: "<change> -> verify: <command-or-check>")

═══════════════════════════════════════════════════════════════════════════════
CONSTRAINTS (run-specific, not in spec)
═══════════════════════════════════════════════════════════════════════════════
{{constraints_bulleted_or_none}}

═══════════════════════════════════════════════════════════════════════════════
OUT_OF_SCOPE (anticipated temptations)
═══════════════════════════════════════════════════════════════════════════════
{{out_of_scope_bulleted_or_none}}

═══════════════════════════════════════════════════════════════════════════════
FEATURE SPEC (read-only)
═══════════════════════════════════════════════════════════════════════════════
{{feature_spec}}

═══════════════════════════════════════════════════════════════════════════════
FEATURE CONTRACT (read-only)
═══════════════════════════════════════════════════════════════════════════════
{{feature_contract}}

═══════════════════════════════════════════════════════════════════════════════
HANDOFF FORMAT
═══════════════════════════════════════════════════════════════════════════════
On completion, emit exactly:

```
HANDOFF:
  feature:        {{feature_name}}
  task:           {{task_one_sentence}}
  files_touched:  [<relative paths>]
  verify_results: [<criterion>: pass|fail]
  next_action:    <dispatcher_proceeds|needs_review|blocked:<reason>>
```
No prose outside this block.
```

---

### `bug-template.json` v2.0.0

```json
{
  "_template_version": "2.0.0",
  "id": "<feature>-<NNN>",
  "title": "<one-line problem statement>",
  "status": "open|in_triage|in_progress|closed",
  "resolution": null,
  "severity": "low|medium|high|critical",
  "description": "<full prose problem statement>",
  "related_feature": "<feature-name>|null",
  "filed":   {"ts": "<ISO-8601>", "by": "<actor>"},
  "closed":  {"ts": null, "by": null, "commit": null, "pr": null},
  "triage":  {"ts": null, "vet_id": null, "classification": null, "evidence_ref": null},
  "history": [
    {"ts": "<ISO-8601>", "actor": "<name>", "action": "opened", "note": "<initial>"}
  ]
}
```

Where `resolution`: `null | fixed | duplicate | invalid | wontfix | superseded`.

---

### `feature-json-template.json` v2.0.0

Add `contract_version` and `spec_version` for drift detection:

```json
{
  "template_version": "2.0.0",
  "name": "{{feature_name}}",
  "version": "{{version}}",
  "owner": "{{owner}}",
  "tdd_state": "spec",
  "summary": "{{summary}}",
  "surface": {"hooks": [], "commands": [], "agents": [], "skills": []},
  "contract_version": "1.0.0",
  "spec_version": "1.0.0",
  "bugs_root": "{{bugs_root}}",
  "deprecation_criterion": "{{deprecation_criterion}}"
}
```

---

### `registry-template.json` and `project-map-template.json` v2.0.0

Add `built_at` and `built_by` for staleness detection.

---

## Validation scripts to add to `contract/scripts/`

1. `check-spec-frontmatter.sh <feature-dir>` — parses YAML frontmatter, asserts required fields.
2. `check-contract-json.sh <feature-dir>` — extracts fenced JSON, validates against schema.
3. `check-spec-no-policy-restatement.sh <feature-dir>` — greps spec body for policy restatements.
4. `check-launch-prompt-shape.sh <prompt-file>` — asserts SCOPE, TASK, SUCCESS_CRITERIA, HANDOFF present.

These run at `test-green` transition in `tdd-step.sh`.

---

## Coexistence window

Template 1.0.0 accepted for one more TDD cycle per feature, then removed. Each feature's refresh (step 8.5) constitutes the migration.
