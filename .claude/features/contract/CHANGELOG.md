---
feature: contract
owner: rabbit-workflow team
deprecation_criterion: when the contract spec's invariant numbering is folded into a structured schema-tracked log
---

# contract — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `docs/spec/spec.md` and have since been retired. Spec.md no longer carries inline tombstones (CONTRACT-BACKLOG-30, F8 partial).

Each entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the backlog ID that drove the retirement.

## Renumber and gap-preservation events

- **CONTRACT-WAVE-9 (this wave):** Spec.md surviving invariants are NOT renumbered. Wave 9 retires four invariants (Inv 6, 7, 30, 35) and preserves the resulting numbering gaps at those positions rather than re-flowing the surviving invariants. The decision departs from the CONTRACT-BACKLOG-31 precedent because the gap count is small and every invariant number is referenced by ~25+ cross-references across `lib/checks.py`, `scripts/enforcement/*.py`, `test/*.py` docstrings, and other features' specs; preserving stable numbers avoids a cascade rewrite that would touch every Inv-citing site. `check_invariant_monotonic_order` accepts gaps (the check is strictly-increasing, not contiguous), so this introduces no enforcement violation.

- **CONTRACT-BACKLOG-31 (earlier cycle):** Spec.md surviving invariants renumbered monotonically to 1..39, closing all gaps left by previously-retired invariants. The tombstone numbers below (2, 6, 8, 14, 27, 29, 31) are HISTORICAL — they record the spec.md numbers as they existed at retirement time and are NOT updated by the renumber. Post-renumber, those historical numbers may numerically collide with new active invariants in spec.md; the collision is benign because tombstone entries are scoped to "historical numbers in this CHANGELOG" by file/section. The companion `test/test-spec-tombstone-gaps-match-changelog.py` was deleted in the same cycle: its premise was the gap-correspondence between spec.md numbering gaps and CHANGELOG tombstones, which no longer holds once all gaps are closed.

## Retired artifacts

### `publish.json` — per-feature deployment manifest (Plan F.1)
Originally a sibling manifest file under each active feature
(`.claude/features/<feature>/publish.json`) declaring `copy-file` targets
for deployment, validated against
`.claude/features/contract/schemas/publish-manifest.schema.json`. Federated
into each feature's `feature.json` `manifest` array during Plan E.* (one
workspace per feature, replacing the legacy `source`+`destination` schema
with `publish_skill` / `publish_file` / `publish_agent` API calls). Plan
F.1 deleted the four remaining files
(`rabbit-feature`, `rabbit-file`, `tdd-state-machine`, `tdd-subagent`)
now that the meta-contract MANIFEST is the single source of truth.
Equivalent assertions:
- per-feature `test-manifest-shape.py` (manifest entry shape)
- per-feature `test-manifest-deploys-correctly.py` (source→deployed byte parity)
- `contract/test/test-retired-artifacts.py` Section D (no `publish.json`
  file remains)

## Retired invariants

### Inv 6 — build-contract.json validation (CONTRACT-WAVE-9)
Originally asserted that `build-contract.json` validates against `build-contract.schema.json`. Both files were deleted during the federate-build-manifests migration; the equivalent assertion now lives in each feature's `feature.json` `manifest` validation against the meta-contract manifest schema. The "Invariant enforcement limitations" section that depended on this invariant was retired alongside.

### Inv 7 — build-contract.json copy-file source check (CONTRACT-WAVE-9)
Originally asserted that every `copy-file` target in `build-contract.json` has a `source` field whose path exists on disk. Retired with Inv 6 — the catalog is gone; per-feature `feature.json` `manifest` schemas + deployment tests cover the equivalent.

### Inv 30 — build-contract.json rabbit-feature-touch source pointer (CONTRACT-WAVE-9)
Originally asserted that the `build-contract.json` entry for `skills/rabbit-feature-touch/SKILL.md` sourced from `rabbit-feature`. The drift-detection responsibility moved to rabbit-feature alongside the federation; the live invariant is rabbit-feature spec Inv 1 backed by `test/test-build-source.py` in the rabbit-feature feature.

### Inv 35 — build-contract.json deployment mappings (CONTRACT-WAVE-9)
Originally asserted (a) the `rabbit-feature-spec` SKILL.md deployment entry and (b) the `tdd-step.py` source pointer in `build-contract.json`. The cited tests `test-rabbit-feature-spec-deployment.py` and `test-build-contract-tdd-state-machine-sources.py` no longer exist (the live deployment test is `test-rabbit-feature-skills-deployment.py` owned by rabbit-feature).

### Inv 2 — dispatch-feature-edit.py deleted (CONTRACT-BACKLOG-27)
Originally asserted that dispatch-feature-edit.py consumed the RABBIT-POLICY-BLOCK-v1 policy-block sentinel. The script was deleted as dead production code (no runtime caller); the sentinel is now consumed only by policy-block.py and the tdd-subagent dispatch path, asserted by test-policy-block.py.

### Inv 6 — workspace-map.py deleted (CONTRACT-BACKLOG-27)
Originally asserted properties of workspace-map.py. The script was deleted as orphan production code; its sole consumer was the retired rabbit-workspace-map skill.

### Inv 8 — rabbit-workspace-map/SKILL.md deleted (CONTRACT-BACKLOG-27)
Originally asserted properties of the rabbit-workspace-map skill. The SKILL.md (source and deployed copy) was deleted as orphan surface together with the build-contract.json entry that deployed it.

### Inv 14 — rabbit-triage.py deleted (CONTRACT-BACKLOG-24)
Originally asserted properties of rabbit-triage.py. The script was deleted as dead production code; it had no production caller outside its own self-references.

### Inv 27 — dispatch-feature-edit.py path-detection (CONTRACT-BACKLOG-27)
Originally asserted path-detection behaviour of dispatch-feature-edit.py. Retired alongside Inv 2 — the script was deleted, so the path-detection invariant no longer applies.

### Inv 29 — audit-orphan-storage.py deleted (CONTRACT-BACKLOG-24)
Originally asserted properties of audit-orphan-storage.py. The script was deleted as dead production code; it had no production caller outside its own self-references.

### Inv 31 — check-no-main-edits.py deleted (CONTRACT-BACKLOG-27)
Originally asserted properties of check-no-main-edits.py. The script was deleted; it was never auto-invoked. The live guards against direct edits to main/master are the feature-touch branch + PR workflow plus the Bash(git push * main) deny rules in rabbit-cage Inv 19.

## Parenthetical strikes also moved here

Two active invariants (Inv 7 and Inv 38) carried parenthetical "removed in BACKLOG-XX" annotations. The parentheticals were documentary tombstones, not normative — they have been moved here so the active invariant prose is no longer mixed with retirement bookkeeping.

### Inv 7 parenthetical — workspace-map.json.schema.json deleted (CONTRACT-BACKLOG-27)
The companion schema workspace-map.json.schema.json was deleted alongside its sole producer (workspace-map.py, retired in this same backlog — see Inv 6 above). The remaining Inv 7 prose describes the surviving workspace-structure.json schema and is unchanged.

### Inv 38 parentheticals — runtime-audit retirement + Cycle B additions
(a) The legacy workspace-map.py --audit runtime audit was retired in CONTRACT-BACKLOG-27 in favour of the direct comparison performed by test-workspace-declares-all-features.py. (b) During Cycle B, the workspace-structure.json declaration was extended to cover rabbit-spec, rabbit-file, and rabbit-feature, closing the pre-existing audit findings. The remaining Inv 38 prose describes the standing declaration invariant and is unchanged.
