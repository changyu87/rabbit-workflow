# Rabbit Workflow Redesign Spec

- **Owner**: rabbit-workflow team
- **Version**: 1.0.0
- **Date**: 2026-05-09
- **Deprecation criterion**: when Claude Code exposes a native workflow contract mechanism that supersedes the `contract` feature

---

## 1. Overview

This redesign reorganizes the rabbit workflow into a strict three-layer model — `policy` (rules), `contract` (templates/schemas/scripts that all features consume), and `rabbit-cage` (the runtime surface that Claude Code sees) — and treats every feature, including rabbit's own, as a uniformly-shaped feature directory recorded in a `registry.json`. Project-specific work lives in sibling `project-{name}/` roots, each carrying its own `project-map.json` and `features/registry.json`. Custom subagent files are eliminated; all dispatch goes through one script (`dispatch-feature-edit.sh`) that prepends the canonical policy block and uses `general-purpose` as `subagent_type`. Scope-guard becomes repo-wide default-deny. The result: one shape for every feature, one path for every dispatch, one boundary for every write, and a uniform full-TDD discipline on every feature touch.

---

## 2. Hierarchy

```
$ROOT/
  |- CLAUDE.md            # symlink -> .claude/features/rabbit-cage/CLAUDE.md
  |- README.md            # symlink -> .claude/features/rabbit-cage/README.md
  |- install.sh           # symlink -> .claude/features/rabbit-cage/install.sh
  |- .claude/
  |   |- settings.json      # symlink -> .claude/features/rabbit-cage/settings.json
  |   |- agents/            # symlink -> .claude/features/rabbit-cage/agents/
  |   |- commands/          # symlink -> .claude/features/rabbit-cage/commands/
  |   |- hooks/             # symlink -> .claude/features/rabbit-cage/hooks/
  |   |- skills/            # symlink -> .claude/features/rabbit-cage/skills/
  |   |- policy/            # symlink -> .claude/features/policy/
  |   |- contract/          # symlink -> .claude/features/contract/
  |   |- features/
  |       |- registry.json  # rabbit's feature registry (schema v1.0.0)
  |       |- rabbit-cage/   # the rabbit workflow itself, as a feature
  |       |   |- agents/      # surface: built-in subagent files (none custom; reserved)
  |       |   |- commands/    # surface: slash commands
  |       |   |- skills/      # surface: skill bundles
  |       |   |- hooks/       # surface: lifecycle hook scripts
  |       |   |- docs/
  |       |   |   |- spec/    # feature spec.md, contract.md
  |       |   |   |- bugs/    # bug filings, file names prefixed "rabbit-cage-"
  |       |- policy/        # the rules feature (split of work-guide.md)
  |       |   |- philosophy.md
  |       |   |- spec-rules.md
  |       |   |- coding-rules.md
  |       |   |- workflow-rules.md
  |       |   |- docs/
  |       |       |- spec/
  |       |       |- bugs/    # prefixed "policy-"
  |       |- contract/      # the meta-feature: templates, schemas, dispatch scripts
  |           |- templates/
  |           |- schemas/
  |           |- scripts/
  |           |- docs/
  |               |- spec/
  |               |- bugs/    # prefixed "contract-"
  |
  |- project-wang/          # an example downstream project (NOT a rabbit feature)
  |   |- project-map.json     # project root artifact (schema v1.0.0)
  |   |- features/
  |   |   |- registry.json    # wang's feature registry
  |   |   |- wang-rtl/
  |   |   |- wang-test/
  |   |- contract/            # project-specific contract overrides; higher precedence than rabbit contract
  |
  |- project-lee/
  |   |- project-map.json
  |   |- features/
  |   |   |- registry.json
  |   |- contract/
```

---

## 3. Schemas

### 3.1 `registry.json` v1.0.0

- **Owner**: the team that owns the enclosing feature container (rabbit-workflow team for `.claude/features/registry.json`; the project owner for `project-{name}/features/registry.json`)
- **Location**: every feature-container directory (`.claude/features/registry.json`, `project-{name}/features/registry.json`)
- **Purpose**: enumerate features in this container, locate their roots, declare their public surface and lifecycle metadata
- **Deprecation criterion**: superseded when Claude Code exposes a native feature-discovery API
- **Schema file**: `contract/schemas/registry.json.schema.json`

