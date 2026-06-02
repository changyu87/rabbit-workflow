---
feature: rabbit-feature
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-feature spec's invariant numbering is folded into a structured schema-tracked log
---

# rabbit-feature — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `docs/spec/spec.md` and have since been retired. Spec.md no longer carries the prose for these invariants — only a one-line `*(Retired — see CHANGELOG.md, …)*` marker at the original number.

Each entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the cascade or backlog ID that drove the retirement.

## Renumber and gap-preservation events

- **TDD-SUBAGENT-BACKLOG-19 cascade (this cycle):** Spec.md surviving invariants are NOT renumbered. The cascade retires two invariants (Inv 10 and Inv 11) — both asserted that the `rabbit-feature-touch` SKILL.md Step 4 documents passing `--human-approval-gate true|false` to `dispatch-tdd-subagent.py`. The upstream `tdd-subagent` feature removed the `--human-approval-gate` CLI flag (v5.0.0) when it dropped the SPEC-READ and HUMAN-APPROVAL steps from the dispatched prompt, so the two assertions no longer have a CLI surface to bind against. Total retirements (2) is well within the renumber-vs-gaps threshold (≤ 5); gaps at positions 10 and 11 are preserved rather than re-flowing the surviving invariants, keeping all cross-references in tests and other features' specs stable.

## Retired invariants

### Inv 10 — Step 4 bypass-active branch passes `--human-approval-gate false` (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that the `rabbit-feature-touch` SKILL.md Step 4 documents passing `--human-approval-gate false` to the Step 5 `dispatch-tdd-subagent.py` invocation when the `.rabbit-human-approval-bypass` marker is present. Retired because the upstream `tdd-subagent` feature removed the `--human-approval-gate` argparse flag entirely in v5.0.0 (the subagent has no user-interaction tools, so the gate has no executor-side meaning). The dispatcher's bypass-active behaviour is now "proceed to Step 5 immediately" with no flag to pass. Replacement: a negative-assertion regression guard in `test/test-touch-skill.py` (`test_no_human_approval_gate_flag_in_source_skill` and `test_no_human_approval_gate_flag_in_deployed_skill`) ensures the flag string never reappears in either SKILL.md.

### Inv 11 — Step 4 bypass-absent branch documents `--human-approval-gate true` (TDD-SUBAGENT-BACKLOG-19)
Originally asserted that the `rabbit-feature-touch` SKILL.md Step 4 documents passing `--human-approval-gate true` (or omitting the flag, since `true` was the default) to the Step 5 `dispatch-tdd-subagent.py` invocation on the default marker-absent path. Retired with Inv 10 — the flag no longer exists in `dispatch-tdd-subagent.py` v4.0.0+, so the assertion has no CLI surface. The dispatcher's bypass-absent behaviour is now to wait for explicit user approval and then proceed to Step 5 (no flag to pass). Replacement: same negative-assertion regression guard as Inv 10.
