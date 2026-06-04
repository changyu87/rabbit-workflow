---
feature: rabbit-issue
owner: rabbit-workflow team
deprecation_criterion: when the rabbit-issue feature is retired or its change history is folded into a structured schema-tracked log
---

# rabbit-issue — Changelog

Version-keyed change log for the rabbit-issue feature. The version here tracks
the spec version declared in `docs/spec.md` frontmatter and the `version`
field in `feature.json` (lockstep); `contract.md` carries its own version.

## Version notes

- **v1.7.0 (housekeeping Phase 2 — history-free doc surfaces + Inv 49 strict
  tier opt-in, #554):** Opted rabbit-issue into the contract Inv 49 strict tier
  by declaring top-level `"housekeeping_clean": true` in `feature.json`, then
  scrubbed all historical-burden framing from the three scanned doc surfaces
  (`docs/spec.md`, `docs/contract.md`, `skills/rabbit-issue/SKILL.md`) so they
  describe only the current design. Removed bare issue references — `#496` (the
  provenance-label section header and SKILL Label-Schema paragraph), `#423`
  (close-reason gating in spec + SKILL Work Protocol / Lifecycle), and `#522`
  (reading-issue-comments section in spec + SKILL Work Protocol, and the
  contract `invokes.gh` / `never` notes); replaced the `per issue` cardinality
  prose in the SKILL Label-Schema table with `per item` (matching spec.md);
  and removed the tombstone framing ("REPLACES the retired rabbit-file", "the
  legacy ... is gone", "retired by predecessor cutover", "deleted by
  migration", "what superseded it"), rephrasing each to present-tense
  declarative that keeps the substantive behaviour (rabbit-issue is the sole
  B/B surface; do NOT invoke rabbit-file; GH Issues / Timeline is the store).
  No invariants renumbered or removed. Strict test
  `contract/test/test-spec-bodies-no-historical-tags.py` goes RED (19
  violations) -> GREEN; full `contract/test/run.py` GREEN. Lockstep minor bump
  of `feature.json` / `spec.md` / `SKILL.md` (1.6.0 -> 1.7.0) and `contract.md`
  (1.5.0 -> 1.6.0). SKILL.md changed, so the deployed copy under
  `.claude/skills/` drifts until the dispatcher republishes
  (republish_needed). The removed `#NNN` provenance lives here in the
  CHANGELOG tombstone, which the strict scan never reads.

- **v1.6.0 (read issue comments via `gh --json comments`, #522):** `gh issue
  view <N> --comments` triggers a deprecated Projects-classic `projectCards`
  GraphQL field that FAILS and returns an EMPTY body on this repo, so comments
  silently read as absent even when present — a correctness trap, not a loud
  error. Added `_gh.gh_issue_comments(number)`, which reads the comment bodies
  via `gh issue view <N> -R <slug> --json comments` (the JSON API does not hit
  the deprecated `projectCards` path) and returns the parsed comment list.
  Updated SKILL.md Work Protocol Step 1 (Fetch) to direct comment reads through
  `--json comments`, never `--comments`, and documented the sanctioned path in
  `docs/spec.md` (new "Reading issue comments" section) and `docs/contract.md`
  (`invokes.gh` note + `never` entry barring the `--comments` path). Added
  `test/test-comments-json-guard.py`: an e2e guard asserting no rabbit-issue
  script or SKILL.md uses `gh issue view … --comments`, that the `--json
  comments` form is present, and that `gh_issue_comments` parses the JSON form
  against the gh shim. Lockstep minor bump of `feature.json` / `spec.md` /
  `SKILL.md` (1.5.0 -> 1.6.0) and `contract.md` (1.4.0 -> 1.5.0). SKILL.md
  version bump means the deployed copy under `.claude/skills/` drifts until the
  dispatcher republishes (republish_needed).

- **v1.5.0 (drop invented "normal mode" of rabbit-feature-touch, #436):** The
  Work Protocol (SKILL.md Step 5, "If the user confirms to proceed") said to
  invoke `rabbit-feature-touch` in **normal mode** — but that skill defines no
  such mode; its only behavioural fork is the default full seven-step TDD cycle
  vs. the lightweight Override Path, so "normal mode" was a prompt-tier
  ambiguity with no source artifact. Replaced it with the accurate vocabulary:
  invoke `rabbit-feature-touch` via its default full seven-step TDD cycle (NOT
  the Override Path), passing the issue title + body as the request text. Also
  corrected the matching spec invariant in `docs/spec.md` ("What this feature
  does NOT define" → "The TDD cycle"), which had described the same
  relationship with the parallel invented term "issue mode" and the wrong
  invocation direction. Added invariant #6 to `test/test-skill-presence.py`:
  the SKILL.md body MUST NOT contain "normal mode" and MUST name the
  default/full seven-step TDD cycle. Lockstep minor bump of `feature.json` /
  `spec.md` / `SKILL.md` (1.4.0 -> 1.5.0) and `contract.md` (1.3.0 -> 1.4.0).
  SKILL.md version bump means the deployed copy under `.claude/skills/` drifts
  until the dispatcher republishes (republish_needed).

- **v1.4.0 (filed-by:<source> provenance label, #496):** `file-item.py` now
  accepts `--filed-by <source>` and stamps the created issue with a
  machine-readable provenance label `filed-by:<source>` (e.g. `filed-by:loop`,
  `filed-by:human`) via the existing `ensure_labels` bootstrap. The flag
  **defaults to `human`** when omitted — the conservative attribution, so an
  unattributed filing is never mis-counted as autonomous-loop self-discovery;
  only callers that know they are the evolve loop pass `--filed-by loop`. The
  label is additive: the other five labels (`bug`/`enhancement`,
  `rabbit-managed`, `feature:<name>`, `priority:<level>`) are unchanged. This
  makes loop-performance metrics — self-discovery rate, discovery→fix ratio —
  derivable by querying the `filed-by:loop` label. A follow-up wires the loop's
  own discovered-issue / decomposition filings to pass `--filed-by loop`.
  Added regression tests in `test/test-file-item.py` (explicit `--filed-by
  loop`, the omitted-flag `filed-by:human` default, and that the existing five
  labels are otherwise unchanged). Lockstep minor bump of `feature.json` /
  `spec.md` / `SKILL.md` (1.3.0 -> 1.4.0) and `contract.md` (1.2.0 -> 1.3.0);
  `file-item.py` module docstring 1.0.0 -> 1.1.0. SKILL.md version bump means
  the deployed copy under `.claude/skills/` drifts until the dispatcher
  republishes (republish_needed).

- **v1.3.0 (flat docs/ layout, #399 Phase 2b):** Relocated the feature's spec
  artifacts from `specs/` to the flat `docs/` layout via `git mv`
  (`specs/spec.md` -> `docs/spec.md`, `specs/contract.md` -> `docs/contract.md`,
  root `CHANGELOG.md` -> `docs/CHANGELOG.md`, this file); the now-empty
  `specs/` directory was removed. The pre-existing `docs/bugs/` subtree is
  preserved as a sibling of the flat doc files — never replaced or nested
  under. This rides on the contract feature's dual-read resolver
  (`resolve_spec_path`), which prefers the flat `docs/` layout and falls back
  to `specs/`, so the move keeps the feature green. Spec/contract content is
  unchanged (location only). Updated rabbit-issue's own spec-aware tooling for
  the flat layout: `test/test-spec-presence.py` resolver now prefers `docs/`
  over `specs/` and its cutover invariant pins that `docs/spec.md` exists and
  `specs/` is gone; the `rabbit-issue` SKILL Work Protocol dual-read prose and
  the `test-gh-helper-resolves-rabbit-repo.py` docstring reference were updated
  to the flat `docs/` layout. Added the E2E regression test
  `test/test-specs-layout.py`, which pins the flat layout, asserts `docs/bugs/`
  is retained, the root `CHANGELOG.md` is gone, and the contract resolver
  targets `docs/`. Lockstep minor bump of `feature.json` / `spec.md` /
  `SKILL.md` (1.2.3 -> 1.3.0) and `contract.md` (1.1.2 -> 1.2.0). Deprecation
  of the upstream `specs/` fallback is owned by issue #399 Phase 3.

- **v1.2.3 (persist not-planned reason-text, #476):** `item-status.py close
  --reason not-planned` now persists the validated `--reason-text` as the close
  comment on the same `gh issue close` call, instead of validating then
  discarding it. With `--comment` also supplied, the reason-text leads
  (separated by a blank line); with only `--reason-text` it is the comment on
  its own. The `completed` close path is unchanged. Added three regression
  tests in `test/test-item-status.py`. Lockstep bump of `feature.json` /
  `spec.md` / `SKILL.md` (1.2.2 -> 1.2.3) and the `item-status.py` module
  docstring (1.1.0 -> 1.1.1).

- **v1.2.2 (specs/ migration, #399 Phase 2):** Migrated the spec surface from
  `docs/spec/` to the canonical `specs/` layout via `git mv` (superseded by
  v1.3.0's flat `docs/` layout). The `docs/bugs/` directory was retained.
  Resolved the `feature.json` backlink in `spec.md` and made the feature's own
  spec-aware tooling dual-read. Lockstep patch bump of `feature.json` /
  `spec.md` / `SKILL.md` (1.2.1 -> 1.2.2) and `contract.md` (1.1.1 -> 1.1.2).

- **v1.2.1 (owner sweep, #416):** Changed the feature owner from an individual
  login to the team identity `rabbit-workflow team` across every owner-bearing
  location in the feature (feature.json, spec/contract frontmatter, SKILL.md
  frontmatter, every runtime-script docstring, and the test-helper / test-module
  owner markers). Added `test/test-owner-sweep.py`. Lockstep patch bump of
  `feature.json` / `spec.md` / `SKILL.md` (1.2.0 -> 1.2.1) and `contract.md`
  (1.1.0 -> 1.1.1).

- **v1.2.0 and earlier:** Pre-sweep history of the GH-Issues wrapper (File /
  List / Work protocols, label schema, rabbit-managed safety guard, close-reason
  gating, and upstream-repo discovery), tracked lockstep across `feature.json`
  and the spec/contract frontmatter.
