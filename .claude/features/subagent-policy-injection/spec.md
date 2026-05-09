# subagent-policy-injection

> **Note:** LLM-prose view (machine-targeted, like everything in rabbit).
> Structured source of truth is [`feature.json`](./feature.json).

## Purpose

Subagent invocations are NOT covered by the auto-refresh hook (which fires
on the parent's `UserPromptSubmit` events, not on tool calls inside a
subagent). They also don't auto-load `CLAUDE.md`. So a subagent only sees
its own agent-definition system prompt + the dispatcher's prompt — and
nothing from the workflow constitution.

This feature ships the **canonical policy block** that every dispatcher
must prepend to every Agent dispatch. Concatenates `philosophy.md`,
`work-guide.md`, and any related rule files into a single block framed
with a hard-command tone (MANDATORY / NOT optional / STOP / constitution
violation). Universal coverage: rabbit's own subagents (`rabbit-breeder`,
`rabbit-vet`) AND Claude's built-in ones (`Plan`, `Explore`,
`code-reviewer`, `general-purpose`, etc.).

The dispatcher is the discipline point. Whoever calls `Agent({...})`
captures the script's stdout and prepends it to the prompt field.

## How it's used

```bash
# Default: philosophy + work-guide only
POLICY=$(bash .claude/features/subagent-policy-injection/scripts/policy-block.sh)
# In the Agent tool prompt:
#   prompt: "$POLICY\n\nSCOPE: <scope>\noperation: ...\n..."

# With related rule files for the dispatched task:
POLICY=$(bash .claude/features/subagent-policy-injection/scripts/policy-block.sh \
    --include .claude/features/feature-skeleton/spec.md \
    --include .claude/features/tdd-state-machine/spec.md)
```

## Why hard-command tone

LLMs are sensitive to framing. The block opens with:

```
═══════════════════════════════════════════════════════════════════════════════
MANDATORY POLICY — READ THIS BEFORE ANY ACTION
═══════════════════════════════════════════════════════════════════════════════

You are operating within the rabbit workflow. The following policy files are
NOT optional reading. They govern every choice you make in this invocation.
Failure to comply is a constitution violation.

If you have not yet internalized these principles, STOP and read them now
before doing anything else. ...
```

The visual delimiter (heavy box-drawing) plus explicit mandate language is
designed to raise attention even when the subagent's context window is
crowded with task data. Tested invariants (test-policy-block.sh):

- All three philosophy principles present (Machine First, Bounded Scope,
  Designed Deprecation).
- All three work-guide section titles present (Tool-Choice Tier, Schemas
  and Contracts, Lifecycle and Ownership).
- ≥ 3 of 4 hard-tone tokens present (MANDATORY, NOT optional, STOP,
  constitution).
- Block opens and closes with visual banners.

## Honest scope notes

- **Dispatcher discipline, not harness enforcement.** Claude Code does not
  expose an Agent-tool `PreToolUse` hook (only `Write|Edit|Bash` etc.), so
  there is no way to verify at the harness level that an Agent dispatch
  included the policy block. PR review and the `rabbit-breeder` /
  `rabbit-vet` system prompts (which mention they expect the block to
  precede their task instructions) are the backstop.

- **No subagent-side check.** A receiving subagent doesn't strictly know
  whether the prompt it got began with the canonical block — it just sees
  the full prompt text. Subagent-side enforcement would require parsing
  the prompt for the banner, which agents could do but adds little (a
  malicious dispatcher could fake the banner anyway).

- **The block does not solve drift within long subagent invocations.** It
  only ensures the policy is present at the START of the invocation.
  In-invocation drift is the gap discussed in the auto-refresh spec; the
  honest mitigation today is keeping subagent invocations short.

- **Related rule files are dispatcher-chosen via `--include`.** No global
  list. Different dispatches need different rules (a feature-creating
  breeder needs `feature-skeleton/spec.md`; a bug-triaging vet needs
  `bug-filing/spec.md`). The dispatcher decides. Defaults to philosophy +
  work-guide only.

## Companion rule

Per `hard-rules` R6 (added in PR #8 amendment):

> Every Agent dispatch prepends the canonical policy block (output of
> `subagent-policy-injection/scripts/policy-block.sh`) to the prompt
> field. Universal: rabbit's own subagents AND Claude's built-in ones.

## What this feature does NOT define

- The auto-refresh mechanism for the main session — that is `auto-refresh`.
- The Agent dispatch protocol for `rabbit-breeder` (SCOPE marker, etc.) —
  that is `breeder`. The policy block is prepended on TOP of that protocol;
  they compose.
- A subagent-side parser that verifies the block was received — out of
  scope; trust + PR review.

## Tests

`test/run.sh` runs `test-policy-block.sh` (10 cases):

- p1: outputs non-empty (>100 bytes)
- p2: contains all three philosophy principles
- p3: contains all three work-guide section titles
- p4: ≥ 3 of 4 hard-command tokens (MANDATORY, NOT optional, STOP, constitution)
- p5: `--include <path>` inserts file content with a filename divider
- p6: missing `--include` path errors clearly
- p7: output is plain text (no binary garbage)
- p8: multiple `--include` flags compose
- p9: output opens with a visual hard banner
- p10: output closes with an END banner
