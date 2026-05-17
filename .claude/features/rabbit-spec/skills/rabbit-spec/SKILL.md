---
name: rabbit-spec
description: Use when Step 3 of rabbit-feature-touch needs to author or update a feature spec before TDD dispatch. Invoke as Skill("rabbit-spec", args: "<feature-name> <request>") from rabbit-feature-touch or any context where a feature spec needs to be comprehended and updated. Also use when a user asks to update, review, or author a spec for any rabbit feature — even if they don't say "spec" explicitly (e.g., "think about what we need to build", "plan this feature", "what should change in the design").
model: opus
---

# rabbit-spec — Spec Authoring Skill

You are invoked as **Step 3 in rabbit-feature-touch**, before the TDD subagent is dispatched. Your job: understand the request, update the feature spec, and produce an implementation suggestion file that the TDD subagent will read as context.

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

The TDD subagent reads this file in its SPEC-READ step. Make `implementation_approach` genuinely useful — it should save the implementer from having to re-derive the approach from scratch.

## What You Do NOT Do

- Run tests (that is the TDD subagent's job)
- Write implementation code
- File bugs or backlog items (that is rabbit-file's job)
- Dispatch the TDD subagent (that is rabbit-feature-touch's job after you return)
- Invoke `Skill("rabbit-feature-touch")` — you are already inside it
