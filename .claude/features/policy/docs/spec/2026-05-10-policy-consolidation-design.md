# Policy Consolidation Design — 2026-05-10

## Goal

Strip operational carve-outs (exception clauses, enforcement cross-references,
script-path annotations) from the policy files so that policy is purely
instructive and descriptive. Scripts enforce exceptions at runtime; policy
states principles.

## Scope

One file changes: `workflow-rules.md`. The other three files
(`philosophy.md`, `spec-rules.md`, `coding-rules.md`) are already clean
after the prior restructure session.

## Approach

**Approach B — Full consolidation.** Remove exception blocks verbatim and
trim sentences that reference enforcement mechanisms. R1–R9 index entries
compressed to single-line rule statements; script paths dropped.

Rejected alternatives:
- **A (surgical strip only)**: Leaves operational noise like "enforced by
  scope-guard" — stops halfway.
- **C (split into two files)**: Adds a file to maintain; user intent is
  removal, not relocation.

Also rejected: removing R1–R9 from policy entirely. Agents need the rules
proactively to avoid violations; enforcement scripts are reactive gates only.

## Changes to `workflow-rules.md`

### 1. Section: Subagent-driven by construction

**Remove:** "This is not a convention — it is enforced by scope-guard (R8)
and the sentinel check (R6)."

Rationale: Enforcement detail, not principle.

### 2. Section: Main Session Is a Dispatcher, Not an Implementer

**Remove:** Entire `**Exceptions (direct calls allowed without subagent):**`
block (three bullet points).

Rationale: Exceptions belong in the scripts. Policy states the rule;
`file-bug.sh`, scope-guard, and `bug-status.sh` encode the carve-outs
mechanically.

### 3. Section: Full TDD on every feature touch

**Remove:** "Exception: metadata-only writes (bug filing via file-bug.sh,
backlog filing via file-backlog-item.sh) require schema compliance only —
the scripts enforce format at write time. No TDD cycle needed for bookkeeping
artifacts."

Rationale: Same as above. `tdd-step.sh` and scope-guard enforce this
distinction at runtime.

### 4. Section: Hard rules index (R1–R9)

**Compress** each entry from a multi-sentence paragraph with script path to
a single-line rule statement. Script paths removed.

| Rule | Compressed statement |
|------|----------------------|
| R1 | Branch per feature; never commit directly to main. |
| R2 | Use Opus for brainstorm, spec, plan, design, and architect subagents. |
| R3 | Tests are end-to-end and non-interactive — no `read` or `select`. |
| R4 | TDD state transitions go through `tdd-step.sh` only. |
| R5 | Features live anywhere; the same discipline applies everywhere. |
| R6 | Every Agent dispatch prepends the canonical policy block. |
| R7 | Vet every bug before closing — triage first, then close. |
| R8 | Every feature touch runs full TDD. |
| R9 | Project-level contract wins over rabbit contract at conflict. |

## Resulting structure of `workflow-rules.md`

```
# Workflow Rules
## Subagent-driven by construction        ← principle only, no enforcement note
## Main Session Is a Dispatcher           ← dispatch patterns, no exceptions block
## Full TDD on every feature touch        ← rule only, no exception sentence
## Token/compliance tradeoff              ← unchanged
## Hard rules index (R1–R9)              ← one-liner per rule, no script paths
## Cross-component handoffs use schemas   ← unchanged
```

## Files not changed

| File | Reason |
|------|--------|
| `philosophy.md` | Pure principles, no operational noise |
| `spec-rules.md` | Clean after H2 promotion |
| `coding-rules.md` | Clean after H2 promotion and rule-5 removal |

## Testing

Assertions to add to `test-policy-consolidation.sh`:
- `workflow-rules.md` does NOT contain the word 'Exception'
- `workflow-rules.md` does NOT contain 'enforced by scope-guard'
- `workflow-rules.md` does NOT contain 'check-no-main-edits' (no script paths)
- Each R1–R9 line fits on a single line (no embedded multi-line bodies)

## Out of scope

- Removing R1–R9 from policy entirely
- Changes to enforcement scripts
- Changes to `spec-rules.md`, `coding-rules.md`, or `philosophy.md`
