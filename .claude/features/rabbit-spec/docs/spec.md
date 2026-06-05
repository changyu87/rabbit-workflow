---
feature: rabbit-spec
version: 1.15.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
status: active
---

# rabbit-spec — Spec

## Purpose

rabbit-spec owns the rabbit workflow's spec-lifecycle skills: `rabbit-spec-create`
drafts a feature's initial `docs/spec.md`, and `rabbit-spec-update` revises an
existing one. The drafting work is done by a read-only subagent
(`rabbit-spec-creator`, tool-restricted to Read/Grep/Glob); each skill is a thin
orchestration wrapper.

## Surface

- `skills/rabbit-spec-create/SKILL.md` — spec-drafting skill
- `skills/rabbit-spec-update/SKILL.md` — dual-mode spec-revision skill
- `agents/rabbit-spec-creator.md` — the read-only drafting subagent
- `scripts/dispatch-spec-create.py` — prompt assembler invoked by the skill

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "1.1.0"` or
   later, `owner: "rabbit-workflow team"`, `tdd_state: "test-green"`,
   non-empty `summary`, non-empty `deprecation_criterion`, and a `surface`
   block that lists the skill at `skills/rabbit-spec-create/SKILL.md`, the
   agent at `agents/rabbit-spec-creator.md`, and the dispatch script at
   `scripts/dispatch-spec-create.py`. The `manifest` MUST contain a
   `publish_skill` entry sourcing the skill and a `publish_agent` entry
   sourcing the agent. The `prompts` array MUST contain exactly one entry
   with `id: "spec-create"`, `kind: "subagent"`, `inject` listing
   philosophy + coding-rules, and `slots: ["feature_name", "paths_globs", "paths_resolved"]`.

2. `agents/rabbit-spec-creator.md` MUST exist with YAML frontmatter declaring
   `name: rabbit-spec-creator`, `tools: Read, Grep, Glob` (exact comma-separated
   list — no `Write`/`Edit`/`Bash`), `model: sonnet`, and `version: 1.1.0` or
   later. The body describes the read-only drafting task and names the flat
   `docs/spec.md` as the draft target. The tool restriction is
   load-bearing — it makes side-effects impossible regardless of what the
   agent attempts. The agent's base name MUST start with `rabbit-` so that the
   deployed `.claude/agents/rabbit-spec-creator.md` satisfies
   `contract.lib.checks.check_naming` (Inv 10/15).

3. `scripts/dispatch-spec-create.py` MUST be executable, carry a
   module-level docstring (Version/Owner/Deprecation criterion), and:
    (a) Accept `--feature-name <name>` (required) and `--paths <globs>`
        (optional; comma-separated, may be empty for standalone mode).
    (b) Resolve each glob via `glob.glob(<g>, recursive=True)`, dedupe,
        sort lexicographically, take first 50. When the deduped resolved
        count EXCEEDS the 50-file cap, the truncation MUST NOT be silent:
        the script MUST emit a structured note to STDERR (stdout stays a
        single prompt-file path so the skill can parse it) reporting BOTH
        the number inspected and the number dropped — the note text MUST
        contain the substring `dropped` and the integer dropped count
        (e.g. `NOTE: resolved <N> files; capped at 50, <M> dropped`).
        When the deduped resolved count is at or below the cap, NO such
        note is emitted (silent success). Enforced by
        `test/test-dispatch-truncation-not-silent.py` (>cap reports the
        dropped count on stderr; <=cap emits no note).
    (c) Invoke `python3 <repo_root>/.claude/features/contract/scripts/build-prompt.py
        --callable-id spec-create --slot feature_name=<name> --slot
        paths_globs=<globs> --slot paths_resolved=<newline-joined>` as a
        subprocess; print the resulting prompt-file path to stdout on
        success; exit nonzero on subprocess failure.
    (d) Stdlib only (argparse, glob, os, subprocess, sys, pathlib).
    (e) `<repo_root>` MUST be resolved via `Path(__file__).resolve().parents[4]` —
        NOT via `subprocess git rev-parse --show-toplevel` and NOT via `os.getcwd()`.
        Both forbidden mechanisms point at the user-project root rather than the
        rabbit root in plugin mode (rabbit lives under `.rabbit/.claude/`),
        breaking the build-prompt.py path; `parents[4]` resolves correctly in
        both the dev workspace and a plugin `.rabbit/` install. Enforced by 3 tests
        under `.claude/features/rabbit-spec/test/`: plugin-layout resolution,
        standalone-layout resolution from external cwd, and nested-git-repo immunity.

4. `skills/rabbit-spec-create/SKILL.md` MUST exist with YAML frontmatter
   declaring `name: rabbit-spec-create`, a description naming both standalone
   and plugin modes, `version: 1.1.0` or later, `owner: rabbit-workflow team`,
   and a `deprecation_criterion`. The body documents the 4-step orchestration
   protocol (assemble prompt → dispatch agent → write to spec.md → report).

5. **`skills/rabbit-spec-update/SKILL.md` dual-mode feature_root resolution.**
   `skills/rabbit-spec-update/SKILL.md` MUST exist with YAML frontmatter
   declaring `name: rabbit-spec-update`, a description that names both
   standalone and plugin modes, `model: opus`, `version: 2.1.0` or later,
   `owner: rabbit-workflow team`, and a `deprecation_criterion`.
   The skill body MUST detect the rabbit mode from
   `<repo_root>/.rabbit/.runtime/mode` (written at SessionStart by
   rabbit-meta's `write_mode_marker`) BEFORE issuing any Read/Edit/Write
   against the target feature's spec.md, and resolve the feature_root prefix
   to:
   - `.claude/features/<feature-name>/` — standalone mode (mode marker
     absent or content equals `standalone`).
   - `.rabbit/rabbit-project/features/<feature-name>/` — plugin mode (mode
     marker content equals exactly `plugin`).
   Every subsequent path reference in the skill body (Step 1 Read of the
   target spec.md, Step 1 optional reads of contract.md / feature.json /
   implementation files, Step 4 Edit/Write of spec.md, and the
   "abort if directory does not exist" guard) MUST use the resolved
   feature_root prefix — NOT the literal `.claude/features/` hardcode.
   The impl-suggestion path `.rabbit/impl-suggestion-<feature-name>.json`
   is mode-agnostic (always lives under `<repo_root>/.rabbit/`) and is
   exempt from the prefix rewrite. Mirroring pattern: `rabbit-feature-scaffold`
   SKILL.md's `## Modes` section is the reference implementation.
   Enforced by `test/test-rabbit-spec-update-dual-mode-paths.py` which
   greps the SKILL.md body for: (a) at least one literal mention of
   `.rabbit/.runtime/mode`, (b) at least one literal mention of
   `.rabbit/rabbit-project/features/`, (c) every literal occurrence of
   `.claude/features/<feature-name>/` appears in a context that names
   the standalone-mode branch (no unconditional uses). Wired into
   `test/run.py`.

