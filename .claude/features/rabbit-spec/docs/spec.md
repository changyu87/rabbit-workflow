---
feature: rabbit-spec
version: 1.20.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes native spec-lifecycle skills that supersede this feature
status: active
---

# rabbit-spec — Spec

## Purpose

rabbit-spec owns the rabbit workflow's spec-lifecycle surface: the
`rabbit-spec-creator` subagent drafts AND writes a feature's initial
`docs/spec.md`, and the `rabbit-spec-update` skill revises an existing one.
The initial-draft path is no longer a skill wrapper — an orchestrator assembles
the subagent's prompt with `scripts/dispatch-spec-creator.py` and dispatches
`rabbit-spec-creator` directly; the subagent writes the spec itself (its sole
write target is `docs/spec.md`) and returns only a `{path_written, summary}`
handoff so the orchestrator's context stays isolated from the full draft body.

## Surface

- `agents/rabbit-spec-creator.md` — the drafting subagent (writes `docs/spec.md`,
  returns `{path_written, summary}`)
- `scripts/dispatch-spec-creator.py` — input assembler for the subagent prompt
- `skills/rabbit-spec-update/SKILL.md` — dual-mode spec-revision skill

## Invariants

1. `feature.json` MUST declare `status: "active"`, `version: "1.1.0"` or
   later, `owner: "rabbit-workflow team"`, `tdd_state: "test-green"`,
   non-empty `summary`, non-empty `deprecation_criterion`, and a `surface`
   block that lists the agent at `agents/rabbit-spec-creator.md` and the
   input-assembler script at `scripts/dispatch-spec-creator.py`. The
   `surface.skills` list contains exactly `skills/rabbit-spec-update/SKILL.md`.
   The `manifest` contains a `publish_agent` entry sourcing the agent and a
   `publish_skill` entry sourcing `skills/rabbit-spec-update/SKILL.md`. The
   `prompts` array MUST contain exactly one entry with `id: "spec-create"`,
   `kind: "subagent"`, `inject` listing philosophy + coding-rules, and
   `slots: ["feature_name", "paths_globs", "paths_resolved"]`.

2. `agents/rabbit-spec-creator.md` MUST exist with YAML frontmatter declaring
   `name: rabbit-spec-creator`, `model: sonnet`, `version: 2.0.0` or later,
   and a `tools` list that grants `Write` and `Explore` alongside
   `Read, Grep, Glob` (it is no longer read-only). The body MUST:
    (a) Mandate that the subagent's SOLE write target is the feature's flat
        `docs/spec.md` — it writes exactly that one file and MUST NOT Write or
        Edit any other path. This single-target scope is load-bearing.
    (b) Mandate use of the **Explore** superpower for codebase reading where
        available (falling back to Read/Grep/Glob when it is not).
    (c) Mandate that the subagent returns ONLY a contracted
        `{path_written, summary}` handoff as its final message and MUST NOT
        echo the full spec body back (context isolation for the orchestrator).
   The agent's base name MUST start with `rabbit-` so that the deployed
   `.claude/agents/rabbit-spec-creator.md` satisfies
   `contract.lib.checks.check_naming` (Inv 10/15).

3. `scripts/dispatch-spec-creator.py` MUST be executable, carry a
   module-level docstring (Version/Owner/Deprecation criterion), and:
    (a) Accept `--feature-name <name>` (required) and `--paths <globs>`
        (optional; comma-separated, may be empty for standalone mode).
    (b) Resolve each glob via `glob.glob(<g>, recursive=True)`, dedupe,
        sort lexicographically, take first 50. When the deduped resolved
        count EXCEEDS the 50-file cap, the truncation MUST NOT be silent:
        the script MUST emit a structured note to STDERR (stdout stays a
        single prompt-file path so the orchestrator can parse it) reporting BOTH
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
    (f) The emitted prompt MUST live under the CANONICAL single-`.rabbit`
        runtime root: `<rabbit_runtime_root(repo_root)>/prompts/`, with NO
        doubled `.rabbit/.rabbit/` segment in either mode. This guarantee is
        ensured UPSTREAM by `contract/scripts/build-prompt.py`, which anchors
        its output dir at rabbit-cage's `rabbit_runtime_root` resolver
        (`.claude/features/rabbit-cage/lib/runtime_root.py`, Inv 52 — vendored:
        returns `repo_root` unchanged; standalone: appends `.rabbit`) in both
        modes. The dispatcher prints build-prompt's emitted path as-is and MUST
        NOT relocate it. Enforced by 2 tests under
        `.claude/features/rabbit-spec/test/`:
        `test-dispatch-prompt-path-no-double-rabbit.py` (vendored layout with
        `RABBIT_ROOT=<host>/.rabbit` → emitted path is single-`.rabbit` and the
        file exists there) and `test-dispatch-prompt-path-standalone.py`
        (standalone layout → path stays the canonical `<repo_root>/.rabbit/
        prompts/...`).

