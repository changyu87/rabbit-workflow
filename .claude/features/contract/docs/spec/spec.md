# contract — Feature Spec

## Purpose

`contract` is the meta-feature of the rabbit workflow. It owns all cross-feature
templates, schemas, and dispatch scripts. Its sole role is to **provide**; it
never modifies another feature's files. Consumers apply the contract artifacts
through their own TDD cycles.

## What It Owns

### Templates (8)

- `templates/spec-template.md` — template for `docs/spec/spec.md`
- `templates/contract-template.md` — template for `docs/spec/contract.md`
- `templates/bug-template.json` — template for bug filing JSON
- `templates/triage-template.md` — template for TRIAGE block output
- `templates/feature-json-template.json` — template for `feature.json`
- `templates/subagent-launch-template.txt` — template for Agent dispatch prompt
- `templates/project-map-template.json` — template for `project-map.json`
- `templates/registry-template.json` — template for `registry.json`

### Schemas (4)

- `schemas/feature.json.schema.json` — validates `feature.json`
- `schemas/registry.json.schema.json` — validates `registry.json`
- `schemas/bug.json.schema.json` — validates bug filings
- `schemas/project-map.json.schema.json` — validates `project-map.json`

### Scripts (7)

- `scripts/policy-block.sh` — emits the canonical policy block to stdout
- `scripts/dispatch-feature-edit.sh` — the only legal Agent dispatch path
- `scripts/rebuild-registry.sh` — rebuilds `registry.json` from `feature.json` files
- `scripts/relink.sh` — creates/refreshes symlinks declared in feature surfaces
- `scripts/render-template.sh` — substitutes `{{key}}` placeholders in templates
- `scripts/check-maps-consistent.sh` — verifies registry and filesystem are in sync
- `scripts/rabbit-triage.sh` — builds a triage prompt for a bug filing

## Invariants

1. `contract` only provides; consumers apply. This feature never directly edits
   any other feature's files.
2. Every consumer applies contract artifacts through its own TDD cycle.
3. Every template carries a `template_version` field (semver, minimum `1.0.0`).
4. Changes to `contract` go through TDD on the `contract` feature itself:
   the `tdd_state` must advance through `spec → test-red → impl → test-green → review`.
5. Cross-feature communication is contract-bound: read nothing outside the
   declared contract; generate nothing outside the declared contract.

## Deprecation Criterion

When Claude Code exposes a native workflow contract mechanism that supersedes
this feature's template, schema, and dispatch responsibilities, `contract` is
deprecated. Migration path: consumers point to the native mechanism; this
feature is archived after a documented coexistence window.

**Owner:** rabbit-workflow team
**Version:** 1.0.0
