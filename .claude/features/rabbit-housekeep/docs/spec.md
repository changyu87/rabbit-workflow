---
feature: rabbit-housekeep
version: 0.5.0
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

It guards two failure modes: reword-not-remove (reshuffling prose while line
counts stay flat) and load-bearing deletion (dropping a script name, schema
field, exit code, decision table, or cross-reference). Reduction is MEASURED
with a deterministic script — a negative line delta is the gate — and the
housekeeping test asserts named load-bearing tokens survive.

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
rabbit-feature-touch, which dispatches the TDD subagent. The housekeeping
test pattern asserts BOTH the measured reduction (`measure-reduction.py diff`
reports a negative total delta) AND that the named load-bearing tokens survive.

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

- `count <path> ...` — JSON of each text file's line count plus `__total__`;
  directories walked recursively, binary files skipped. The machine-first
  BEFORE/AFTER snapshot.
- `diff <before.json> <after.json>` — JSON with `per_artifact`,
  `total_delta` (after − before; negative means lines removed), `reduced`
  (true iff `total_delta < 0`), `removed_paths`, and `added_paths`.

Exit `0` success, `2` invocation error. The reduction verdict is the
`reduced` field — the script reports, the caller's test gates.

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
   a `diff` subcommand whose output reports `total_delta` and a boolean
   `reduced` flag.

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

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Coverage:

- `test-measure-reduction.py` — E2E driving `count` and `diff` against
  fixture trees: correct totals, removal yields `reduced: true`, reword
  yields `reduced: false`, invocation error exits `2`.
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

## Out of Scope

- The TDD execution itself — owned by tdd-subagent and invoked through the
  rabbit-feature-touch path.
- The decomposition proposal UI — the decomposition dispatch shape is reused
  from rabbit-decompose, not reimplemented here.
- Sub-issue filing and lifecycle — owned by rabbit-issue (`file-item.py`).
- Decomposed-parent close-on-children-complete — owned by rabbit-auto-evolve.
