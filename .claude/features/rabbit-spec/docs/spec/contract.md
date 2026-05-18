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

- Any TDD-cycle skill, test runner, or implementation tool. This skill stops
  after writing the impl-suggestion file; downstream execution is the caller's
  concern (Inv 7 — process-agnostic).

## Consumed By

- Any process or caller that needs a feature spec authored or updated
  (examples include: feature-touch workflows, backlog grooming sessions,
  standalone design review, direct user invocation). The skill makes no
  assumption about who invoked it, and its sole output — the
  `.rabbit/impl-suggestion-<feature>.json` file — is read by whichever
  process called it (Inv 7).
