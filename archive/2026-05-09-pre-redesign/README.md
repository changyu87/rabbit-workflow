# Archive: 2026-05-09 Pre-Redesign

**Date archived:** 2026-05-09  
**Archived by:** Step 3 of the contract-feature redesign migration

## What is here

Three feature directories that were active in `.claude/features/` up to
2026-05-09, preserved verbatim before deletion from the live tree:

| Directory | Original path |
|-----------|---------------|
| `features/vet/` | `.claude/features/vet/` |
| `features/breeder/` | `.claude/features/breeder/` |
| `features/subagent-policy-injection/` | `.claude/features/subagent-policy-injection/` |

## Why archived

These features implemented the first-generation rabbit-workflow agent model:

- **vet** — the `rabbit-vet` quality-gate subagent and its prompt templates.
- **breeder** — the `rabbit-breeder` implementation subagent and its templates.
- **subagent-policy-injection** — the per-dispatch policy-block injection
  mechanism (R6), including `policy-block.sh` and its bundled templates.

The redesign centralises all cross-agent contracts and template references
under `.claude/features/contract/`, eliminating the private per-feature
template copies that these directories maintained.  The policy-block mechanism
is superseded by the contract feature's unified dispatch protocol.

## Deprecation criterion (met)

Archived when the `contract` feature absorbed all responsibilities previously
split across vet, breeder, and subagent-policy-injection, and the live
`.claude/features/` tree was verified clean of private template copies.

## Do not restore

These directories are read-only historical artifacts.  Any future need for the
capability they encoded should be expressed through the `contract` feature or
a new versioned replacement — not by restoring these files.
