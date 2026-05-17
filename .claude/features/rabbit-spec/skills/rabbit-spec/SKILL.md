---
name: rabbit-spec
description: Use when a feature spec needs to be authored or updated, in any context. Invoke as Skill("rabbit-spec", args: "<feature-name> <request>") from any skill, process, or directly. Reads the current spec, judges the request type, invokes superpowers as needed, updates the spec surgically, and produces an implementation suggestion file for whoever invoked it. Also use when a user asks to update, review, or author a spec for any rabbit feature — even if they don't say "spec" explicitly (e.g., "think about what we need to build", "plan this feature", "what should change in the design", "update the design for this bug fix").
model: opus
---

# rabbit-spec — Spec Authoring Skill

Your job: understand the request, update the feature spec, and produce an implementation suggestion file. You are a general-purpose spec skill — any process can invoke you. You don't assume who called you or what comes next.

## Inputs

Args format: `<feature-name> <request-or-item-description>`

- **feature-name**: the rabbit feature to update (e.g., `tdd-subagent`, `rabbit-file`)
- **request**: the user's raw request, or a bug/backlog item description in B/B mode

## Step 1 — Read Current State

Before forming any opinion, read:
1. The feature's current spec: `.claude/features/<feature-name>/docs/spec/spec.md`
2. Any existing implementation files in `.claude/features/<feature-name>/scripts/` and `.claude/features/<feature-name>/skills/` (read freely — you are not writing to these)

Understanding what already exists prevents you from re-speccing things that are already implemented and helps you identify what actually needs to change.

## Step 2 — Judge Request Type

Decide whether the request is **open-ended** or **specific**:

| Signal | Classification |
|--------|---------------|
| Vague goal, exploratory language, "what should we do about X", no clear acceptance criteria | Open-ended |
| Bug fix, backlog task, bounded change with clear outcome, "add invariant N", "rename X to Y" | Specific |

When in doubt, lean toward **specific** — the brainstorming superpower adds cost and time, so only invoke it when the user genuinely needs design exploration.

## Step 3 — Invoke Superpowers

**If open-ended:**
```
Skill("superpowers:brainstorming")
```
Then, once design is settled:
```
Skill("superpowers:writing-plans")
```

**If specific:**
```
Skill("superpowers:writing-plans")
```
Only. No brainstorming needed when the change is already well-defined.

Both superpowers run under your current model context (opus). Do not dispatch a subagent — this skill runs inline.

## Step 4 — Update the Spec

Edit `.claude/features/<feature-name>/docs/spec/spec.md` to reflect what the request requires. Be surgical:
- For specific requests: add/modify only the affected invariants or surface entries
- For open-ended requests: apply the full design outcome from the superpowers above

Do not touch implementation files — your scope is the spec only.

## Step 5 — Write impl-suggestion File

Write `.rabbit/impl-suggestion-<feature-name>.json` (create `.rabbit/` if it doesn't exist):

```json
{
  "schema_version": "1.0.0",
  "feature": "<feature-name>",
  "generated_at": "<iso8601 timestamp>",
  "request_summary": "<one sentence: what was asked>",
  "spec_changes": "<one paragraph: what changed in the spec and why>",
  "implementation_approach": "<narrative: how you suggest implementing the spec changes>",
  "affected_files": ["<explicit path 1>", "<explicit path 2>"],
  "key_invariants": ["<invariant text that directly constrains implementation>"]
}
```

Make `implementation_approach` genuinely useful — it should save any downstream implementer from having to re-derive the approach from scratch.

## What You Do NOT Do

- Run tests
- Write implementation code
- File bugs or backlog items (that is rabbit-file's job)
- Invoke any other skill — your output is the impl-suggestion file; what happens next is the caller's concern
