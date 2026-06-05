---
name: rabbit-decompose
description: Propose a feature decomposition for an existing codebase or a high-level spec, interactively iterate with the user until accepted, then orchestrate scaffolding + initial spec drafting per accepted feature. Use when the user wants to start a new rabbit-managed project from a spec/prompt, or when the user wants to retroactively organize an existing codebase into rabbit features. Phrases like "decompose this into features", "propose a feature breakdown", "let's organize this codebase with rabbit", "/rabbit-decompose", "what features should this project have". Do NOT use to revise individual feature specs (that's rabbit-spec-update) or to scaffold a single feature whose name + globs you already know (that's rabbit-feature-scaffold).
version: 0.7.1
owner: rabbit-workflow team
deprecation_criterion: when Claude Code exposes native feature-decomposition assistance that supersedes this skill
---

# rabbit-decompose — Interactive Feature Decomposer

Your job: turn a high-level intent — a spec, a design doc, or a codebase — into a list of rabbit features the user accepts, then drive the downstream pipeline (scaffold + initial spec draft) per accepted feature.

This skill is **interactive by design**. Do not fire-and-forget. The user reviews the proposal and adjusts it before any scaffolding happens.

## Inputs

Args format: `<scenario-hint-or-source>`

The user may supply:
- A scenario hint (`"greenfield"`, `"existing-codebase"`) and a source (spec text inline, path to a design doc, or path to a codebase root)
- Just a source — infer the scenario from whether the source is a file vs a directory
- Just a scenario — ask the user for the source

When unclear, ask the user one focused question to disambiguate. Do not guess.

## Protocol

### Step 1 — Gather inputs

Confirm the scenario and source material with the user. Two cases:

- **Greenfield**: the source is a spec, design doc, or natural-language description. The decomposition produces a feature list with names + purposes; globs MAY be empty (features will be authored from scratch).
- **Existing codebase**: the source is a directory under the project root. The decomposition produces a feature list with names + purposes + path globs (each feature owns a slice of the existing code).

**Where the source lives — resolve it, do not guess.** When the user does not give an explicit source path (e.g. a no-args existing-codebase run), the decomposition SOURCE ROOT is resolved by the canonical resolver `scripts/handoff-scaffold.py`, the same resolver Step 4 uses — so Step 1 and Step 4 cannot disagree. It detects mode via `rabbit-meta`'s `detect_mode` and returns the source root: in **plugin mode** the source root is the **parent of the `.rabbit` install** (the rabbit-root is the vendored `.rabbit/` tooling dir, so the project to decompose is its parent — never the `.rabbit/` workflow tooling itself); in **standalone mode** it is the repo root. Run the resolver and confirm the resolved `source_root` with the user before pointing Glob/Read at it:

<!-- example -->
```bash
python3 .claude/features/rabbit-decompose/scripts/handoff-scaffold.py --source-root
```

### Step 2 — Analyze and propose

Read the source material (Read/Grep/Glob for codebase scenarios; just read for spec scenarios). Produce a proposed feature list as a structured Markdown table:

```
| name | purpose | globs |
|------|---------|-------|
| feature-one | one-line purpose | `src/one/**/*` |
| feature-two | one-line purpose | `src/two/**/*` |
| ...
```

Show this table to the user. Below the table, briefly explain the boundaries you chose (1-2 sentences per feature for non-obvious cases).

**Guidelines for the proposal:**

- Each feature should be **functionally independent yet of manageable logical complexity** — small enough for a single TDD cycle to reason about, large enough to be a real boundary not a single file.
- Names are lowercase kebab-case, descriptive of the *what*, not the *how*.
- In existing-codebase scenarios, no two features may overlap (their globs must not match the same paths). The scaffolder will reject overlaps; pre-empt that here.
- Aim for 3-12 features as a starting point. Fewer than 3 probably doesn't need rabbit; more than 12 probably indicates over-decomposition.

### Step 3 — Iterate with the user

The user will respond with edits: add features, remove features, merge two into one, split one in two, adjust boundaries, rename. Update the proposal table and re-present.

Loop until the user explicitly accepts ("looks good", "go ahead", "ship it"). Do not proceed to scaffolding without explicit approval.

### Step 4 — Hand off to scaffold + spec-create

Once the user accepts:

**A. Scaffold.** Write the accepted list to a JSON file — `[{"name": "X", "globs": [...]}, ...]` — then run the hand-off orchestrator. It resolves the rabbit root, detects mode deterministically (reusing `rabbit-meta`'s `detect_mode`), authors the batch temp file with a script-owned timestamp, and dispatches the scaffolder on the mode-correct branch:

<!-- example -->
```bash
python3 .claude/features/rabbit-decompose/scripts/handoff-scaffold.py --features <accepted.json>
```

The script owns the mode branch: in **plugin mode** it runs the scaffolder in batch form (one `project-map.json` mutation); in **standalone mode** the batch form is plugin-only, so the script emits a `per-feature` plan. When the script reports `branch: "per-feature"`, invoke the scaffolder once per accepted feature, sequentially (they're cheap):

```
Skill("rabbit-feature-scaffold", args: the feature name)
```

**B. Seed specs.** For each accepted feature that has non-empty globs, invoke the spec-create skill:
```
Skill("rabbit-spec-create", args: "<feature-name> <glob1> <glob2> ...")
```
Run these calls **sequentially**, one per accepted feature, from the main session. Do **not** wrap them in `Agent(...)` calls. `rabbit-spec-create` is itself a subagent-dispatching skill: it internally dispatches the `rabbit-spec-creator` subagent via the Agent tool. Wrapping a subagent-dispatching skill inside an `Agent(...)` call produces an illegal two-level subagent nesting chain (decompose -> Agent level-1 -> rabbit-spec-creator level-2) that Claude Code does not support — the level-2 dispatch is blocked. Invoking `rabbit-spec-create` directly with `Skill(...)` keeps `rabbit-spec-creator` at level-1 (main session -> rabbit-spec-creator), which is the only supported path. For greenfield features with no globs, invoke once with just the name to produce a skeleton.

**C. Report.** Tell the user: `N` features scaffolded; `M` spec drafts produced; paths to each. Note that the spec drafts are *starting points* — the user reviews and edits before they're final.

## What you do NOT do

- Modify the user's source code. rabbit-decompose proposes; the user reviews; scaffolding happens; spec drafting happens. None of that touches source code.
- Skip the user-approval loop. Even if the proposal looks obvious, present it and wait for acceptance.
- Invoke rabbit-spec-update for the seeded drafts — those drafts are by definition new, not revisions. The user edits them directly when they review.
- Decide for the user whether a project should use rabbit at all. If the user is asking for a decomposition, assume they want one.

## Why interactive

The hard problem in feature decomposition isn't the analysis — it's the *boundary judgment*. Where one developer sees one feature, another sees three. The user's preferences and the codebase's history are inputs only the user has. The skill's job is to produce a reasonable starting proposal and then yield to the user's judgment, not to insist on its first answer.