6. **Spec-path layout: canonical flat `docs/` only.**
   Both spec-lifecycle skills and the drafting agent resolve the in-feature
   spec-file *layout* independently of the mode prefix (Inv 5). The single
   canonical layout is the FLAT `<feature_root>/docs/spec.md` (and
   `<feature_root>/docs/contract.md`). Every rabbit feature carries this flat
   layout; there is no `specs/` or legacy `docs/spec/` fallback.
   - `skills/rabbit-spec-update/SKILL.md` MUST resolve the target
     `<feature_root>/docs/spec.md` (and `<feature_root>/docs/contract.md`) for
     every Step 1 Read and the Step 4 Edit/Write of spec.md. `feature.json`
     stays at `<feature_root>/feature.json`. The skill body MUST name
     `docs/spec.md` as the spec-file path and MUST NOT describe any
     `specs/spec.md` or `docs/spec/spec.md` fallback.
   - `skills/rabbit-spec-create/SKILL.md` MUST write the drafted body to the
     canonical flat `<dest_root>/docs/spec.md`. The skill body MUST name
     `docs/spec.md` as the destination and MUST NOT describe any
     `specs/spec.md` or `docs/spec/spec.md` fallback.
   - `agents/rabbit-spec-creator.md` MUST name the flat `docs/spec.md` as its
     draft target.
   Enforced by `test/test-spec-path-layout-canonical.py`
   (source-inspection of both SKILL.md bodies and the agent body asserting
   canonical-only resolution; also asserts rabbit-spec's own flat-`docs/`
   layout) and the on-disk `test/test-docs-layout.py`. Both wired into
   `test/run.py`.

7. **Live surfaces carry current issue vocabulary.**
   rabbit-spec's live surfaces (`docs/spec.md`, `docs/contract.md`,
   `skills/rabbit-spec-create/SKILL.md`, `skills/rabbit-spec-update/SKILL.md`,
   `feature.json`) MUST describe request inputs and request classes using the
   current rabbit-issue vocabulary — "issue", "bug or enhancement", and
   "rabbit-managed issue" (GitHub's bug/enhancement taxonomy). The legacy
   custom-store abbreviation and phrase family, and the standalone
   request-class noun for the deferred-work bucket, MUST NOT appear as LIVE
   description. Enforced by `test/test-bb-terminology.py`, wired into
   `test/run.py`.

8. **Strict contiguous invariant numbering (opted in).**
   rabbit-spec opts into the contract feature's strict CONTIGUOUS
   invariant-numbering tier by declaring `"contiguous_invariants": true` at
   the top level of `feature.json`. Its invariants MUST therefore be numbered
   contiguously 1..N with no holes — the contract check
   `check_invariant_monotonic_order` rejects any gap for an opted-in feature.
   When an invariant is removed, survivors are renumbered to close the hole
   via the deterministic reflow tool
   `.claude/features/contract/scripts/reflow-invariants.py`; removed numbers
   and their history live only in `docs/CHANGELOG.md`. Enforced by
   `test/test-contiguous-invariants-optin.py`, wired into `test/run.py`.

## Tech Stack

Python 3 stdlib only.

## Tests

`test/run.py` invokes every `test-*.py` file under `test/`. Each invariant
above names its enforcing test in its "Enforced by" clause; each test file's
module docstring states what it asserts.

## Out of Scope

- The user-code globs themselves and their semantics — owned by
  `rabbit-feature`.
- The prompt template body at
  `.claude/features/contract/templates/prompts/spec-create.txt` — owned by
  `contract` per Inv 57.
