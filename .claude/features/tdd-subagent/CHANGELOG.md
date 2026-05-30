---
feature: tdd-subagent
owner: rabbit-workflow team
deprecation_criterion: when the tdd-subagent spec's invariant numbering is folded into a structured schema-tracked log
---

# tdd-subagent — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `docs/spec/spec.md` and have since been retired. Spec.md carries inline tombstones (one-line `*(Retired — see CHANGELOG.md, <backlog-id>.)*` markers); the full retirement rationale lives here.

Each entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the backlog ID that drove the retirement.

## Renumber and gap-preservation events

- **Phase 7c (drop --linked-item / --linked-items / --item-type CLI surface):** Spec.md surviving invariants are NOT renumbered. This cycle retires four invariants (Inv 6, 19, 20, 30) and simplifies one (Inv 21 — `closed_items` is now always an empty list but the field is retained on the HANDOFF schema for forward compatibility per Inv 22). Numbering gaps at positions 6, 19, 20, 30 are preserved rather than re-flowing the surviving invariants. Total retirement count (4) is within the housekeeping protocol's renumber-vs-gaps threshold (≤ 5); the cross-reference cost of a cascade rewrite outweighs the gap cost. Inv 3 (exit codes), Inv 4 (CLI flag set), and Inv 45 (prompts section slots) were rewritten in place — they keep their numbers because the surrounding invariants still reference those numbers.
- **TDD-SUBAGENT-BACKLOG-19 (drop redundant SPEC-READ + HUMAN-APPROVAL steps):** Spec.md surviving invariants are NOT renumbered. This backlog retires four invariants (Inv 5, 13, 25, 26) and preserves the resulting numbering gaps at those positions rather than re-flowing the surviving invariants. Total retirement count (4) is within the housekeeping protocol's renumber-vs-gaps threshold (≤ 5); the cross-reference cost of a cascade rewrite outweighs the gap cost. Inv 4 (CLI flag set) and Inv 8 (step-banner list) were rewritten in place — they keep their numbers because the surrounding invariants still reference those numbers.

## Retired invariants

### Inv 6 — `--linked-items` triple validation (Phase 7c)
Originally asserted that the dispatcher validated `--linked-items` entries (comma-separated `<feature>:<type>:<id>` triples) for exactly two colons, non-empty fields, and a type in {bug, backlog}, emitting a stderr diagnostic and exit 2 on any malformed entry BEFORE the prompt was written to stdout. Retired alongside the `--linked-items` flag itself: secondary linked-item closure was wired through the now-removed `rabbit-file` feature's `item-status.py`, and that feature was retired in earlier phases. With no downstream consumer of the parsed triples, the validator and its surrounding parse loop are dead code. The flag was removed from the argparse surface in `dispatch-tdd-subagent.py`; argparse now rejects `--linked-items` as an unrecognized argument. Equivalent assertion: spec Inv 4 (flag set excludes `--linked-items`), `test/test-cli-invocation.py` (asserts argparse rejects `--linked-items` as an unrecognized argument).

### Inv 19 — primary `--linked-item` closure (Phase 7c)
Originally asserted that when `--linked-item` + `--item-type` were supplied, the assembled prompt's STEP 7 UNLOCK section contained an `item-status.py set --feature <f> --type <t> --id <i> --status close --reason 'TDD cycle complete' --fix-commits $IMPL_SHA` block to close the primary item after the impl commit. Retired with the `rabbit-file` feature: there is no longer an `item-status.py` script to invoke, and item-state management was relocated outside the TDD cycle. The corresponding close-call rendering block was deleted from `dispatch-tdd-subagent.py`; the flag was removed from the argparse surface.

### Inv 20 — secondary `--linked-items` closure (Phase 7c)
Originally asserted that every secondary entry in `--linked-items` produced an additional `item-status.py set ... --reason 'TDD cycle complete (secondary item resolved by same commit)' ...` block in STEP 7 UNLOCK. Retired with Inv 19 for the same reason: the downstream `item-status.py` script no longer exists. The flag and its rendering loop were removed.

### Inv 21 — HANDOFF `closed_items` list (Phase 7c — simplified, not retired)
Originally asserted that HANDOFF's `closed_items` field listed every item closed by the cycle (primary + secondaries). With the `--linked-item` / `--linked-items` surface gone (Inv 19, 20), there are no items to close, so `closed_items` is now always an empty list `[]`. Inv 21 is **simplified rather than retired**: the field is retained on the HANDOFF schema for forward compatibility per Inv 22 (HANDOFF schema versioning), and a future cycle reintroducing item-close machinery would simply repopulate the list without a schema bump. The simplified invariant text lives inline in spec.md at Inv 21.

### Inv 30 — `--linked-item` path-layout validation (Phase 7c)
Originally asserted that `dispatch-tdd-subagent.py` resolved the `--linked-item` path and required the canonical `.../rabbit/features/<feature>/<bugs|backlogs>/<id>/` layout, exiting 2 with a stderr diagnostic on a mismatch and wiring the validated feature name (segments[-3]) through to the close-call block. Retired with Inv 19: with no downstream close-call block to consume the validated feature name, the layout check is dead code. The `_validate_linked_item` helper was deleted from `dispatch-tdd-subagent.py` and the flag itself was removed.

### Inv 5 — boolean flag vocabulary (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that boolean values for `--human-approval-gate` are exactly `true` or `false` (no `enabled`/`disabled`, `yes`/`no`, etc.). Retired alongside the `--human-approval-gate` flag itself: the flag was removed from the argparse surface in `dispatch-tdd-subagent.py`, so there is no boolean vocabulary left to constrain. The wider boolean-vocabulary convention (true/false only) is still observed by other rabbit features that accept boolean flags, but it is not specific to tdd-subagent any more. Equivalent assertion: spec Inv 4 (flag set excludes `--human-approval-gate`), `test/test-cli-invocation.py` (asserts argparse rejects `--human-approval-gate true` and `--human-approval-gate false` as unrecognized arguments).

### Inv 13 — SPEC-READ diff target (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that the assembled prompt's STEP 1 SPEC-READ section runs `git diff HEAD~1 -- <feature_dir>/docs/spec/`. The STEP 1 SPEC-READ section was deleted from the prompt template altogether: spec context is already interpolated verbatim into the prompt via `{spec_content}`, so an in-subagent diff against HEAD~1 was redundant (the subagent has the post-edit spec in front of it; the dispatcher's spec-authoring step produced the committed baseline). With the SPEC-READ section gone, there is no diff command for any test to assert.

### Inv 25 — `--human-approval-gate true` branch (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that with `--human-approval-gate true` (default), the assembled prompt contains a STEP 2 HUMAN-APPROVAL section instructing the subagent to invoke `Skill("superpowers:writing-plans")`, present the implementation summary to the user, and wait for explicit approval before STEP 3 LOCK. Retired because subagents have no user-interaction tools — the "wait for explicit approval" instruction was dead code (subagents cannot prompt the user, and the dispatcher's Step 4 HUMAN-APPROVAL gate is the real approval surface). The STEP 2 HUMAN-APPROVAL section was deleted from the prompt template. The `--human-approval-gate` flag was removed from the argparse surface alongside.

### Inv 26 — `--human-approval-gate false` branch (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that with `--human-approval-gate false`, the assembled prompt's STEP 2 HUMAN-APPROVAL section is a one-line stub stating the step is skipped. Retired with Inv 25 — the STEP 2 HUMAN-APPROVAL section no longer exists in either branch (there is no longer a flag to branch on), so there is no stub form to assert.