4. **`skills/rabbit-spec-update/SKILL.md` dual-mode feature_root resolution.**
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
   - `.rabbit/rabbit-project/features/<feature-name>/` — vendored mode (mode
     marker content equals `vendored`, the canonical value, or the legacy
     `plugin` value). The skill body MUST dual-accept BOTH spellings for the
     vendored branch — the same `_VENDORED_MODES = ("vendored", "plugin")`
     coexistence idiom every contract reader uses — so a marker that holds
     `vendored` resolves to the vendored feature_root and never silently
     falls through to the standalone path. The legacy `plugin` acceptance is
     dropped only once no install carries the older marker spelling.
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
   the standalone-mode branch (no unconditional uses); and by
   `test/test-rabbit-spec-update-vendored-mode.py` which asserts the body
   mentions `vendored` and places every `vendored` mention in the
   vendored/plugin branch context. Both wired into `test/run.py`.

5. **Spec-path layout: canonical flat `docs/` only.**
   The `rabbit-spec-update` skill and the drafting agent resolve the in-feature
   spec-file *layout* independently of the mode prefix (Inv 4). The single
   canonical layout is the FLAT `<feature_root>/docs/spec.md` (and
   `<feature_root>/docs/contract.md`). Every rabbit feature carries this flat
   layout; there is no `specs/` or legacy `docs/spec/` fallback.
   - `skills/rabbit-spec-update/SKILL.md` MUST resolve the target
     `<feature_root>/docs/spec.md` (and `<feature_root>/docs/contract.md`) for
     every Step 1 Read and the Step 4 Edit/Write of spec.md. `feature.json`
     stays at `<feature_root>/feature.json`. The skill body MUST name
     `docs/spec.md` as the spec-file path and MUST NOT describe any
     `specs/spec.md` or `docs/spec/spec.md` fallback.
   - `agents/rabbit-spec-creator.md` MUST name the flat `docs/spec.md` as its
     sole write target.
   Enforced by `test/test-spec-path-layout-canonical.py`
   (source-inspection of the `rabbit-spec-update` SKILL.md body and the agent
   body asserting canonical-only resolution; also asserts rabbit-spec's own
   flat-`docs/` layout) and the on-disk `test/test-docs-layout.py`. Both wired
   into `test/run.py`.

6. **Live surfaces carry current issue vocabulary.**
   rabbit-spec's live surfaces (`docs/spec.md`, `docs/contract.md`,
   `agents/rabbit-spec-creator.md`, `skills/rabbit-spec-update/SKILL.md`,
   `feature.json`) MUST describe request inputs and request classes using the
   current rabbit-issue vocabulary — "issue", "bug or enhancement", and
   "rabbit-managed issue" (GitHub's bug/enhancement taxonomy). The legacy
   custom-store abbreviation and phrase family, and the standalone
   request-class noun for the deferred-work bucket, MUST NOT appear as LIVE
   description. Enforced by `test/test-bb-terminology.py`, wired into
   `test/run.py`.

7. **Strict contiguous invariant numbering (opted in).**
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

8. **Script-backed orchestration: zero unmarked runtime-placeholder steps.**
   The feature's authored SKILL.md / agent / command bodies MUST carry zero
   `check-script-backed.py` findings (spec-rules §4 Script-Backed
   Orchestration). Live orchestration steps that compute a value or assemble a
   runtime placeholder belong in a companion `scripts/` invocation, not inline
   in a body. A fenced block that is non-executable documentation rather than a
   live step the model assembles — e.g. an ILLUSTRATIVE CLI synopsis, or the
   `rabbit-spec-creator` agent's contracted `{path_written, summary}` handoff
   schema — MUST carry the `<!-- example -->` exemption marker on the line
   directly above its opening fence so the scanner treats it as documentation.
   Enforced by `test/test-script-backed-clean.py` (asserts
   `.claude/features/rabbit-housekeep/scripts/check-script-backed.py scan` of
   the feature dir reports `count: 0`), wired into `test/run.py`.

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