```json
{
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "features": {
    "auto-refresh": {
      "root": ".claude/features/auto-refresh",
      "version": "1.0.0",
      "tdd_state": "test-green",
      "summary": "Periodic policy re-injection via UserPromptSubmit hook.",
      "surface": {
        "hooks":    [".claude/hooks/rbt-refresh.sh"],
        "commands": [".claude/commands/rabbit-refresh.md", ".claude/commands/rabbit-set-threshold.md"],
        "agents":   [],
        "skills":   []
      },
      "bugs_root": ".claude/features/auto-refresh/docs/bugs",
      "deprecation_criterion": "when Claude Code exposes native policy injection hooks"
    }
  }
}
```

Field semantics:

- `schema_version` (string, required) — semver of this registry schema
- `owner` (string, required) — accountable team for this registry instance
- `features` (object, required) — keyed by feature name (kebab-case)
  - `root` (string, required) — repo-relative path to the feature directory
  - `version` (string, required) — semver of the feature itself
  - `tdd_state` (enum, required) — current TDD state from `tdd-step.sh`
  - `summary` (string, required) — one-line human description
  - `surface` (object, required) — files this feature publishes via `relink.sh`; keys: `hooks`, `commands`, `agents`, `skills`; values are repo-relative symlink targets the feature owns
  - `bugs_root` (string, required) — directory holding this feature's bug filings
  - `deprecation_criterion` (string, required) — explicit end-of-life condition

### 3.2 `project-map.json` v1.0.0

- **Owner**: the project owner (e.g., wang team for `project-wang`)
- **Location**: project root (`project-{name}/project-map.json`)
- **Purpose**: declare project name, source code root, and which source paths belong to which features
- **Not registered in rabbit's `registry.json`** — projects are not rabbit features
- **Deprecation criterion**: superseded when Claude Code exposes a native project-mapping mechanism
- **Schema file**: `contract/schemas/project-map.json.schema.json`

```json
{
  "schema_version": "1.0.0",
  "name": "project-wang",
  "path": "/absolute/path/to/source/root",
  "source_map": {
    "src/test/": "wang-test",
    "src/rtl/":  "wang-rtl"
  }
}
```

Field semantics:

- `schema_version` (string, required) — semver of this schema
- `name` (string, required) — project name; matches the `project-{name}/` directory
- `path` (string, required) — absolute path to the project's source code root
- `source_map` (object, required) — keys are paths **relative to `path`**; values are feature names registered in `project-{name}/features/registry.json`
- Unmapped paths are feature-free (unguarded by scope-guard)
- No overlapping source paths allowed; validated by `onboard consolidate`

---

## 4. Components

### 4.1 scope-guard v2

- **Owner**: `rabbit-cage` feature
- **Version**: 2.0.0
- **Purpose**: enforce repo-wide default-deny on writes; allow only writes inside an active scope or to settings files
- **Interface**: PreToolUse hook on `Write`/`Edit`/`MultiEdit` tools; reads `.rabbit-scope-active` marker file
- **Invariants**:
  - Repo root is determined by `git rev-parse --show-toplevel`
  - Any write **inside** the repo root is **denied** unless:
    - the target file basename is `settings.json` or `settings.local.json`, OR
    - a scope marker (`.rabbit-scope-active`) exists naming the feature whose write is in progress, AND the target path is under that feature's declared scope
  - Writes **outside** the repo root are unrestricted
  - Marker file format and lookup are owned by `dispatch-feature-edit.sh`
- **Deprecation criterion**: when Claude Code exposes per-feature write boundaries natively

### 4.2 `contract` feature

