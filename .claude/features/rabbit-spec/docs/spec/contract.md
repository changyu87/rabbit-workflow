---
feature: rabbit-spec
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
---

# rabbit-spec — Contract

rabbit-spec is the owner of the rabbit workflow's spec-lifecycle skills. In
this revival stage the feature carries no surface artifacts; the contract
therefore declares empty `provides`, `reads`, and `invokes` blocks. The
`never` array pins the boundary so future absorptions (rabbit-spec-create in
Stage 2, rabbit-spec-update in Stage 3) cannot land surface without first
updating `spec.md`.

```json
{
  "schema_version": "1.0.0",
  "feature": "rabbit-spec",
  "version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when Claude Code exposes native spec-lifecycle skills that supersede this feature",
  "provides": {},
  "reads": {},
  "invokes": {},
  "never": [
    "introduces any surface artifact without first updating spec.md",
    "modifies another feature's files"
  ]
}
```
