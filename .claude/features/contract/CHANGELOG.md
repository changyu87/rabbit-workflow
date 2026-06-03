---
feature: contract
owner: rabbit-workflow team
deprecation_criterion: when the contract spec's invariant numbering is folded into a structured schema-tracked log
---

# contract — Retired Invariants Log

This file holds the tombstones for invariants that were previously declared in `specs/spec.md` and have since been retired. Spec.md no longer carries inline tombstones (CONTRACT-BACKLOG-30, F8 partial).

Each entry below carries the original invariant number (as it appeared in spec.md at the time of retirement), a one-line summary of what the invariant asserted and why it was retired, and the backlog ID that drove the retirement.

## Version notes

- **v2.4.0 (contract spec dir migrated to `specs/`, #399 Phase 2):** Moved contract's own `docs/spec/` to `specs/` via `git mv` and removed the now-empty `docs/` directory; contract's canonical spec/contract docs now live at `specs/spec.md` and `specs/contract.md`. The dual-read resolver (`resolve_spec_path`) keeps the legacy `docs/spec/` fallback alive for every other feature still mid-migration, so the suite stays green. Updated contract's own hardcoded spec paths (test-files-exist, test-cli-naming-convention, test-python-only-stack, test-bug-fixes-cycle, the test-no-dead-contract-scripts self-exclusion) to `specs/`, and made the cross-feature doc scanners dual-read aware so contract's relocated docs stay covered: test-spec-bodies-no-historical-tags (`feature_doc_surfaces`), test-check-numbered-lists (t7 globs), and test-check-invariant-monotonic-order (`live_feature_dirs`). Spec prose for the affected invariants (32, 33, 34, 38, 39, 49) updated to describe dual-read / the new contract layout. New E2E regression `test/test-contract-spec-dir-migrated.py` asserts `specs/spec.md` + `specs/contract.md` exist, no `docs/` remains, and the resolver prefers `specs/` for contract. Phase 3 (separate PR) drops the fallback once all features have moved.

- **v2.3.0 (dual-read spec/contract path resolution, #399 Phase 1):** Added `resolve_spec_path(feature_root, name)` to `lib/checks.py` — prefers the new `specs/<name>` layout and falls back to legacy `docs/spec/<name>`. Wired into `validate_feature` (the spec.md/contract.md missing/empty checks) and `check_invariant_monotonic_order` (spec.md read). Phase 1 of issue #399's `docs/spec/` -> `specs/` migration opens a coexistence window (#450 Pattern 1) so every feature stays green while features migrate one-by-one in Phase 2; Phase 3 (separate PR) drops the fallback once all features have moved. Contract's own `docs/spec/` directory is intentionally NOT migrated in this phase — the fallback keeps it valid. Genuine absence of both layouts is still flagged. New E2E regression test `test/test-spec-path-dual-read.py` proves both layouts validate. Deprecation criterion for the fallback: issue #399 Phase 3 (every feature migrated to `specs/`).

- **v2.0.0 (Skill-path prompt injection retirement, #391):** Major-bump retirement of the Skill-path PreToolUse prompt-injection surface. `hooks/prompt-injector.py` source + deployed copy deleted; contract's `manifest` and `runtime` emptied (no live hook or Stop-event callers remain); nine `prompts[]` entries with `kind: "skill"` removed across rabbit-feature, rabbit-spec, rabbit-config, rabbit-issue, rabbit-auto-evolve, rabbit-decompose; nine corresponding skill-passthrough templates deleted from `templates/prompts/`. Contract is now verification-only — the mechanical RABBIT-POLICY-BLOCK-v1 sentinel-validation contract owned by rabbit-cage's `scope-guard.py` (Inv 66, PR #390/#394) supersedes the Skill-path injection mechanism. The `check_prompt_injection_failures` and `cleanup_old_prompts` runtime APIs remain in `lib/runtime.py` and the runtime-schema closed enum (they have no live callers but remain part of the meta-contract surface per Inv 41/47 for any future re-use).

- **v1.51.1 (Inv 65 banner-status delegation, #382):** `emit_auto_evolve_banner` refactored to delegate line-1/line-2 content to `rabbit-auto-evolve/scripts/banner-status.py` via subprocess. Contract owns the dispatch mechanism (gate marker check, subprocess invocation, JSON parse, mapping to `print_result`); rabbit-auto-evolve owns the per-variant content. Three pre-existing inlined line-2 variants removed from `lib/runtime.py`. `contract.md` `invokes.scripts` extended to declare the cross-feature script invocation. `emit_auto_evolve_stop_line` unchanged.

## Renumber and gap-preservation events

- **Plan F.3 (rabbit-print refactor):** Spec.md surviving invariants are NOT renumbered. Plan F.3 retires four invariants tied to the rabbit-print registry/wrapper architecture (Inv 4, 27, 28, 29) and preserves the resulting numbering gaps at those positions rather than re-flowing the surviving invariants. Total gap count (4 + the eight pre-existing) remains well within the renumber-vs-gaps threshold; the cross-reference cost of a cascade rewrite still outweighs the gap cost.

- **CONTRACT-WAVE-9 (earlier cycle):** Spec.md surviving invariants are NOT renumbered. Wave 9 retires four invariants (Inv 6, 7, 30, 35) and preserves the resulting numbering gaps at those positions rather than re-flowing the surviving invariants. The decision departs from the CONTRACT-BACKLOG-31 precedent because the gap count is small and every invariant number is referenced by ~25+ cross-references across `lib/checks.py`, `scripts/enforcement/*.py`, `test/*.py` docstrings, and other features' specs; preserving stable numbers avoids a cascade rewrite that would touch every Inv-citing site. `check_invariant_monotonic_order` accepts gaps (the check is strictly-increasing, not contiguous), so this introduces no enforcement violation.

- **CONTRACT-BACKLOG-31 (earlier cycle):** Spec.md surviving invariants renumbered monotonically to 1..39, closing all gaps left by previously-retired invariants. The tombstone numbers below (2, 6, 8, 14, 27, 29, 31) are HISTORICAL — they record the spec.md numbers as they existed at retirement time and are NOT updated by the renumber. Post-renumber, those historical numbers may numerically collide with new active invariants in spec.md; the collision is benign because tombstone entries are scoped to "historical numbers in this CHANGELOG" by file/section. The companion `test/test-spec-tombstone-gaps-match-changelog.py` was deleted in the same cycle: its premise was the gap-correspondence between spec.md numbering gaps and CHANGELOG tombstones, which no longer holds once all gaps are closed.

## Retired artifacts

### `rabbit-print-messages.json` — message-id registry (Plan F.3)
Originally the JSON registry data file at
`.claude/features/contract/schemas/rabbit-print-messages.json` holding the
brand, bar, color palette, and every `[rabbit]` message body keyed by
message-id. `rabbit_print.py` loaded this file at first use and rendered
each producer-supplied message-id by registry lookup; twelve named
wrappers (`welcome`, `policy_drift`, `surface_drift`, `scope_guard_off`,
`scope_guard_bypassed`, `human_approval_bypass`,
`bypass_permissions_active`, `dispatch_bypass_note`, `skills_updated`,
`policy_refreshed`, `tdd_transition`, `tdd_forced`) wrapped the lookup.
Plan F.3 deleted the registry and the wrappers in favour of a direct-call
API: producers now supply `text/icon/color/format` inline at the call
site. Equivalent assertions: spec Inv 48 (direct-call API),
`test-rabbit-print-renderer.py` (asserts retired wrappers are absent and
exercises the inline-args surface).

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

### Inv 4 — three-artifact rabbit-print authority (Plan F.3)
Originally asserted that the `[rabbit]` print system was split into three
artifacts: `rabbit-print-messages.json` (registry data file with `icon`,
`color`, `text` per message), `rabbit-print.schema.json` (JSON Schema for
the registry), and `rabbit_print.py` (renderer module). Plan F.3
collapsed the architecture: the registry was deleted, the schema was
repurposed as a wire-format spec for the `rabbit_print()` argument
shape, and the renderer became a direct-call API
(`rabbit_print(text, icon, color, format)`). Replacement: new Inv 48.

### Inv 27 — rabbit-print-messages.json registry shape (Plan F.3)
Originally asserted the on-disk shape of the message-id registry
(`brand`, `bar`, `colors`, and the closed message-id set: `welcome`,
`policy-drift`, `surface-drift`, `scope-guard-off`, `scope-guard-bypassed`,
`human-approval-bypass`, `bypass-permissions-active`,
`dispatch-bypass-note`, `skills-updated`, `policy-refreshed`,
`tdd-transition`, `tdd-forced`). Retired with the registry file; producers
now carry their text/icon/color/format inline at the call site.

### Inv 28 — rabbit_print.py module shape with named wrappers (Plan F.3)
Originally asserted that `rabbit_print.py` exposed
`rabbit_print(message_id, **kwargs)`, `rabbit_subline`, `rabbit_block`,
plus twelve named wrappers (one per registry message-id). Plan F.3 dropped
the wrappers and changed `rabbit_print` to `(text, icon, color, format)`;
the surviving module surface is asserted by new Inv 48 (which also asserts
the wrappers are absent).

### Inv 29 — named-wrapper producer set (Plan F.3)
Originally asserted that `tdd-step.py` and `dispatch-tdd-subagent.py`
were the canonical named-wrapper producer set, that direct calls to
`rabbit_print("message-id", ...)` at producer call sites were forbidden,
and that the wrappers were the public API for producers. Retired with
the wrappers themselves; the surviving "producers MUST route through
`rabbit_print.py` rather than emit inline ANSI/brand strings" guarantee
is part of new Inv 48 and is asserted by `tdd-state-machine/test/test-branding.py`
and `tdd-subagent/test/test-bypass-marker-note.py`.

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

### Inv 55 — PreToolUse hook `hooks/prompt-injector.py` (issue #391)
Originally asserted that `.claude/features/contract/hooks/prompt-injector.py` MUST exist as a PreToolUse hook intercepting `tool_name == "Skill"` calls, walking `.claude/features/*/feature.json` for a `prompts` entry with `kind: "skill"` matching the skill id, invoking `build-prompt.py` to assemble a policy-prefixed prompt, and emitting it as `additionalContext`. Retired by issue #391: the Skill-path injection surface was superseded by the mechanical RABBIT-POLICY-BLOCK-v1 sentinel-validation contract (new Inv 66, PR #390/#394) owned by rabbit-cage's `scope-guard.py`. The sentinel mechanism enforces that every `Agent` dispatch carries a policy-injected prompt (assembled by contract's `build-prompt.py`), shifting the contract from per-tool runtime injection to per-tool dispatch-time validation. Source hook + deployed copy + corresponding `publish_hook` manifest entry + `test/test-prompt-injector-hook.py` all deleted in the same cycle.

### Inv 56 — Contract's `manifest` + `runtime` for prompt-injection (issue #391)
Originally asserted that `.claude/features/contract/feature.json` declare EXACTLY one manifest entry (`publish_hook` for the prompt-injector source) and EXACTLY two runtime.Stop entries (`check_prompt_injection_failures` consuming the hook's failure log, then `cleanup_old_prompts` sweeping `.rabbit/prompts/`). Retired by issue #391 alongside Inv 55: with the hook gone, contract no longer owns any hook or runtime instances of its own. `manifest`, `runtime`, and `configuration` are now empty (`[]`/`{}`/`[]`) — contract is verification-only. The two runtime library functions (`check_prompt_injection_failures`, `cleanup_old_prompts`) remain in `lib/runtime.py` and the runtime-schema closed enum per Inv 41/47 for any future re-use, but no feature's `runtime` block calls them. Companion `test/test-contract-manifest-runtime.py` deleted in the same cycle.
