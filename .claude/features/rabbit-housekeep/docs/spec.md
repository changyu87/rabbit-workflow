---
feature: rabbit-housekeep
version: 0.9.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when housekeeping is provided natively by the rabbit CLI as a first-class measured-reduction subcommand
status: active
---

# rabbit-housekeep — Spec

## Purpose

rabbit-housekeep distills the housekeeping-wave slim / line-reduction work
into a first-class, repeatable, user-facing capability. It manifests ONE skill
and ONE `/rabbit-housekeep` command that run measured verify-or-flag
housekeeping against a target in WAVES sized to the target's complexity, and
decompose cross-feature scope into per-feature work. The wave anchors on the
CONSUMING PROJECT's declared features (the user's project under
`rabbit-project/features/*` in a vendored install, or `.claude/features/*`
standalone) — never on rabbit-workflow's own framework features.

Cleanup runs in two dimensions: the DOC dimension (default, slimming doc
surfaces) and an OPT-IN CODE dimension (the `--code` selector, simplifying and
dead-code-pruning the feature's `src/`). In both, reduction is REPORTED, never
MANDATED: the ONE MANDATORY gate is behavior preserved (the feature's existing
test suite stays green). When there is dead, redundant, or simplifiable content
the wave removes it (`verdict: reduced`); when the target is already lean and
nothing is dead, the wave honestly reports `verdict: no-op` — an already-clean
SUCCESS, not a failure, never forced into a reword. Reduction is MEASURED with a
deterministic script; the housekeeping test asserts behavior preserved and that
named load-bearing tokens survive, guarding against load-bearing deletion
(dropping a script name, schema field, exit code, decision table, or
cross-reference).

## Surface

- `skills/rabbit-housekeep/SKILL.md` — the user-invocable skill.
- `commands/rabbit-housekeep.md` — the `/rabbit-housekeep` slash command, the
  user-facing entry point that resolves consuming-project scope and hands off
  to the skill.
- `scripts/resolve-housekeep-scope.py` — deterministic, mode-aware resolution
  of the CONSUMING PROJECT's feature set (vendored: `rabbit-project/features/*`,
  excluding rabbit's own; standalone: `.claude/features/*`).
- `scripts/measure-reduction.py` — deterministic per-artifact line accounting
  and before/after reduction diff.
- `scripts/check-script-backed.py` — deterministic scan of a target feature's
  `skills/*/SKILL.md`, `agents/*.md`, and `commands/*.md` bodies for
  orchestration steps that violate the spec-rules §4 Script-Backed
  Orchestration standard (a NEW verify-or-flag dimension).
- `scripts/wave-automerge.py` — deterministic gated auto-merge DECISION for a
  user-installed wave's PR: `decide` reads the wave's HANDOFF gates, PR
  mergeable/CI state, and honest-reduction verdict and emits `merge` only on
  all-green, else `leave-open` with the failing gate named; `gather` collects
  the PR-side signals via `gh pr view`.
- `docs/spec.md`, `docs/contract.md`, `docs/CHANGELOG.md`, `feature.json`,
  `test/run.py` — feature scaffolding.

## Methodology

The skill applies the prove-it-dead-or-flag protocol from coding-rules.md §6,
embedded VERBATIM in the SKILL.md body (not paraphrased): each claim runs its
matching deterministic check, then proven-dead content is DELETEd, proven-live
KEPT, and an unverifiable claim FLAGged as a `housekeeping`-tagged sub-issue so
one uncertain sentence never stalls the wave.

Slim decisions apply coding-rules §2 (Simplicity First) and §7 (Parenthetical
Clarity). Schemas, decision tables, exit codes, script names, and
cross-references are preserved verbatim. History lives in `docs/CHANGELOG.md`;
the doc surfaces describe the current design only.

## Waves and decomposition

The skill sizes the work into waves by target complexity:

- A single-feature tidy is ONE wave: measure before, verify-or-flag-and-remove,
  measure after, report.
- A multi-feature or repo-wide mandate is MANY waves: the scope is DECOMPOSED
  into one bounded per-feature unit each, reusing the decomposition dispatch
  shape. Each unit is filed as a `housekeeping`-tagged sub-issue via the
  rabbit-issue filing script, and the parent→children linkage is recorded so
  the rabbit-auto-evolve parent-close machinery closes the parent when every
  child closes.

Each per-feature unit executes through the governed TDD path —
rabbit-feature-touch, which dispatches the TDD subagent. The dispatch carries
the `housekeep: measured reduction wave` signal that feature-touch's
reduction-wave detection keys on, so the per-feature spec reduction rides ONE
governed RED->GREEN cycle: the subagent authors the spec reduction and its
gating test together, with no dispatcher pre-commit of the spec outside the
cycle and no forced no-spec-change escape hatch. The housekeeping test pattern
asserts the MANDATORY behavior-preserved gate (the existing test suite stays
green) and that the named load-bearing tokens survive; it REPORTS the measured
`verdict` (`reduced` or `no-op`) but does not mandate reduction.

## Tool-choice tiering

- Measurement, line accounting, and before/after diffing are SCRIPT-tier:
  `scripts/measure-reduction.py` owns them deterministically.
- Slim decisions (redundant vs load-bearing) are SPEC-tier directives that
  tightly constrain the subagent.
- Decomposition, dispatch, and parent-close reuse existing scripted
  machinery — rabbit-decompose's decomposition shape, rabbit-issue filing,
  and rabbit-auto-evolve's parent-close — not reinvented here.

## measure-reduction.py

Deterministic, stdlib-only, two subcommands (full interface in the script
docstring):

- `count [--docs-only | --code] <path> ...` — JSON of each text file's line
  count plus `__total__`; directories walked recursively, binary files skipped.
  The machine-first BEFORE/AFTER snapshot. With `--docs-only` (the DOC
  dimension, default), a directory argument is restricted to the DOC SURFACES a
  wave slims (`docs/spec.md`, `docs/contract.md`, `skills/*/SKILL.md`) and
  EXCLUDES `test/` and `docs/CHANGELOG.md`, so the mandated housekeeping test a
  wave adds under `test/` does not flip the Step-7 verdict. With `--code` (the
  OPT-IN code dimension), a directory argument is restricted to the feature's
  `src/` source files (`src/**/*.py`), excluding docs/, test/, and skills/ —
  symmetric to `--docs-only`. The two flags are mutually exclusive.
- `diff <before.json> <after.json>` — JSON with `per_artifact`,
  `total_delta` (after − before; negative means lines removed), `reduced`
  (true iff `total_delta < 0`), `verdict` (`reduced` when content was removed,
  else `no-op`), `removed_paths`, and `added_paths`.

Exit `0` success, `2` invocation error. The honest outcome is the `verdict`
field: `reduced` or `no-op` (already-clean SUCCESS). Reduction is REPORTED, not
MANDATED — the script reports, the caller's test asserts behavior preserved.

## Script-backed-orchestration verify-or-flag dimension

Housekeeping also enforces the spec-rules §4 **Script-Backed Orchestration**
standard as a NEW verification DIMENSION (not new machinery): an orchestration
step that involves a COMPUTED VALUE or MODE-AWARE BRANCHING MUST live in a
companion script under `scripts/` that the body invokes — not as prose or
inline bash; and a bash block carrying RUNTIME PLACEHOLDERS (e.g.
`<feature-name>`, `<branch-name>`) the model assembles at invocation time is
prompt-tier, not script-tier. The §4 read-only-informational exception holds:
simple read-only informational commands inline (e.g. `git log --oneline -5`)
and trivial one-liners are NOT flagged.

Detection is SCRIPT-tier (the check enforces the same tier it embodies):
`scripts/check-script-backed.py` deterministically scans the target feature's
`skills/*/SKILL.md`, `agents/*.md`, and `commands/*.md` bodies and reports each
non-conformant step. The disposition reuses housekeep's existing
prove-it-dead-or-flag machinery: each non-conformant step is FLAGged as a
`housekeeping`-tagged sub-issue (the Step 2 filing shape) naming the file, the
step, and the conversion target (move the logic into `scripts/`; the
SKILL/command invokes it). Straightforward conversions MAY be done inline
within a governed touch; complex orchestration is never silently rewritten.

## check-script-backed.py

Deterministic, stdlib-only (full interface in the script docstring):

- `scan <feature-dir>` — walk the feature's `skills/*/SKILL.md`, `agents/*.md`,
  and `commands/*.md` bodies, find every fenced bash block, and emit a JSON
  object `{"findings": [...], "count": N}`. Each finding records `file`,
  `line` (1-based start of the offending block), `reason` (one of
  `runtime-placeholder`, `computed-value`, `mode-aware-branching`), and
  `snippet`. Read-only informational commands and trivial one-liners are
  excluded, as is any block carrying an `<!-- example -->` marker on the line
  directly above its opening fence — a non-executable illustrative snippet that
  documents how to invoke a script, not a live step. The marker is NARROW: an
  unmarked live step with a placeholder STILL flags.

Exit `0` when the scan ran (regardless of whether findings were emitted), `2`
on invocation error (missing/bad feature-dir). The verdict is the `count`
field — the script reports, the caller's verify-or-flag disposition acts.

## Gated wave auto-merge

For a user-installed `/rabbit-housekeep` run (the manual skill invocation, NOT
the autonomous loop), a wave still CREATES its PR through the
rabbit-feature-touch path for the audit trail, but on green gates the PR is
auto-merged to `main` rather than left pending for the user to merge by hand.
Auto-merge is DEFAULT-ON for housekeep waves — they are mechanical and fully
gated — with an opt-out: the `--no-automerge` phrase in the housekeep request
creates the PR and leaves it open, exactly as a plain feature-touch PR. No
shared trust-mode config exists to reuse today (safety-governance and
rabbit-cage carry no `auto-merge` / `gated-merge` trust-mode key); aligning the
opt-out with a future shared trust-mode config is a follow-up enhancement, not
this feature's job.

The MERGE-OR-LEAVE-OPEN decision is a computed, gate-aware branch, so it is
SCRIPT-tier (spec-rules §4): `scripts/wave-automerge.py` owns it. The SKILL
builds the gating payload from the wave's signals — the HANDOFF gates
(`tdd_state`, `test_result`, `spec_compliance`), the honest-reduction `verdict`
from Step 7, and the PR-side `mergeable` / `merge_state_status` / `ci_status`
collected by the script's `gather` subcommand — and asks the script to
`decide`. The decision is `merge` ONLY when ALL hold: the HANDOFF gates are
green (`tdd_state: test-green`, `test_result: pass`, `spec_compliance: pass`),
the PR is mergeable/clean with green CI, AND the honest-reduction outcome held
(a measured `reduced` OR an honest already-clean `no-op` — a `no-op` is a
PASSING outcome, per the honest-gate semantics). Any failed gate yields
`leave-open` with the failing gate NAMED in `reasons`, leaving the PR OPEN for
human attention.

## wave-automerge.py

Deterministic, stdlib-only (full interface in the script docstring):

- `decide` — read a JSON gating payload on stdin and print a decision object
  `{"pr", "decision": "merge"|"leave-open", "reasons": [...]}`. Each gate that
  fails appends a NAMED reason, so a `leave-open` verdict is auditable and
  locatable. A missing signal a gate requires fails that gate CLOSED — auto-merge
  is opt-in to safety. The passing reduction verdicts are `reduced` and `no-op`.
- `gather --pr <N>` — collect the PR-side signals via
  `gh pr view <N> --json mergeable,mergeStateStatus,statusCheckRollup` and print
  `{"pr", "mergeable", "merge_state_status", "ci_status"}`; the caller merges
  these with the HANDOFF gates + verdict before calling `decide`.

Exit `0` on a printed decision (`decide` always exits 0 when the payload
parsed), `2` on invocation error (bad/empty JSON payload, missing `--pr`, bad
subcommand). The script makes the DECISION; the SKILL performs the resulting
`gh pr merge` on a `merge` decision.

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "0.1.0"` or later,
   `owner: "rabbit-workflow team"`, a valid `tdd_state`, non-empty `summary`,
   non-empty `deprecation_criterion`, and a `manifest` containing a
   `publish_skill` entry sourcing `skills/rabbit-housekeep/SKILL.md` AND a
   `publish_command` entry sourcing `commands/rabbit-housekeep.md`. The
   `surface.commands` list MUST name the command.

2. `skills/rabbit-housekeep/SKILL.md` MUST exist with YAML frontmatter
   declaring `name: rabbit-housekeep`, a description naming the wave-sized
   measured housekeeping behavior, a `version` in lockstep with `feature.json`,
   `owner: rabbit-workflow team`, and a `deprecation_criterion`.

3. The SKILL.md MUST embed coding-rules.md §6 ("Cleanup: Prove It Dead or Flag
   It") VERBATIM (byte-for-byte, not paraphrased), delimited by explicit
   BEGIN/END markers, so the governing policy is cited rather than restated.

4. The SKILL.md MUST document that rabbit-housekeep is a subagent-dispatching
   skill and MUST NOT be invoked inside an `Agent(...)` call (illegal
   two-level subagent nesting). It MUST name the constraint and direct
   parallelization to dispatch the underlying TDD subagent directly at
   level-1.

5. `scripts/measure-reduction.py` MUST provide deterministic per-artifact line
   accounting via a `count` subcommand and a before/after reduction verdict via
   a `diff` subcommand whose output reports `total_delta`, a boolean `reduced`
   flag, AND a `verdict` field whose value is `reduced` when content was removed
   and `no-op` when nothing changed (an honest already-clean outcome, REPORTED
   not MANDATED). `count` MUST accept a `--docs-only` flag that restricts a
   directory argument to the doc surfaces a wave slims (`docs/spec.md`,
   `docs/contract.md`, `skills/*/SKILL.md`), excluding `test/` and
   `docs/CHANGELOG.md`, AND a mutually-exclusive `--code` flag that restricts a
   directory argument to the feature's `src/` source files (`src/**/*.py`),
   excluding docs/, test/, and skills/.

6. `docs/contract.md` MUST exist with proper frontmatter and a JSON block
   declaring the cross-feature relationships: `invokes` names the TDD subagent
   dispatch (rabbit-feature-touch / tdd-subagent), the rabbit-decompose
   decomposition-shape reuse, the rabbit-issue filing script `file-item.py`,
   and the rabbit-auto-evolve parent-close machinery — every reuse declared in
   the machine-readable `invokes` block, never in trailing prose only;
   `provides` names the skill and the measurement and script-backed-check
   scripts; `never` includes editing files outside the target feature's
   directory and rewording without measured removal.

7. `scripts/check-script-backed.py` MUST provide a deterministic `scan`
   subcommand that walks a target feature's `skills/*/SKILL.md`, `agents/*.md`,
   and `commands/*.md` bodies and reports, as JSON, every orchestration step
   that violates spec-rules §4 Script-Backed Orchestration: a bash block with
   runtime placeholders, or a computed-value / mode-aware-branching step held
   as prose or inline bash instead of a companion `scripts/` invocation. It
   MUST NOT flag read-only informational commands, trivial one-liners (the
   §4 read-only-informational exception), or blocks explicitly marked
   illustrative via an `<!-- example -->` marker directly above the fence; that
   marker MUST stay NARROW so an unmarked live step with a placeholder still
   flags. Output reports a `findings` list and a `count`; exit `2` on
   invocation error.

8. The SKILL.md MUST embed spec-rules.md §4 Script-Backed Orchestration text
   VERBATIM (byte-for-byte, not paraphrased), delimited by explicit BEGIN/END
   markers, AND document the script-backed-orchestration verify-or-flag
   dimension: it invokes `scripts/check-script-backed.py` and routes each
   non-conformant step through the prove-it-dead-or-flag disposition (FLAG a
   `housekeeping`-tagged sub-issue naming the file, the step, and the
   conversion target).

9. `commands/rabbit-housekeep.md` MUST exist with YAML frontmatter declaring
   all six required keys (`name: rabbit-housekeep`, `description`, a `version`
   in lockstep with `feature.json`, `owner: rabbit-workflow team`, a
   `deprecation_criterion`, and `template_version`). It is a THIN user-facing
   entry point: it resolves consuming-project scope via
   `scripts/resolve-housekeep-scope.py`, hands off to the skill, and honors the
   no-Agent()-nesting constraint (the skill it invokes is subagent-dispatching).

10. `scripts/resolve-housekeep-scope.py` MUST provide a deterministic, mode-aware
    `list` subcommand that enumerates the CONSUMING PROJECT's feature names. In
    a vendored install it MUST return `rabbit-project/features/*` and EXCLUDE
    rabbit's own framework features under `.claude/features/*`; in a standalone
    install it MUST return `.claude/features/*`. Mode detection dual-accepts the
    `vendored` (canonical) / `plugin` (legacy) marker value with a structural
    fallback to a present `rabbit-project/` work tree. Bad invocation exits `2`.

11. The SKILL.md MUST keep the DOC dimension as the DEFAULT and document an
    OPT-IN CODE dimension selected by `--code`. The code dimension MUST state
    the priority order — SIMPLIFY first via the in-environment `code-simplifier`
    agent (preserving all functionality), then DEAD CODE removal applying the
    coding-rules §6 grep-for-callers protocol to `src/` symbols (none = dead →
    remove; unverifiable → FLAG a `housekeeping`-tagged sub-issue), then
    measured `src/` REDUCTION reported honestly — routed through the governed
    TDD path. It MUST state the ONE MANDATORY gate is behavior preserved (the
    feature's existing test suite stays green), that an already-clean target is
    an honest `no-op` SUCCESS, and that cleanup edits only the target feature's
    `src/`, never cross-feature.

12. `scripts/wave-automerge.py` MUST provide a deterministic `decide`
    subcommand that reads a JSON gating payload on stdin and emits a decision
    object reporting `decision: "merge"` ONLY when ALL gates hold — the HANDOFF
    gates green (`tdd_state: test-green`, `test_result: pass`,
    `spec_compliance: pass`), the PR mergeable/clean with green CI, AND the
    honest-reduction `verdict` a passing outcome (`reduced` OR `no-op`) — else
    `decision: "leave-open"` with each failing gate NAMED in `reasons`. A
    missing required signal fails its gate CLOSED. It MUST also provide a
    `gather --pr <N>` subcommand that collects the PR-side mergeable / merge
    state / CI signals via `gh pr view`. Bad invocation exits `2`. The SKILL.md
    MUST document gated wave auto-merge as DEFAULT-ON for user-installed waves
    with a `--no-automerge` opt-out, invoke `scripts/wave-automerge.py` for the
    decision, and merge the PR only on `decision: merge`.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Coverage:

- `test-measure-reduction.py` — E2E driving `count` and `diff` against
  fixture trees: correct totals, removal yields `reduced: true`, reword
  yields `reduced: false`, invocation error exits `2`, `count --docs-only`
  scopes a feature dir to its doc surfaces (excluding `test/` and
  `docs/CHANGELOG.md`) so a docs-shrink-plus-test-grow wave still reports the
  doc-scoped `reduced: true` verdict, `diff` reports an honest `verdict`
  (`no-op` for a no-change wave, `reduced` for a removal), and `count --code`
  scopes a feature dir to its `src/` source files.
- `test-skill-structure.py` — E2E asserting the skill is present and
  manifest-published, the coding-rules §6 block is embedded byte-for-byte
  verbatim, the spec-rules §4 Script-Backed Orchestration block is embedded
  byte-for-byte verbatim, the script-backed-orchestration verify-or-flag
  dimension is documented, and the subagent-dispatching no-Agent-nesting
  constraint is documented.
- `test-check-script-backed.py` — E2E driving `scan` against fixture feature
  trees: a SKILL.md with a runtime-placeholder bash block is flagged, a
  computed-value / mode-aware-branching prose step is flagged, a read-only
  informational one-liner and a script-backed invocation are NOT flagged, a
  block marked illustrative via `<!-- example -->` is skipped while an unmarked
  live step with a placeholder STILL flags, agents/*.md and commands/*.md
  bodies are scanned, and invocation error exits `2`.
- `test-user-facing-surface.py` — E2E asserting the `/rabbit-housekeep` command
  exists with the six required frontmatter keys (owner `rabbit-workflow team`,
  lockstep version), the manifest publishes it and `surface.commands` names it,
  `resolve-housekeep-scope.py list` returns the consuming project's features in
  vendored mode while EXCLUDING rabbit's own and returns `.claude/features/*`
  standalone, bad invocation exits non-zero, and the SKILL.md documents
  consuming-project targeting plus the scope script.
- `test-wave-automerge.py` — E2E driving `wave-automerge.py decide` with
  in-payload gating signals (no `gh` shell-out): all-gates-green + `reduced`
  merges, an honest `no-op` STILL merges, each failed HANDOFF gate / not-clean
  PR / red CI yields `leave-open` with the gate named in `reasons`, and a
  bad/empty JSON payload exits `2`.

## Out of Scope

- The TDD execution itself — owned by tdd-subagent and invoked through the
  rabbit-feature-touch path.
- The decomposition proposal UI — the decomposition dispatch shape is reused
  from rabbit-decompose, not reimplemented here.
- Sub-issue filing and lifecycle — owned by rabbit-issue (`file-item.py`).
- Decomposed-parent close-on-children-complete — owned by rabbit-auto-evolve.
