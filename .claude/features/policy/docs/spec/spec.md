---
feature: policy
version: 1.4.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native subagent-policy injection point
status: active
---

# policy — Spec

## Purpose

Owns the three canonical rule files fed to every subagent dispatch.

## Surface

- `.claude/features/policy/philosophy.md`
- `.claude/features/policy/spec-rules.md`
- `.claude/features/policy/coding-rules.md`

## Tech Stack

- All runtime scripts and test harnesses are Python 3. No `.sh` files are present.

## Invariants

1. All three rule files (`philosophy.md`, `spec-rules.md`, `coding-rules.md`) exist and are non-empty.
2. `workflow-rules.md` does not exist.
3. No `.sh` files exist anywhere within the feature directory.
4. `coding-rules.md` Section 3 ("Surgical Changes") MUST clarify that
   "uncommitted" includes BOTH staged and unstaged work from the
   current agent session: if YOUR changes (staged or unstaged) made an
   import / variable / function unused in the current session, remove
   it; once a change is committed (even within the same session) it
   counts as pre-existing — mention it, don't delete it. (BACKLOG-12)
5. `test/test-backlog003.py` MUST carry a header comment naming its
   end-of-life criterion: the file documents the BACKLOG-003 era rule
   numbering migration and may be retired once a wider
   `test-policy-invariants-*` test covers the same numbering checks.
   (BACKLOG-11)

## Out of Scope

- Generating policy output on demand — consumers read files directly.
- Modifying files in any other feature.
