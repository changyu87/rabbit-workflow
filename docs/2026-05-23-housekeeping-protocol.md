---
date: 2026-05-23
status: active
authors: Changyu, Claude (backstop)
purpose: protocol for housekeeping waves to reach merge-confidence on `feature/meta-contract-api-libraries`
---

# Housekeeping Protocol — Plan B → Main Merge Readiness

## Purpose

`feature/meta-contract-api-libraries` carries Plan A (meta-contract foundation) and Plan B (four API libraries). It is not yet merge-ready because:

1. The leftover design Plans C, D, E, F have not been executed
2. Plans A and B were implemented without `rabbit-feature-touch` or the rabbit `tdd-subagent` (the workflow's own TDD machinery)
3. Existing features (rabbit-feature, tdd-subagent, contract, rabbit-cage, others) have not been audited against the post-meta-contract architecture
4. Several feature specs likely carry historical/documentation burden incompatible with the audit criteria defined below

This protocol defines the sequenced work to reach merge-confidence: finish the design's leftover plans, then run housekeeping audit waves on existing features, then execute Plan F cleanup. Each wave runs autonomously in its own workspace; the backstop (Claude in ws42) prepares workspaces + prompts, the human pastes, the session returns a structured report.

## Branch and Workspace Discipline

- All work lands on `feature/meta-contract-api-libraries` (the integration branch).
- Each wave runs in its own clone at `/home/cyxu/workflow-dev/rabbit-marathon/wsNN/`.
- Each wave pushes its commits to the integration branch on origin.
- Existing open B/B items remain open at merge time — the protocol does not require closing them.
- Workspaces are sequential, not parallel, to avoid push-conflict on the shared branch (parallelization is possible but adds merge coordination cost; defer unless cycle time forces it).

## Wave Sequence

| # | Workspace | Scope | Discipline | Notes |
|---|---|---|---|---|
| C | wsNN | Plan C — rabbit-cage dispatcher rewrite | superpowers TDD, session scope override | Shrinks rabbit-cage spec from ~20K to ~5K tokens |
| D | wsNN | Plan D — rabbit-config feature scaffolding | superpowers TDD, session scope override | New feature; hosts `/rabbit-config` skill + runtime alerts |
| 1 | wsNN | Wave 1 — rabbit-feature audit (spec/code/tests) | superpowers TDD, session scope override | Includes folding rabbit-feature-scope/ into rabbit-feature as a surfaced skill |
| 2 | wsNN | Wave 2 — rabbit-config audit (inserted) | superpowers TDD, session scope override | Inserted on 2026-05-23 after Plan D shipped with multiple piecemeal bugs (BUG-1 twice, BUG-2, false-alarm BUG-100). Consolidates rabbit-config to "golden" before tdd-subagent audit, since rabbit-feature-touch (the tdd-subagent's caller) consumes rabbit-config's human-approval-bypass configurable. Wave numbering for subsequent waves shifted up by one from the original protocol. |
| 3 | wsNN | Wave 3 — tdd-subagent audit | superpowers TDD, session scope override | Hardens the rabbit TDD machinery before relying on it. Was originally Wave 2. |
| 4 | wsNN | Wave 4 — rabbit-feature consolidation re-audit | rabbit's tdd-subagent + rabbit-feature-touch | First validation of the now-golden tdd-subagent against rabbit-feature. Was originally Wave 3. |
| E.* | wsNN per feature | Plan E — per-feature meta-contract migration (one workspace per feature) | rabbit's tdd-subagent + rabbit-feature-touch | Each feature declares its MANIFEST/RUNTIME/CONFIGURATION in feature.json |
| 5+ | wsNN per feature | Housekeeping audit for each remaining feature | rabbit's tdd-subagent + rabbit-feature-touch | Standard discipline restored. Was originally 4+. |
| F | wsNN | Plan F — cleanup: drop build-contract.json, drop rabbit-print-messages.json, drop named wrappers | rabbit's tdd-subagent + rabbit-feature-touch | Breaking cleanup; only safe after every feature is migrated |

Plan E is intentionally separate from the housekeeping audit waves (per Q&A decision): one workspace per feature for the meta-contract migration, distinct from the audit that made the feature "golden." This preserves clean separation of concerns and gives each PR-stage commit a single purpose.

## Audit Criteria

### Spec audit criteria (apply to every wave that touches a `docs/spec/spec.md`)

A spec is golden when ALL of these hold:

1. **Current-design only.** The spec describes the system as it currently is. No "this used to be X, now Y" passages, no historical migration prose, no chronological narration.
2. **No documentation burden.** No "per BUG-123" / "per BACKLOG-456" references in spec body. Rationale tied to a bug or backlog ID is recorded in the bug/backlog item itself or in the commit message, not in the spec.
3. **No retired-feature references** unless the retired feature's name still appears in the active surface (e.g., as a tombstone path that another invariant pins).
4. **Strict, consistent vocabulary.** Same word for same thing across the spec. No synonym drift ("hook" vs "handler" vs "callback" for the same concept).
5. **Confined.** Each invariant scopes one obligation. Compound invariants ("X MUST do A AND B AND also C unless Z") get split.
6. **Precise.** Quantifiable assertions where applicable (exact enum sets, exact file paths, exact return shapes).
7. **Focused.** No commentary on adjacent features or speculative future work. Out-of-scope items belong in B/B, not in the spec.
8. **Clear.** A reader who never saw the codebase can determine, from the spec alone, whether the implementation conforms.
9. **Well-written.** No grammatical drift, no incomplete sentences, no ASCII-art-as-substitute-for-prose.

### Test audit criteria (apply to every wave that touches a feature's `test/`)

A test suite is golden when ALL of these hold:

1. **Spec-only coverage.** Every test traces to a spec invariant. If a test exercises behavior not in the spec, either the spec gains an invariant or the test is removed.
2. **No precautionary tests.** No "just in case" tests for behaviors the spec does not promise. Defensive checks live in the production code, not in defensive test cases for hypotheticals.
3. **Minimal sufficient set.** For each invariant, the fewest tests that cover it (positive + boundary + negative cases as the invariant warrants). Redundant tests collapse.
4. **Bounded runtime.** No test takes longer than necessary. Long-running tests get justified or replaced with smaller fixtures.
5. **Deterministic.** No flakiness, no timing-dependent assertions, no environment-dependent outputs that vary across runs.
6. **Isolated.** Each test cleans up after itself (tempdir, marker files, etc.); test order does not matter.

When applying the test audit criteria, the wave SHOULD ask explicitly: "Do I really need this many tests for this invariant?" If reducing test count loses coverage of a spec invariant, the reduction is wrong. If reducing test count loses coverage of NON-spec behavior, the reduction is correct.

### Functional code audit criteria

A feature's functional code is golden when:

1. **Implements every spec invariant.** No spec invariant is unimplemented or only partially implemented.
2. **No behavior beyond the spec.** Code that does more than the spec promises is either:
   - Removed (if it's dead) OR
   - Surfaced as a new spec invariant (if it's load-bearing)
3. **Follows the rabbit-cage Tech Stack convention** (Python 3 stdlib only unless explicitly approved).
4. **Code conforms to spec-rules.md and coding-rules.md** (already loaded as @-imports in CLAUDE.md).

## B/B Filing Protocol

Any wave that detects an issue OUTSIDE its declared scope MUST file a B/B item via the `rabbit-file` skill rather than fixing the issue itself. This preserves wave scope discipline and prevents one wave from sprawling into unrelated cleanup.

Per-wave protocol:

1. While auditing, maintain a list of "alongside findings" — issues not in current scope.
2. Before completing the wave, invoke `rabbit-file` (file-item.py) to create a bug or backlog entry for each finding, with:
   - Type: `bug` if the finding is a defect (code/spec/test mismatch with intended behavior); `backlog` if it's a future improvement or architectural concern.
   - Feature: the feature the finding belongs to (NOT the current wave's feature).
   - Title and description per the existing rabbit-file conventions.
   - Priority: best-judgement (low/medium/high/critical).
3. Report the filed B/B IDs in the wave's final output.

The B/B items live on the `bug-backlog-files` branch (managed by rabbit-file), not on the integration branch.

**B/B operations do NOT require a per-feature scope marker.** rabbit-file writes to the `bug-backlog-files` branch via its own worktree (`.claude/tmp/bug-backlog-files-<pid>/`), never to feature directories on the integration branch. The scope-guard hook is therefore not triggered by `file-item.py` / `item-status.py` / `list-items.py` invocations from within a wave, regardless of which feature's scope marker (if any) is active. Confirmed by Wave 9.

## Scope-Guard Mechanism

Different wave types use different scope-guard handling:

- **Plan C, Plan D, Wave 1, Wave 2** (no `rabbit-feature-touch`): write `.rabbit-scope-override` with content `session` at wave start. Revoke at wave end via `python3 .claude/features/rabbit-cage/scripts/scope-guard-on.py`. The session override broadly permits writes for the duration; tight scope discipline is enforced by wave goals + the audit criteria, not by scope-guard.
- **Wave 3, Plan E.*, Wave 4+, Plan F** (use `rabbit-feature-touch`): no scope override needed. `rabbit-feature-touch` sets per-feature `.rabbit-scope-active-<feature>` markers per its protocol, which the scope-guard honors automatically. The wave operates only within `rabbit-feature-touch`'s standard discipline.

## Merge-Back Ritual (Wave 5+ Integration)

Waves that use `rabbit-feature-touch` produce their commits on a feature branch (e.g. `feat/<feature>-wave<N>-audit`) per the touch protocol's Step 2. Integrating those commits into the housekeeping branch (`feature/meta-contract-api-libraries`) requires a fast-forward merge from the backstop workspace, which is blocked by the `Bash(git merge *)` deny rule in `.claude/settings.json`.

The deny rule does double duty: it protects `main` from accidental direct merges AND it forces this manual merge-back ritual so the backstop is always the one stitching wave outputs into the integration branch. The two intents are not separable from the rule itself; the ritual below is the protocol-level alignment.

The backstop ritual (mirrors what Wave 5 and Wave 8 followed):

1. Ask the human for an override mode (one-time or session) — explicit confirmation per scope-guard's discipline.
2. Edit `.claude/settings.json` to drop `Bash(git merge *)` from `permissions.deny`.
3. `git fetch origin feat/<feature>-wave<N>-audit:wave<N>-local` (or fetch from the wave's local repo if not yet on origin).
4. `git merge --ff-only wave<N>-local`.
5. `git push origin feature/meta-contract-api-libraries`.
6. Restore the deny rule (sync-check auto-restores on next Stop via the publish loop, but a deliberate `git checkout -- .claude/settings.json` after push is equally fine and immediate).
7. Revoke session-mode override via `scope-guard-on.py` if it was a session override.
8. Delete the feature branch locally and on origin once integrated.

## Invariant Renumber vs Gaps

When a wave retires invariants, the surviving invariants either get renumbered (closing the gaps) or stay where they are (leaving gaps in the active set). Both have costs:

- **Renumber** cascades through cross-feature references (tests, other specs, comments) — typical blast radius ~25 cross-references per retired invariant.
- **Preserve gaps** grows the "intentional gaps" inventory in `CHANGELOG.md` and makes the active set harder to scan.

**Rule**: preserve gaps when **≤5** retirements in a single wave; renumber when **>5** OR when gap density makes the active set hard to navigate (waves with many retired invariants in close numeric proximity are candidates for renumber even under 5). The contract feature's `check_invariant_monotonic_order` enforcement requires strictly-increasing numbers within each `## Invariants` / `### Invariants` section, NOT contiguous — gaps are permitted by the checker.

When preserving gaps, the wave MUST tombstone each retired invariant in `CHANGELOG.md` with its historical number, a one-line "what it asserted + why retired" summary, and the backlog ID that drove the retirement.

## Workspace Preparation (backstop's responsibility)

For each wave the backstop:

1. Clones the integration branch into `wsNN`:
   ```
   git clone https://github.com/changyu87/rabbit-workflow.git /home/cyxu/workflow-dev/rabbit-marathon/wsNN
   git -C /home/cyxu/workflow-dev/rabbit-marathon/wsNN checkout feature/meta-contract-api-libraries
   ```
2. Runs a smoke test to confirm the suite is green at the starting point.
3. Drafts the wave-specific prompt (scope, discipline, deliverables, output format) and gives it to the human to paste.

## Prompt Skeleton

Each wave prompt MUST contain these sections:

```
WAVE NAME AND NUMBER

Working directory: /home/cyxu/workflow-dev/rabbit-marathon/wsNN
Branch: feature/meta-contract-api-libraries

GOAL: <one-sentence statement of what this wave accomplishes>

SCOPE: <which feature(s) this wave may touch>

ANTI-SCOPE: <features and files this wave MUST NOT touch>

DISCIPLINE: <superpowers TDD or rabbit-feature-touch + tdd-subagent>

SCOPE-GUARD: <session override or feature-touch>

REFERENCE DOCS:
- docs/superpowers/specs/2026-05-23-housekeeping-protocol.md (this document — read it first)
- docs/superpowers/specs/2026-05-23-meta-contract-architecture-design.md
- <plan or design docs specific to this wave>

AUDIT CRITERIA: apply the spec / test / code criteria from the housekeeping
protocol. Treat them as binding rather than aspirational.

B/B PROTOCOL: anything detected outside SCOPE gets filed via rabbit-file
skill before wave completion. Do NOT expand scope to fix alongside findings.

OUTPUT FORMAT: see below.
```

## Output Format (what each wave returns)

The wave session reports:

1. **Status**: `golden` | `incomplete` | `blocked` | `escalated`
2. **Commit list**: SHAs and one-line summaries, in chronological order
3. **Files changed**: counts (created / modified / deleted) and a brief categorization
4. **Test suite state**: total tests + pass count + any added/removed
5. **B/B items filed**: ID list with one-line summary per item
6. **Audit verdict per criterion**: pass/fail with brief justification per spec/test/code criterion
7. **Open questions for backstop**: anything that needs human/backstop decision
8. **Suggested next wave**: per the housekeeping sequence

Anything more is welcome but the above is the minimum.

## Merge Readiness Criteria

The integration branch is merge-ready when:

1. All leftover design plans (C, D, E.*, F) have landed
2. All housekeeping audit waves (1, 2, 3, 4+) have returned `golden`
3. Full contract + all-feature test suite passes
4. Each feature's spec, code, and tests meet the audit criteria
5. No `incomplete` or `blocked` wave outstanding
6. Open B/B items are acceptable to carry forward (per protocol they remain open at merge time)

When all six hold, the integration branch is PR'd to main.

## Protocol Versioning

This document is the source of truth for the housekeeping protocol. Changes to wave sequence, audit criteria, scope-guard mechanism, or output format require updating this document and committing the change to `feature/meta-contract-api-libraries`.
