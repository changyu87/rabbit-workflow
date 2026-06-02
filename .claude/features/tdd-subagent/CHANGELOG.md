---
feature: tdd-subagent
owner: rabbit-workflow team
deprecation_criterion: when the tdd-subagent spec's invariant numbering is folded into a structured schema-tracked log
---

# tdd-subagent — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `docs/spec/spec.md` and have since been retired. Spec.md carries inline tombstones (one-line `*(Retired — see CHANGELOG.md, <backlog-id>.)*` markers); the full retirement rationale lives here.

Each entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the backlog ID that drove the retirement.

## Renumber and gap-preservation events

- **TDD-SUBAGENT-BACKLOG-19 (drop redundant SPEC-READ + HUMAN-APPROVAL steps):** Spec.md surviving invariants are NOT renumbered. This backlog retires four invariants (Inv 5, 13, 25, 26) and preserves the resulting numbering gaps at those positions rather than re-flowing the surviving invariants. Total retirement count (4) is within the housekeeping protocol's renumber-vs-gaps threshold (≤ 5); the cross-reference cost of a cascade rewrite outweighs the gap cost. Inv 4 (CLI flag set) and Inv 8 (step-banner list) were rewritten in place — they keep their numbers because the surrounding invariants still reference those numbers.

## Retired invariants

### Inv 5 — boolean flag vocabulary (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that boolean values for `--human-approval-gate` are exactly `true` or `false` (no `enabled`/`disabled`, `yes`/`no`, etc.). Retired alongside the `--human-approval-gate` flag itself: the flag was removed from the argparse surface in `dispatch-tdd-subagent.py`, so there is no boolean vocabulary left to constrain. The wider boolean-vocabulary convention (true/false only) is still observed by other rabbit features that accept boolean flags, but it is not specific to tdd-subagent any more. Equivalent assertion: spec Inv 4 (flag set excludes `--human-approval-gate`), `test/test-cli-invocation.py` (asserts argparse rejects `--human-approval-gate true` and `--human-approval-gate false` as unrecognized arguments).

### Inv 13 — SPEC-READ diff target (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that the assembled prompt's STEP 1 SPEC-READ section runs `git diff HEAD~1 -- <feature_dir>/docs/spec/`. The STEP 1 SPEC-READ section was deleted from the prompt template altogether: spec context is already interpolated verbatim into the prompt via `{spec_content}`, so an in-subagent diff against HEAD~1 was redundant (the subagent has the post-edit spec in front of it; the dispatcher's spec-authoring step produced the committed baseline). With the SPEC-READ section gone, there is no diff command for any test to assert.

### Inv 25 — `--human-approval-gate true` branch (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that with `--human-approval-gate true` (default), the assembled prompt contains a STEP 2 HUMAN-APPROVAL section instructing the subagent to invoke `Skill("superpowers:writing-plans")`, present the implementation summary to the user, and wait for explicit approval before STEP 3 LOCK. Retired because subagents have no user-interaction tools — the "wait for explicit approval" instruction was dead code (subagents cannot prompt the user, and the dispatcher's Step 4 HUMAN-APPROVAL gate is the real approval surface). The STEP 2 HUMAN-APPROVAL section was deleted from the prompt template. The `--human-approval-gate` flag was removed from the argparse surface alongside.

### Inv 26 — `--human-approval-gate false` branch (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that with `--human-approval-gate false`, the assembled prompt's STEP 2 HUMAN-APPROVAL section is a one-line stub stating the step is skipped. Retired with Inv 25 — the STEP 2 HUMAN-APPROVAL section no longer exists in either branch (there is no longer a flag to branch on), so there is no stub form to assert.
