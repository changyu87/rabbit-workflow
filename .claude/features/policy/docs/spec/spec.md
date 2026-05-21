---
feature: policy
version: 1.5.0
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
5. `test/test-coding-rules-numbering.py` (formerly
   `test-backlog003.py`, renamed in BACKLOG-14 for filename-convention
   compliance per Inv 9) MUST carry a header comment naming its
   end-of-life criterion: the file documents the BACKLOG-003 era rule
   numbering migration and may be retired once `test-policy-invariants`
   covers the same numbering checks. (BACKLOG-11, rename BACKLOG-14)

6. **Read-before-Edit principle (BACKLOG-13).** `coding-rules.md` MUST
   include a general principle requiring every actor that edits an
   existing file to first Read it in the same session. The principle
   is invariant text — not the wording of any specific tool — and
   propagates the lesson of rabbit-feature Inv 35 from one skill to
   every subagent via the policy preamble injected by
   `dispatch-tdd-subagent.py`. The canonical phrasing MUST express:
   (a) read before editing existing files, (b) read the surrounding
   module before writing alongside existing code, (c) edits made
   without reading are speculative. A regression test
   (`test-rule-files-content.py` or successor) MUST assert the
   principle's canonical phrase is present in `coding-rules.md`.

7. **Test file convention (BACKLOG-13).** `test-policy-invariants.py`
   (non-versioned) is the canonical name for the spec-conformance
   test suite. The legacy versioned forms
   (`test-policy-invariants-v1-X-Y.py`) MUST NOT be reintroduced —
   they triggered a rename cycle on every spec version bump
   (BACKLOG-13 retired the pattern). `test-files-exist.py` MUST NOT
   exist (its coverage is subsumed by `test-policy-invariants.py`).

8. **Historical-fixes regression guard (BACKLOG-14, F5).**
   `test/test-policy-bug-fixes.py` is a documentary regression guard
   for closed historical tickets (POLICY-BUG-1/2/7/9/18/19,
   POLICY-BACKLOG-1/2/5/6/9). Its docstring MUST state a concrete,
   observable retirement criterion: the file MUST be retired once
   `test-policy-invariants.py` contains equivalent assertions for
   every ticket the kitchen-sink file covers. A retirement-watch test
   (`test-historical-fixes-retirement.py` or equivalent) MUST fire
   (FAIL) when subsumption is observable via `# Subsumes: POLICY-...`
   marker comments in `test-policy-invariants.py` — that failure
   signals it is safe (and required) to delete
   `test-policy-bug-fixes.py` and the watch test together. The
   previous open-ended criterion ("when each bug/backlog has its own
   targeted test or is closed") is REMOVED — it never fires because
   the tickets are already closed.

9. **Test filename convention (BACKLOG-14, F6).** All test files
   under `test/` MUST use behavior-first names (e.g.,
   `test-coding-rules-numbering.py`, `test-no-stale-imports.py`).
   Ticket IDs (POLICY-BUG-N, POLICY-BACKLOG-N) MUST appear only in
   docstring headers as `Traces: POLICY-...` lines, never embedded in
   filenames. The ID-first forms `test-POLICY-N-*.py`,
   `test-backlogNNN.py`, and `test-backlog-N-M.py` MUST NOT be
   reintroduced; they triggered rename churn on every wave of ticket
   cleanup. Exception: `run.py` is the test harness, not a test.

## Out of Scope

- Generating policy output on demand — consumers read files directly.
- Modifying files in any other feature.
