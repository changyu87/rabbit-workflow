---
feature: rabbit-spec
version: 1.0.0
owner: rabbit-workflow team
---

# rabbit-spec — Contract

## Reads

- Target feature `docs/spec/spec.md` (any feature)
- Any implementation files in target feature directory (read-only)
- `.rabbit/impl-suggestion-<feature>.json` (if pre-existing, to avoid clobbering)

## Writes

- Target feature `docs/spec/spec.md` (updated spec)
- `.rabbit/impl-suggestion-<feature>.json` (impl suggestion output)

## Invokes

- `Skill("superpowers:brainstorming")` — open-ended requests only
- `Skill("superpowers:writing-plans")` — all requests

## Does NOT Invoke

- `Skill("rabbit-feature-touch")` — not a feature touch, no TDD cycle
- Any test runner or implementation tool

## Consumed By

- `rabbit-feature-touch` Step 3 (main session, inline)
