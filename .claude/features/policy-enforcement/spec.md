# policy-enforcement

> Source of truth: [`feature.json`](./feature.json).
> Implementation files (NOT in this directory):
> - Constitution principles: [`../../philosophy.md`](../../philosophy.md)
> - Construction rules: [`../../work-guide.md`](../../work-guide.md)
> - Anchor file with `@`-imports: [`/CLAUDE.md`](../../../CLAUDE.md)

## Purpose

Owns the policy anchor — the three documents that govern how every agent
in the rabbit workflow operates:

1. **`philosophy.md`** — Three principles (Machine First, Bounded Scope,
   Designed Deprecation). Principle-level. Should change rarely.
2. **`work-guide.md`** — Construction rules (Tool-Choice Tier, Schemas and
   Contracts, Lifecycle and Ownership), code-editing discipline (the four
   Karpathy sections), and Hard Rules (Part III). Operational. Changes
   when new disciplines are formalized.
3. **`CLAUDE.md`** — The repo-root anchor file that `@`-imports
   `philosophy.md` and `work-guide.md` so they are visible to Claude Code
   on every session. Tiny on its own; important for what it points at.

This feature is a **documentation overlay** over these three pre-existing
artifacts. It does not move them. It records the contract that they exist
with their load-bearing sections intact, and ships a test that fails if
any required section disappears.

## Why this is a feature

A policy that nobody enforces is decoration. By treating the policy anchor
as a feature with tests, the workflow gains:

- A test runner that can be invoked in CI to fail builds if the
  constitution drifts (e.g. a Karpathy section gets accidentally deleted).
- An owner and a deprecation criterion for the policy itself, so the
  question "who maintains this and when does it sunset" has a recorded
  answer.
- A schema-conformant landing pad for the policy, on equal footing with
  the other features.

## Required sections (load-bearing)

`philosophy.md` MUST contain (matched as substrings, case-sensitive):

- "Machine First"
- "Bounded Scope"
- "Designed Deprecation"

`work-guide.md` MUST contain:

- "Tool-Choice Tier"
- "Schemas and Contracts"
- "Lifecycle and Ownership"

`CLAUDE.md` MUST `@`-import both `philosophy.md` and `work-guide.md`.

These are the canonical anchors. If any disappears, the policy is broken —
fix it before merging.

## Auto-refresh interaction

The `auto-refresh` feature periodically re-injects the contents of the
files that `CLAUDE.md` `@`-imports. Adding a new policy file means:

1. Add it under `.claude/`.
2. Add an `@./.claude/<file>.md` line to `CLAUDE.md`.
3. The auto-refresh hook picks it up automatically on the next refresh.

No code changes required to bring a new policy file into the rotation.

## What this feature does NOT define

- The mechanics of refresh — that is `auto-refresh`.
- The layout / schema of features — that is `feature-skeleton`.
- The lockdown rules in `settings.json` — that is `claude-write-lockdown`.

Bounded scope: this feature owns the **policy anchor's existence and
shape**, not its content evolution (content edits are normal PRs against
`philosophy.md` / `work-guide.md`).

## Tests

`test/run.sh` (13 cases):

- t1–t3: existence of philosophy.md, work-guide.md, CLAUDE.md.
- t4: each load-bearing principle string in philosophy.md.
- t5: each load-bearing section title in work-guide.md.
- t6: CLAUDE.md `@`-imports both files.
- t7–t9: file size sanity (catches accidental truncation).