- **Owner**: rabbit-workflow team
- **Version**: 1.0.0
- **Purpose**: own all cross-feature templates, schemas, and dispatch scripts; provide artifacts to other features without ever modifying them
- **Interface**:
  - Templates (`contract/templates/`):
    - `spec-template.md` — every feature's `docs/spec/spec.md` must conform
    - `contract-template.md` — every feature's `docs/spec/contract.md` must conform
    - `bug-template.json` — mandatory fields for every bug filing
    - `triage-template.md` — output format for `rabbit-triage.sh`
    - `feature.json.template` — scaffold for new feature metadata
    - `subagent-launch-template.txt` — policy block + scope marker + structured input contract
    - `project-map-template.json` — template for `project-map.json`
    - `registry-template.json` — template for `registry.json`
  - Schemas (`contract/schemas/`):
    - `feature.json.schema.json`
    - `registry.json.schema.json`
    - `bug.json.schema.json`
    - `project-map.json.schema.json`
  - Scripts (`contract/scripts/`):
    - `policy-block.sh` — builds the canonical policy block; moved from `subagent-policy-injection`
    - `dispatch-feature-edit.sh` — the only legal Agent dispatch path
    - `rebuild-registry.sh` — rebuilds `registry.json` from on-disk feature dirs
    - `relink.sh` — idempotent; reads each feature's `surface` from `registry.json`; creates/refreshes all symlinks
    - `render-template.sh <template> <output> <key=value>...` — fills a template
    - `check-maps-consistent.sh` — PR-time validator: `registry.json` matches on-disk reality
    - `rabbit-triage.sh <feature-dir> <bug-name>` — loads bug + feature, builds one-shot triage Agent call
- **Invariants**:
  - Every template carries `template_version` in its frontmatter for coexistence tracking
  - The contract feature provides; it never directly edits another feature
  - All scripts read inputs from declared paths only; no implicit lookups
- **Deprecation criterion**: when Claude Code exposes a native workflow contract mechanism

### 4.3 `policy` feature

- **Owner**: rabbit-workflow team
- **Version**: 1.0.0
- **Purpose**: hold the canonical rule text fed to subagents; split of the legacy `work-guide.md`
- **Interface**:
  - `philosophy.md` — unchanged from prior; fed to **all** subagents
  - `spec-rules.md` — Part I of work-guide (Construction Rules); fed to **spec/plan** subagents only
  - `coding-rules.md` — Part II of work-guide (Karpathy code-editing discipline); fed to **code-touching** subagents only
  - `workflow-rules.md` — Part III (Hard Rules R1–R9) plus the new sections below; fed to **all** subagents
- **Invariants**:
  - Rule files are read-only artifacts referenced by name from `policy-block.sh` via `--include`
  - Splitting is content-only; the canonical wording of the original work-guide.md is preserved per section
- **Deprecation criterion**: when Claude Code exposes a native subagent-policy injection point

`workflow-rules.md` MUST contain these sections:

- **Subagent-driven by construction** — every implementation touch goes through a dispatched subagent via `dispatch-feature-edit.sh`. The main session reads, decides, dispatches, verifies. It does not edit files.
- **Full TDD on every feature touch** — any add/edit/delete of a feature, including a typo fix or comment deletion, MUST go through the full TDD step sequence. No partial flows. The discipline is uniform because partial TDD is how drift sneaks in.
- **Token/compliance tradeoff is the user's call** — full TDD costs tokens. The cost is intentional — drift costs more. The user always retains the judgment of whether to dispatch at all. The rule is: if you touch a feature, you run the full discipline. Choosing not to touch is always available.
- **Hard rules index (R1–R9)** — see Section 6.

### 4.4 `onboard` skill (rabbit feature)

- **Owner**: rabbit-workflow team
- **Version**: 1.0.0
- **Purpose**: scaffold and maintain `project-{name}/` directories and their maps
- **Interface** (sub-commands of the `rabbit-project` skill):
  - `init <name>` — scaffold `project-{name}/` (directories + `project-map.json` from template + `features/registry.json` from template). Does NOT touch `.claude/features/registry.json`.
  - `set-path <name> <path>` — set or change the `path` field in `project-map.json`
  - `map <name> <source-path> <feature-name>` — add or edit a `source_map` entry
  - `consolidate <name>` — non-interactive; sync `project-map.json` with `features/registry.json`; called automatically post-TDD
- **Invariants**:
  - Registered in rabbit's `.claude/features/registry.json` (it IS a rabbit feature)
  - Contract changes are out of scope for `onboard`; they go through TDD on the `contract` feature
  - `consolidate` is wired into `tdd-step.sh` at the `test-green` transition alongside `rebuild-registry.sh`:

    ```
    rebuild-registry.sh             # refresh features/registry.json
    rabbit-project consolidate      # sync project-map.json with registry (if project context)
    ```

