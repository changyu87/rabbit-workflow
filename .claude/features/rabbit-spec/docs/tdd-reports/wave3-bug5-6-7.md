---
feature: rabbit-spec
cycle: wave3-bug5-6-7
tdd_state: test-green
impl_sha: ae9334268616d9c089eac4269f3b178b6a531806
spec_compliance: pass
date: 2026-05-18
---

# Wave 3 TDD Report — rabbit-spec (BUG-5, BUG-6, BUG-7)

## Scope

Three Wave 3 bugs were closed under spec.md v1.2.0:

- **BUG-5** (Inv 9): `feature.json` `version` drifted from `docs/spec/spec.md`
  frontmatter `version`. Now enforced by a test.
- **BUG-6** (Inv 10/Inv 3 coverage): no test enforced that SKILL.md documents
  the impl-suggestion schema.
- **BUG-7** (Inv 10/Inv 5 coverage): no test enforced the relative ordering of
  the "Update the Spec" and "Write impl-suggestion File" steps.

## Tests Added

| Path | Invariant | Mechanism |
|------|-----------|-----------|
| `test/test-inv3-impl-suggestion-schema.py` | Inv 3 | Asserts built SKILL.md body documents all 8 required schema fields and schema_version 1.0.0 |
| `test/test-inv5-spec-before-impl-suggestion.py` | Inv 5 | Asserts "Step 4 — Update the Spec" heading offset < "Step 5 — Write impl-suggestion File" heading offset in built SKILL.md |
| `test/test-inv9-version-sync.py` | Inv 9 | Loads feature.json + spec.md frontmatter, asserts version equality |

All three tests target deployed/source artifacts (E2E rule satisfied).

## Implementation

Single change: `.claude/features/rabbit-spec/feature.json` `version` bumped
from `1.0.0` to `1.2.0` to match the v1.2.0 spec.md frontmatter.

No runtime script changes. Skill-only feature.

## Test Results

- RED: `test_versions_equal` failed with `feature.json='1.0.0' vs spec.md='1.2.0'`.
- GREEN (after version bump): full `test/run.py` passes — all 5 test files pass.

## Commits

- `e09ce07` test(rabbit-spec): add Wave 3 tests for Inv 3, 5, 9 (BUG-5, 6, 7)
- `ae93342` fix(rabbit-spec): Wave 3 (BUG-5, 6, 7)
