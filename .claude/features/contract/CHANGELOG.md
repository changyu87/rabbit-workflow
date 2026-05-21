---
feature: contract
owner: rabbit-workflow team
deprecation_criterion: when the contract spec's invariant numbering is folded into a structured schema-tracked log
---

# contract — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `docs/spec/spec.md` and have since been retired. Spec.md no longer carries inline tombstones (CONTRACT-BACKLOG-30, F8 partial); the original invariant numbers remain unused in spec.md, creating intentional numeric gaps until the full monotonic renumber lands in CONTRACT-BACKLOG-31.

Each entry below carries the original invariant number (as it appeared in spec.md before retirement), a one-line summary of what the invariant asserted and why it was retired, and the backlog ID that drove the retirement.

## Retired invariants

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
Originally asserted properties of check-no-main-edits.py. The script was deleted; it was never auto-invoked. The live guards against direct edits to main/master are the feature-touch branch + PR workflow plus the Bash(git push * main) deny rules in rabbit-cage Inv 51.

## Parenthetical strikes also moved here

Two active invariants (Inv 7 and Inv 38) carried parenthetical "removed in BACKLOG-XX" annotations. The parentheticals were documentary tombstones, not normative — they have been moved here so the active invariant prose is no longer mixed with retirement bookkeeping.

### Inv 7 parenthetical — workspace-map.json.schema.json deleted (CONTRACT-BACKLOG-27)
The companion schema workspace-map.json.schema.json was deleted alongside its sole producer (workspace-map.py, retired in this same backlog — see Inv 6 above). The remaining Inv 7 prose describes the surviving workspace-structure.json schema and is unchanged.

### Inv 38 parentheticals — runtime-audit retirement + Cycle B additions
(a) The legacy workspace-map.py --audit runtime audit was retired in CONTRACT-BACKLOG-27 in favour of the direct comparison performed by test-workspace-declares-all-features.py. (b) During Cycle B, the workspace-structure.json declaration was extended to cover rabbit-spec, rabbit-file, and rabbit-feature, closing the pre-existing audit findings. The remaining Inv 38 prose describes the standing declaration invariant and is unchanged.
