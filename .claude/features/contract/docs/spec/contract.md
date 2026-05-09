# contract — Contract

**Owner:** rabbit-workflow team
**Version:** 1.0.0

## What `contract` Provides

All paths are relative to the repository root.

### Templates
- `.claude/features/contract/templates/spec-template.md`
- `.claude/features/contract/templates/contract-template.md`
- `.claude/features/contract/templates/bug-template.json`
- `.claude/features/contract/templates/triage-template.md`
- `.claude/features/contract/templates/feature-json-template.json`
- `.claude/features/contract/templates/subagent-launch-template.txt`
- `.claude/features/contract/templates/project-map-template.json`
- `.claude/features/contract/templates/registry-template.json`

### Schemas
- `.claude/features/contract/schemas/feature.json.schema.json`
- `.claude/features/contract/schemas/registry.json.schema.json`
- `.claude/features/contract/schemas/bug.json.schema.json`
- `.claude/features/contract/schemas/project-map.json.schema.json`

### Scripts
- `.claude/features/contract/scripts/policy-block.sh`
- `.claude/features/contract/scripts/dispatch-feature-edit.sh`
- `.claude/features/contract/scripts/rebuild-registry.sh`
- `.claude/features/contract/scripts/relink.sh`
- `.claude/features/contract/scripts/render-template.sh`
- `.claude/features/contract/scripts/check-maps-consistent.sh`
- `.claude/features/contract/scripts/rabbit-triage.sh`

## What Consumers Read

Consumers read any of the above paths by their absolute or repo-relative path.
No hidden side channels. No free-form communication.

## What `contract` Never Does

- Never directly edits another feature's `feature.json`, specs, tests, or
  implementation files.
- Never writes outside `.claude/features/contract/`.
- Never modifies another feature's registry entry without that feature's
  explicit TDD-gated step.
- Never generates human-readable views alongside machine-format artifacts;
  views are produced by tools operating on schema-formed outputs.
