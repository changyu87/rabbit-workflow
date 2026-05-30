---
feature: rabbit-feature
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-feature spec's invariant numbering is folded into a structured schema-tracked log
---

# rabbit-feature — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `docs/spec/spec.md` and have since been retired. Spec.md no longer carries the prose for these invariants — only a one-line `*(Retired — see CHANGELOG.md, …)*` marker at the original number.

Each entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the cascade or backlog ID that drove the retirement.

## Renumber and gap-preservation events

- **Phase 7c cleanup — rip B/B mode (this cycle):** Spec.md surviving invariants are NOT renumbered. This cycle retires two invariants (Inv 13 and Inv 42) — both asserted documentation in the `rabbit-feature-touch` SKILL.md for the B/B (bug / backlog) invocation mode of the seven-step sequence. The B/B mode itself is removed from the SKILL.md as part of this phase; with rabbit-file retired in Phase 7b there are no remaining callers passing `--linked-item` to `dispatch-tdd-subagent.py`, leaving the two invariants without any caller-side surface to bind against. Total retirements (2) is well within the renumber-vs-gaps threshold (≤ 5); gaps at positions 13 and 42 are preserved rather than re-flowing the surviving invariants, keeping all cross-references in tests and other features' specs stable. This continues the same gap-preservation pattern established by the Inv 10 / Inv 11 cascade.

- **TDD-SUBAGENT-BACKLOG-19 cascade:** Spec.md surviving invariants are NOT renumbered. The cascade retires two invariants (Inv 10 and Inv 11) — both asserted that the `rabbit-feature-touch` SKILL.md Step 4 documents passing `--human-approval-gate true|false` to `dispatch-tdd-subagent.py`. The upstream `tdd-subagent` feature removed the `--human-approval-gate` CLI flag (v5.0.0) when it dropped the SPEC-READ and HUMAN-APPROVAL steps from the dispatched prompt, so the two assertions no longer have a CLI surface to bind against. Total retirements (2) is well within the renumber-vs-gaps threshold (≤ 5); gaps at positions 10 and 11 are preserved rather than re-flowing the surviving invariants, keeping all cross-references in tests and other features' specs stable.

## Retired invariants

### Inv 10 — Step 4 bypass-active branch passes `--human-approval-gate false` (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that the `rabbit-feature-touch` SKILL.md Step 4 documents passing `--human-approval-gate false` to the Step 5 `dispatch-tdd-subagent.py` invocation when the `.rabbit-human-approval-bypass` marker is present. Retired because the upstream `tdd-subagent` feature removed the `--human-approval-gate` argparse flag entirely in v5.0.0 (the subagent has no user-interaction tools, so the gate has no executor-side meaning). The dispatcher's bypass-active behaviour is now "proceed to Step 5 immediately" with no flag to pass. Replacement: a negative-assertion regression guard in `test/test-touch-skill.py` (`test_no_human_approval_gate_flag_in_source_skill` and `test_no_human_approval_gate_flag_in_deployed_skill`) ensures the flag string never reappears in either SKILL.md.

### Inv 11 — Step 4 bypass-absent branch documents `--human-approval-gate true` (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that the `rabbit-feature-touch` SKILL.md Step 4 documents passing `--human-approval-gate true` (or omitting the flag, since `true` was the default) to the Step 5 `dispatch-tdd-subagent.py` invocation on the default marker-absent path. Retired with Inv 10 — the flag no longer exists in `dispatch-tdd-subagent.py` v4.0.0+, so the assertion has no CLI surface. The dispatcher's bypass-absent behaviour is now to wait for explicit user approval and then proceed to Step 5 (no flag to pass). Replacement: same negative-assertion regression guard as Inv 10.

### Inv 13 — B/B mode reads `item.json` via python3 (Phase 7c)
Originally asserted that the `rabbit-feature-touch` SKILL.md Step 1 B/B-mode block extracts the related feature from `<item-dir>/item.json` using `python3` (not `jq`, which is not a declared dependency) and references `item.json` (not the legacy `bug.json`). Retired because the entire B/B (bug / backlog) invocation mode was removed from the SKILL.md in the Phase 7c cleanup: with rabbit-file retired in Phase 7b there are no callers passing `--linked-item` to `dispatch-tdd-subagent.py`, so the Step 1 B/B-mode block (and the item.json read path it locks) no longer exists in the SKILL.md. The unified seven-step sequence is now single-mode (normal-mode-only) and resolves scope exclusively via `Skill("rabbit-feature-scope", ...)`.

### Inv 42 — B/B item materialization documented in SKILL.md (Phase 7c)
Originally asserted that the `rabbit-feature-touch` SKILL.md Step 1 contains a `#### B/B item materialization` subsection documenting (a) why materialization is needed (the canonical `bug-backlog-files` branch is never checked out), (b) the local mirror path layout under `.rabbit/rabbit/features/<feature>/<type>s/<id>/`, (c) the `git show origin/bug-backlog-files:...` fetch command, and (d) what gets passed to `--linked-item` (the local mirror directory). Inv 42 also required byte-identical presence of the subsection in both the source and deployed SKILL.md. Retired with Inv 13 — the B/B mode (and the materialization step it required) was removed entirely in the Phase 7c cleanup; with no caller passing `--linked-item`, neither the subsection nor the materialization workflow has a remaining surface to document. The byte-identity requirement between source and deployed SKILL.md is preserved by Inv 1 (build source) and the existing `test_inv41_source_and_deployed_byte_identical` test.