- **Deprecation criterion**: when project scaffolding is offered by a native Claude Code mechanism

### 4.5 `dispatch-feature-edit.sh`

- **Owner**: `contract` feature
- **Version**: 1.0.0
- **Location**: `contract/scripts/dispatch-feature-edit.sh`
- **Purpose**: the only legal path from main session to an implementation subagent
- **Interface**: invoked by main session with a feature name and a structured task input
- **Procedure**:
  1. Read the appropriate `registry.json` to find the feature root
  2. If the feature is a project feature: read `project-map.json` to determine source scope
  3. Touch the scope marker (`.rabbit-scope-active`) naming the feature
  4. Build the policy block via `policy-block.sh --include <relevant-rule-files>`; rule selection depends on the task class (spec / code / mixed)
  5. Append the feature's `docs/spec/spec.md` and `docs/spec/contract.md` as context
  6. Load contracts in precedence order: project contract first (if applicable), rabbit contract second; project values shadow rabbit values
  7. Invoke `Agent` with `subagent_type: general-purpose` and the assembled prompt
  8. After the Agent returns: remove the scope marker, run validators, call `tdd-step.sh` for the appropriate transition
- **Invariants**:
  - Every built prompt begins with the sentinel string `RABBIT-POLICY-BLOCK-v1` for PR-time detective grep
  - No direct `Agent` calls bypassing this script are allowed; PR-time check enforces sentinel presence
  - Scope marker is always removed in a trap, even on subagent failure
- **Deprecation criterion**: when Claude Code exposes a native policy-injecting dispatch hook

### 4.6 `rabbit-triage.sh`

- **Owner**: `contract` feature
- **Version**: 1.0.0
- **Location**: `contract/scripts/rabbit-triage.sh`
- **Purpose**: replace `rabbit-vet.md`; build a one-shot Agent triage call from a bug filing + feature context
- **Interface**: `rabbit-triage.sh <feature-dir> <bug-name>`
- **Procedure**:
  1. Load `<feature-dir>/docs/bugs/<bug-name>.json` (validated against `bug.json.schema.json`)
  2. Load the feature's `docs/spec/spec.md` and `docs/spec/contract.md`
  3. Render `triage-template.md` with the loaded context
  4. Build the policy block via `policy-block.sh` (workflow + coding rule files)
  5. Invoke `Agent` with `subagent_type: general-purpose` and the assembled prompt
  6. Capture the `TRIAGE:` block from the Agent response and write it to `vet-triage.json`
- **Invariants**:
  - Triage output conforms to `triage-template.md`
  - Main session never closes a bug without a fresh `vet-triage.json` from this script (R7)
  - `--skip-vet-reason` is reserved for scoped agents; main session is forbidden from using it
- **Deprecation criterion**: when triage is integrated into a native Claude Code workflow

---

## 5. Deprecations

| What                                                     | Replaced by                                              | Archive path                                                         |
|----------------------------------------------------------|----------------------------------------------------------|----------------------------------------------------------------------|
| `.claude/agents/rabbit-vet.md`                           | `contract/scripts/rabbit-triage.sh`                      | `archive/2026-05-09-pre-redesign/agents/rabbit-vet.md`               |
| `.claude/agents/rabbit-breeder.md`                       | `contract/scripts/dispatch-feature-edit.sh`              | `archive/2026-05-09-pre-redesign/agents/rabbit-breeder.md`           |
| `.claude/features/vet/`                                  | `contract/templates/triage-template.md`                  | `archive/2026-05-09-pre-redesign/features/vet/`                      |
| `.claude/features/breeder/`                              | `policy/workflow-rules.md` (convention text)             | `archive/2026-05-09-pre-redesign/features/breeder/`                  |
| `.claude/features/subagent-policy-injection/`            | `contract/scripts/policy-block.sh`                       | `archive/2026-05-09-pre-redesign/features/subagent-policy-injection/`|
| `.claude/work-guide.md`                                  | `policy/{spec,coding,workflow}-rules.md`                 | `archive/2026-05-09-pre-redesign/work-guide.md`                      |
| `maps.json` (everywhere)                                 | `registry.json`                                          | n/a — rename only                                                    |

