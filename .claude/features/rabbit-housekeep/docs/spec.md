---
feature: rabbit-housekeep
version: 0.2.1
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when housekeeping is provided natively by the rabbit CLI as a first-class measured-reduction subcommand
status: active
---

# rabbit-housekeep — Spec

## Purpose

rabbit-housekeep distills the housekeeping-wave slim / line-reduction work
into a first-class, repeatable capability. It manifests ONE skill that runs
measured verify-or-flag housekeeping against a target in WAVES sized to the
target's complexity, and decomposes cross-feature scope into per-feature work.

It guards two failure modes: reword-not-remove (reshuffling prose while line
counts stay flat) and load-bearing deletion (dropping a script name, schema
field, exit code, decision table, or cross-reference). Reduction is MEASURED
with a deterministic script — a negative line delta is the gate — and the
housekeeping test asserts named load-bearing tokens survive.

## Surface

- `skills/rabbit-housekeep/SKILL.md` — the user-invocable skill.
- `scripts/measure-reduction.py` — deterministic per-artifact line accounting
  and before/after reduction diff.
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

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "0.1.0"` or later,
   `owner: "rabbit-workflow team"`, a valid `tdd_state`, non-empty `summary`,
   non-empty `deprecation_criterion`, and a `manifest` containing a
   `publish_skill` entry sourcing `skills/rabbit-housekeep/SKILL.md`.

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
   `provides` names the skill and the measurement script; `never` includes
   editing files outside the target feature's directory and rewording without
   measured removal.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Coverage:

- `test-measure-reduction.py` — E2E driving `count` and `diff` against
  fixture trees: correct totals, removal yields `reduced: true`, reword
  yields `reduced: false`, invocation error exits `2`.
- `test-skill-structure.py` — E2E asserting the skill is present and
  manifest-published, the coding-rules §6 block is embedded byte-for-byte
  verbatim, and the subagent-dispatching no-Agent-nesting constraint is
  documented.

## Out of Scope

- The TDD execution itself — owned by tdd-subagent and invoked through the
  rabbit-feature-touch path.
- The decomposition proposal UI — the decomposition dispatch shape is reused
  from rabbit-decompose, not reimplemented here.
- Sub-issue filing and lifecycle — owned by rabbit-issue (`file-item.py`).
- Decomposed-parent close-on-children-complete — owned by rabbit-auto-evolve.
