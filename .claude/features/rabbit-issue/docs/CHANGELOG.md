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

- **v1.11.1 (measured-reduction housekeeping wave, closes #814; child of
  #794):** Verify-or-flag prose reduction of the doc surfaces per
  coding-rules §6/§2/§7, with zero behavior or contract change. Cut redundant
  restatement and restated rationale: the provenance validation paragraph's
  duplicate "validation guarantees…" sentence, the housekeeping flag's
  boolean-switch restatement of its own table plus the `gh issue edit
  --add-label` history aside, the safety-invariant queue-agreement rationale,
  the User-install-backend history clause, and the Purpose duplicate sentence
  in spec.md; in SKILL.md, the provenance/housekeeping prose that duplicates
  the spec sections it already points to, the File-Protocol flag re-explanation,
  the close-without-work rejected-phrase enum (now a pointer to spec
  §Lifecycle), and the decorative Lifecycle ASCII state diagram (the precise
  bullets are retained). spec.md 203 → 193, SKILL.md 260 → 243 (−27 doc-surface
  lines); contract.md was already lean (pure JSON block) and is unchanged
  except its version. All load-bearing tokens preserved (invariant ids, label
  schema incl. `housekeeping`, the `filed-by:` enum, code tokens). Added
  `test-label-schema-pinned.py`: a guard asserting every documented label token
  survives in spec.md and contract.md and that the provenance enum names both
  non-human values, so a future reduction cannot silently drop a label token.
  Four-way version lockstep 1.11.0 → 1.11.1 (feature.json + spec.md + SKILL.md;
  contract.md 1.9.0 → 1.9.1). SKILL.md changed, so the deployed copy under
  `.claude/skills/` drifts until the dispatcher republishes (republish_needed).

- **v1.11.0 (first-class `housekeeping` category label, closes #800):** The
  `housekeeping` tag is now first-class. `file-item.py` gains a `--housekeeping`
  boolean flag that appends the `housekeeping` label to the created issue's
  label set in the same `gh issue create` call (auto-created via the existing
  `ensure_labels` bootstrap); omit it for non-housekeeping issues. This
  replaces the ad-hoc 2-step file-then-`gh issue edit --add-label` dance, so a
  housekeeping-wave sub-issue is tagged in ONE deterministic filing step.
  Added `housekeeping` to the documented label schema as a sanctioned category
  label: the spec.md label table gains a `housekeeping` row plus a new
  §Housekeeping label subsection, the SKILL.md Label Schema / File Protocol /
  Scripts Reference document the flag, and the contract `issue_labels` list
  gains `housekeeping`. The label is additive — the type / `feature:` /
  `priority:` / optional `filed-by:` labels are unchanged. Four-way version
  lockstep 1.10.0 → 1.11.0 (feature.json + spec.md + SKILL.md; contract.md
  1.8.0 → 1.9.0). Script Version line: file-item.py 1.3.0 → 1.4.0. Tests:
  `test-file-item.py` asserts `--housekeeping` adds the label, omitting it does
  not, the label is additive against the base set, and it composes with
  `--filed-by`. SKILL.md changed, so the deployed copy under `.claude/skills/`
  drifts until the dispatcher republishes (republish_needed).

- **v1.10.0 (remove rabbit-managed application — coexistence step 3 of #753,
  part of #760):** The FINAL "remove last" cleanup. Now that selection is
  actionability-based (#758) and provenance is migrated (#759), nothing
  depends on `rabbit-managed`. `file-item.py` STOPS applying the
  `rabbit-managed` label to newly filed issues (the label is dropped from the
  applied set; `type` / `feature:` / `priority:` / optional `filed-by:` are
  unchanged). `list-items.py` SELECTION switches off the `--label
  rabbit-managed` gh filter onto the ACTIONABILITY basis — it lists only issues
  carrying a valid `feature:<name>` label (filtered in Python, consistent with
  rabbit-auto-evolve's fetch-queue). Removed the residual `rabbit-managed`
  mention from the `_gh.py` actionability-guard docstring. Prose: dropped the
  `rabbit-managed` row from the spec.md / SKILL.md label schema and from the
  contract `issue_labels` list. The descriptive phrase "rabbit-managed issue
  surface" (= managed by rabbit, not the label) is retained per the sanctioned
  terminology. Four-way version lockstep 1.9.0 → 1.10.0 (feature.json +
  spec.md + SKILL.md; contract.md 1.7.0 → 1.8.0). Script Version lines:
  file-item.py 1.2.0 → 1.3.0, list-items.py 1.0.0 → 1.1.0, _gh.py 1.3.0 →
  1.4.0. Tests: `test-file-item.py` asserts `rabbit-managed` is ABSENT from
  the applied label set; `test-list-items.py` asserts the gh list call no
  longer passes `--label rabbit-managed` and that non-actionable
  (no-`feature:`) issues are excluded. Cross-feature `rabbit-managed`
  references in rabbit-auto-evolve and contract/workspace-structure.json are
  out of this feature's scope (barrier subagents 2 and 3 of #760).

- **v1.9.0 (filed-by fixed enum + actionability guard — coexistence step 2 of
  #753, closes #759):** Cleaned the `filed-by:` provenance scheme into a FIXED
  ENUM `{rabbit, autonomous-evolve}` with human as the UNTAGGED default.
  `file-item.py` now validates `--filed-by`: omit it for human (no label
  stamped), pass `rabbit` (bot/wrapped script) or `autonomous-evolve` (the
  evolve loop); the legacy `loop`, the literal `human`, and any other or
  space-bearing value are REJECTED before any gh call, so polluted values
  (e.g. `filed-by:tdd-subagent (#685)`) can never recur. Legacy `filed-by:loop`
  semantics map onto `filed-by:autonomous-evolve`; `filed-by:human` drops to
  untagged. Rebased the `_gh.py` safety guard from a `rabbit-managed` basis
  onto ACTIONABILITY: `item-status.py close`/`reopen` now refuse issues lacking
  a valid `feature:` label (a raw hand-filed issue with no labels stays out of
  rabbit's reach), aligning with the actionability basis the queue adopted in
  coexistence step 1 (#758). COEXISTENCE: `rabbit-managed` APPLICATION is
  UNTOUCHED — `file-item.py` still stamps it; its removal is step 3 (#760).
  Four-way version lockstep 1.8.1 → 1.9.0 (feature.json + spec.md + SKILL.md;
  contract.md 1.6.0 → 1.7.0). Tests: `test-file-item.py` rewrites filed-by
  cases to the enum; `test-rabbit-managed-guard.py` rebased to actionability
  (refuses no-`feature:` issue, permits an actionable one).

- **v1.8.1 (housekeeping round 2 — measured dead-prose removal, #686):**
  REMOVAL pass under #639 (prove-it-dead-or-flag) and #677 (success = lines
  deleted, not tags scrubbed). Total md reduction: 524 → 464 lines (−60,
  −11.5%). `skills/rabbit-issue/SKILL.md` (290 → 249): deleted the
  "Why This Shape" rationale section (pure historical narration of the
  retired rabbit-file design — the live routing fact survives in Overview);
  removed the duplicated SHA/history negative-space paragraph from Lifecycle
  (spec §SHA/event history is authoritative); collapsed the verbatim 6-row
  Label-Schema table to a prose summary pointing at spec §Label schema;
  trimmed the duplicated projectCards rationale and dead `specs/spec.md`
  fallback from the Work Protocol (spec is authoritative; specs/ cutover is
  complete and test-pinned); collapsed the filed-by rationale to a terse
  operational pointer. `docs/spec.md` (185 → 166): deleted the
  git-remote-removal history paragraph (dead historical burden — the live
  resolution order remains); deleted the dead "live smoke test" clause
  (grep-proven absent: no smoke-test artifact exists) and the feature's own
  TDD-bootstrap narration; collapsed the redundant third projectCards
  paragraph and the filed-by metrics over-explanation to single authoritative
  statements. `docs/contract.md` (49, unchanged) and the runtime scripts/test
  suite were left untouched — every contract key is load-bearing and the
  e2e/static suite already pins every preserved behavior. #639 checks per
  deletion: `--fix-commits` (grep: never existed in code), `live smoke test`
  (grep: absent), `git remote get-url origin` (grep: removed from _gh.py),
  `specs/` fallback (test-spec-presence pins cutover complete). No new test
  files (md-only mandate); all suites GREEN before and after.

- **v1.8.0 (retire legacy B/B terminology on live surfaces):** Replaced the
  legacy "bug-and-backlog (B/B)" / standalone "backlog" custom-store vocabulary
  on the live surfaces with current rabbit-issue terminology — "issue" / "bug or
  enhancement" / "rabbit-managed issue" (GitHub's bug/enhancement taxonomy).
  `docs/spec.md`: Purpose now says GH Issues is "rabbit's issue store for bugs
  and enhancements"; the Projects-v2 NOT-defined bullet now says "file a
  separate issue" instead of "backlog". `skills/rabbit-issue/SKILL.md`:
  description and Overview now say "rabbit-managed issue surface"; the
  branch-store narration says "branch-backed item storage" (B/B abbreviation
  dropped). `feature.json` summary now narrates "retired branch-backed item
  store" instead of "bug-and-backlog (B/B) storage". Historical narration of the
  retired custom store is preserved; only the dead vocabulary is removed. The
  literal `origin/bug-backlog-files` branch name (a real historical artifact)
  stays as-is on contract.md and SKILL.md. New static test
  `test/test-bb-terminology.py` asserts no live "B/B" abbreviation or
  "bug-and-backlog" vocabulary remains on the four live surfaces (RED with 7
  violations -> GREEN). Lockstep minor bump of `feature.json` / `spec.md` /
  `SKILL.md` (1.7.0 -> 1.8.0); `contract.md` unchanged (1.6.0). SKILL.md
  changed, so the deployed copy under `.claude/skills/` drifts until the
  dispatcher republishes (republish_needed).

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