---

## 6. Hard Rules (R1–R9)

| Rule | Statement                                                                                                                                  | Enforcement                                                                                       |
|------|--------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| R1   | Branch per feature; never work on main.                                                                                                    | `.claude/features/hard-rules/scripts/check-no-main-edits.sh`                                      |
| R2   | Opus for brainstorming / spec / planning subagents.                                                                                        | `.claude/features/hard-rules/scripts/check-opus-for-planning-agents.sh`                           |
| R3   | Tests are end-to-end, no human intervention.                                                                                               | `.claude/features/hard-rules/scripts/check-tests-non-interactive.sh <feature-dir>`                |
| R4   | TDD step transitions go through `tdd-step.sh`.                                                                                             | `breeder` subagent policy + PR review; manual `tdd_state` edits forbidden                         |
| R5   | Unified work model: features live anywhere, same discipline applies.                                                                       | Scope-guard detects feature dirs by `feature.json` presence, not path prefix                      |
| R6   | Every Agent dispatch prepends the canonical policy block.                                                                                  | `policy-block.sh` produces it; `dispatch-feature-edit.sh` always invokes it; sentinel grep at PR  |
| R7   | Vet before close; main session never skips.                                                                                                | `bug-status.sh` gate; `--skip-vet-reason` reserved to scoped agents; PR review                    |
| R8   | Every feature touch (any scope, any size) runs full TDD.                                                                                   | scope-guard v2 denies writes without active scope marker; `tdd-step.sh` gates all transitions     |
| R9   | Project-level contract wins over rabbit contract at conflict.                                                                              | `dispatch-feature-edit.sh` loads project contract first, rabbit contract second; project shadows  |

---

## 7. Implementation Order

| Step | Description                                                                                                                                                         | Depends on | Verify by                                                                                       |
|------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------------|
| 1    | Create `policy/` feature: split `work-guide.md` into `philosophy.md`/`spec-rules.md`/`coding-rules.md`/`workflow-rules.md`; author new sections in `workflow-rules.md`. | —          | All four files exist; `workflow-rules.md` contains the four required sections; TDD test-green   |
| 2    | Create `contract/` feature: templates, schemas, scripts (including `policy-block.sh` moved from `subagent-policy-injection`).                                       | 1          | All listed templates/schemas/scripts present; templates carry `template_version`; TDD test-green |
| 3    | Migrate existing features to consume contract templates; archive `vet/`, `breeder/`, `subagent-policy-injection/` under `archive/2026-05-09-pre-redesign/`.         | 2          | No feature retains a private copy of a template now owned by `contract/`; archive paths populated |
| 4    | Reshape feature dirs to absorb `agents/`, `commands/`, `hooks/`, `skills/`, `docs/`; update `install.sh` to delegate to `relink.sh`; rename `maps.json` -> `registry.json` everywhere. | 3          | `relink.sh` is idempotent across two runs; no `maps.json` remains; `registry.json` validates    |
| 5    | Ship `scope-guard.sh` v2.0.0 (repo-wide default-deny + allowlist); add R8 + R9 to `hard-rules`.                                                                     | 4          | A write outside an active scope and outside settings is denied; R8/R9 listed in `hard-rules/spec.md` |
| 6    | Replace `rabbit-vet.md` with `contract/scripts/rabbit-triage.sh`; archive the old agent file.                                                                       | 5          | `rabbit-triage.sh <feature> <bug>` produces a `vet-triage.json` conforming to `triage-template.md` |
| 7    | Delete `rabbit-breeder.md`; finalize `dispatch-feature-edit.sh` as the only dispatch path; add sentinel detective check.                                            | 6          | Sentinel `RABBIT-POLICY-BLOCK-v1` present in every dispatched prompt; PR check fails on absence |
| 8    | Wire `rebuild-registry.sh` + `rabbit-project consolidate` into `tdd-step.sh test-green`; add `check-maps-consistent.sh` to PR gates; create `onboard` skill as a feature. | 7          | `test-green` triggers both scripts; PR gate fails on registry/disk drift; `onboard` registered  |

---

## 8. Open Questions

None. All decisions are settled.
