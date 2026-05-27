# Rabbit User-Interfacer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task corresponds to one or more `rabbit-feature-touch` cycles — the rabbit workflow handles fine-grained TDD red/green/refactor inside each cycle. Plan-level steps describe the *dispatcher* actions, not per-line edits.

**Goal:** Ship the user-interfacer development cycle — making rabbit installable as a vendored plugin in any user project, with drift-protected Claude on day 1 (Tier 1) and opt-in per-feature spec-as-memory + scope-guard via enhanced `rabbit-feature-new` (Tier 2). Defers TDD-on-user-code and B/B-on-user-code to later cycles.

**Architecture:** Per-project vendored install at `<user-project>/.rabbit/` (no embedded `.git`). Two modes auto-detected at session start (plugin vs standalone). Tier 1 = policy block auto-loaded by `.rabbit/CLAUDE.md`. Tier 2 = `rabbit-feature-new <name> <path-glob>` maps user code to a feature with spec-seeding subagent; scope-guard reads `project-map.json` and blocks unsanctioned edits with a one-shot bypass mechanism.

**Tech Stack:** Python 3 (sole scripting tech stack — rabbit-cage Inv 17, contract Inv 8). Stdlib-only for everything (no external deps per the established pattern). Shell `touch` for user-driven markers.

**Spec source:** `docs/superpowers/specs/2026-05-27-rabbit-user-interfacer-design.md` (v0.2.0).

---

## Architecture overview — 4 phases, 12 tasks

```
PHASE 1 — Foundation (serial; nothing else can land until these do)
  Task 1.1  Scaffold new feature: rabbit-meta             (NEW feature)
  Task 1.2  project-map.json schema in contract           (contract)
  Task 1.3  Mode-detection library function               (rabbit-meta)

PHASE 2 — Runtime (mostly serial after Phase 1; 2.2 depends on 2.1)
  Task 2.1  SessionStart mode-detection hook              (rabbit-cage)
  Task 2.2  Scope-guard plugin-mode + project-map reader  (rabbit-cage)
  Task 2.3  One-shot bypass-once marker mechanism         (rabbit-cage)

PHASE 3 — Surfaces (3.1 must precede 3.2; 3.3/3.4 parallel)
  Task 3.1  Spec-seeding subagent (NEW agent)             (NEW feature: spec-seeder)
  Task 3.2  rabbit-feature-new path-glob enhancement      (rabbit-feature)
  Task 3.3  .rabbit/CLAUDE.md template + generator        (rabbit-meta)
  Task 3.4  .rabbit/README.md template + generator        (rabbit-meta)

PHASE 4 — Install ritual (parallel; depends only on Phase 1)
  Task 4.1  docs/install.md (root install docs)           (no feature; root docs/)
  Task 4.2  Bootstrap one-liner / bootstrap.sh            (rabbit-meta)
```

**Total feature touches:** ~12 (one per task), spread across:
- 2 new features (`rabbit-meta`, `spec-seeder`)
- 3 existing features touched (`contract`, `rabbit-cage`, `rabbit-feature`)
- 1 root-docs add (`docs/install.md`)

**Parallelization map:** Within Phase 2 (after Phase 1), Tasks 2.1 → 2.2 → 2.3 are serial (each depends on the prior). Within Phase 3, 3.1 → 3.2 is serial; 3.3 / 3.4 / Phase 4 can all run in parallel against 3.1+3.2 once Phase 1 lands.

---

## File-touch map

### New files (created)

| Path | Purpose |
|---|---|
| `.claude/features/rabbit-meta/` | New feature dir (entry point for plugin-mode machinery: mode detection lib, CLAUDE.md/README.md generators, bootstrap helper) |
| `.claude/features/rabbit-meta/feature.json` | Feature manifest (`name=rabbit-meta`, `version=0.1.0`, `manifest`/`runtime` declarations) |
| `.claude/features/rabbit-meta/docs/spec/spec.md` | Spec: invariants for mode detection, CLAUDE.md generation, README.md generation, bootstrap |
| `.claude/features/rabbit-meta/docs/spec/contract.md` | Empty contract placeholder (per Inv 57 pattern) |
| `.claude/features/rabbit-meta/lib/mode_detection.py` | `detect_mode(cwd) -> "plugin" | "standalone"` |
| `.claude/features/rabbit-meta/lib/generate_claude_md.py` | Generate `.rabbit/CLAUDE.md` content for plugin mode |
| `.claude/features/rabbit-meta/lib/generate_readme.py` | Generate `.rabbit/README.md` with killer story |
| `.claude/features/rabbit-meta/templates/CLAUDE.md.template` | Plugin-mode CLAUDE.md template (policy @-imports + boundary note) |
| `.claude/features/rabbit-meta/templates/README.md.template` | User-facing README with killer story + 3-line "what to do next" |
| `.claude/features/rabbit-meta/scripts/bootstrap.sh` | Optional one-line install helper (or inline doc) |
| `.claude/features/rabbit-meta/test/run.py` | Test runner (delegates to test-*.py files) |
| `.claude/features/rabbit-meta/test/test-*.py` | Per-task tests (see each task) |
| `.claude/features/spec-seeder/` | New agent feature for the spec-seeding read-only subagent |
| `.claude/features/spec-seeder/feature.json` | Feature manifest with `prompts` entry for the seeder agent |
| `.claude/features/spec-seeder/docs/spec/spec.md` | Spec for the seeder's behavior (sections it produces, read-only invariant) |
| `.claude/features/spec-seeder/docs/spec/contract.md` | Empty contract placeholder |
| `.claude/features/spec-seeder/agents/spec-seeder.md` | Agent definition (model, tools=Read+Grep+Glob only) |
| `.claude/features/contract/templates/prompts/spec-seeder.txt` | Prompt template with slots: feature_name, paths_globs, paths_resolved |
| `.claude/features/spec-seeder/test/run.py`, `test/test-*.py` | Per-task tests |
| `.claude/features/contract/schemas/project-map.json.schema.json` | NEW schema: `{schema_version, features: {<name>: {paths, feature_dir}}}` |
| `.claude/features/contract/templates/project-map-template.json` | Already exists per spec.md Surface line 24 — verify or create empty greenfield template |
| `docs/install.md` | Root install docs (4-step ritual: clone, drop .git, commit, cd .rabbit && claude) |

### Existing files (modified)

| Path | Change |
|---|---|
| `.claude/features/rabbit-cage/feature.json` | Add new SessionStart runtime entry (mode-detection); add scope-guard plugin-mode args |
| `.claude/features/rabbit-cage/docs/spec/spec.md` | Add invariants: mode-detection hook behavior; scope-guard plugin-mode block-by-default; bypass-once consume semantics |
| `.claude/features/rabbit-cage/hooks/session-start-dispatcher.py` | Invoke `rabbit-meta.detect_mode` and write `.rabbit/.runtime/mode` |
| `.claude/features/rabbit-cage/hooks/scope-guard.py` | Add plugin-mode branch: read `project-map.json`, block declared-feature paths without scope-active marker, consume `.rabbit/.runtime/scope-bypass-once` |
| `.claude/features/rabbit-feature/skills/rabbit-feature-new/SKILL.md` | Document new `<name> <path-glob>...` invocation (plugin mode); MUST go through skill-creator |
| `.claude/features/rabbit-feature/scripts/rabbit-feature-new.py` (or equivalent) | Path-glob validation, non-overlap check, project-map.json registration, dispatch spec-seeder, scaffold feature dir |
| `.claude/features/rabbit-feature/docs/spec/spec.md` | Add invariants: plugin-mode invocation; path-glob validation; non-overlap; spec-seeding integration |
| `.claude/features/contract/docs/spec/spec.md` | Inv 51-style new invariant: project-map.json schema shape + location; check_project_map cross-feature lint (optional Phase 1 deliverable) |
| `.claude/features/contract/lib/checks.py` | Optionally add `check_project_map(features_root) -> CheckResult` |
| `.claude/workspace-structure.json` | Declare new `rabbit-meta` and `spec-seeder` nodes (per contract Inv 31) |

---

## Cross-feature touch flags

Each task below names a primary scope feature. The TDD subagent works under one scope marker. Any edit outside that scope MUST emit a HANDOFF with `cross_feature_dependency`. Pre-planned cross-feature dependencies:

| Task | Primary | Cross-feature edits (require separate dispatch) |
|---|---|---|
| 1.1 | rabbit-meta | `.claude/workspace-structure.json` (contract — declare rabbit-meta node) |
| 1.2 | contract | none (schema lives in contract) |
| 1.3 | rabbit-meta | none |
| 2.1 | rabbit-cage | none if `rabbit-meta.detect_mode` is just imported (lib reads only); else split |
| 2.2 | rabbit-cage | none (scope-guard owns its own logic) |
| 2.3 | rabbit-cage | none |
| 3.1 | spec-seeder | `.claude/features/contract/templates/prompts/spec-seeder.txt` (contract — new template); `.claude/workspace-structure.json` (contract); `.claude/features/contract/docs/spec/spec.md` Inv 57 to enumerate the new template |
| 3.2 | rabbit-feature | none if it only invokes seeder via Skill/Agent; else split |
| 3.3 | rabbit-meta | none |
| 3.4 | rabbit-meta | none |
| 4.1 | (no feature) | `docs/install.md` is root docs — use one-shot scope override |
| 4.2 | rabbit-meta | none |

---

# PHASE 1 — Foundation

These three tasks land first. Everything else depends on them.

## Task 1.1: Scaffold rabbit-meta feature

**Files:**
- Create: `.claude/features/rabbit-meta/feature.json`
- Create: `.claude/features/rabbit-meta/docs/spec/spec.md`
- Create: `.claude/features/rabbit-meta/docs/spec/contract.md`
- Create: `.claude/features/rabbit-meta/test/run.py`
- Create: `.claude/features/rabbit-meta/test/test-structure.py`
- Modify: `.claude/workspace-structure.json` (add node — cross-feature; HANDOFF expected)

**Approach:** Use `rabbit-feature-new` in standalone mode to scaffold the new feature. Then add per-spec invariants for what rabbit-meta will own. Defer all implementation tasks to later phases.

- [ ] **Step 1.1.1: Scaffold via rabbit-feature-new**

Run from main session (dispatcher), no scope marker needed (rabbit-feature-new is the scaffolder):

```
Skill("rabbit-feature-new", args: "rabbit-meta")
```

Expected: creates `.claude/features/rabbit-meta/` with feature.json, docs/spec/spec.md, docs/spec/contract.md, test/run.py from the contract templates.

- [ ] **Step 1.1.2: Author the initial spec**

Invoke rabbit-feature-spec to populate spec.md with the rabbit-meta invariants:

```
Skill("rabbit-feature-spec", args: "rabbit-meta Initial spec: rabbit-meta owns plugin-mode machinery — mode detection (Inv 1: detect_mode(cwd) returns 'plugin' if .rabbit basename + non-.rabbit-only parent, else 'standalone'); CLAUDE.md generation for plugin mode (Inv 2: contains policy @-imports + user-project boundary note); README.md generation with killer story (Inv 3); bootstrap helper (Inv 4). Tier-1 drift protection deliverables live here. No tdd-subagent on user code; no B/B on user code (deferred)."
```

- [ ] **Step 1.1.3: Dispatch rabbit-feature-touch with the scaffold + cross-feature HANDOFF**

The dispatch will hit the workspace-structure.json edit and emit HANDOFF for cross_feature_dependency: contract. Expected.

```
Skill("rabbit-feature-touch", args: "rabbit-meta Initial scaffolding — empty test runner only; defer mode-detection implementation to Task 1.3")
```

- [ ] **Step 1.1.4: Follow-up cross-feature cycle for contract.workspace-structure.json**

```
Skill("rabbit-feature-touch", args: "contract Add rabbit-meta node to .claude/workspace-structure.json per Inv 31 (declares all on-disk features). New feature scaffolded in Task 1.1.")
```

- [ ] **Step 1.1.5: Verify both green; PR or stop short per dispatcher protocol**

Run: `python3 .claude/features/rabbit-meta/test/run.py` → exit 0
Run: `python3 .claude/features/contract/test/run.py` → exit 0
Run: `python3 .claude/features/contract/scripts/enforcement/check-workspace-declares-all-features.py` (if exists, otherwise the test inside contract covers this) → exit 0

---

## Task 1.2: project-map.json schema in contract

**Files:**
- Create: `.claude/features/contract/schemas/project-map.json.schema.json`
- Modify: `.claude/features/contract/docs/spec/spec.md` (new invariant, e.g. Inv 59)
- Create: `.claude/features/contract/test/test-project-map-schema-shape.py`
- (Optional) Modify: `.claude/features/contract/lib/checks.py` (add `check_project_map`)
- (Optional) Create: `.claude/features/contract/scripts/enforcement/check-project-map.py` shim

**Schema shape:**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "schema_version": "1.0.0",
  "owner": "rabbit-workflow team",
  "deprecation_criterion": "when rabbit's user-project plugin model is superseded",
  "type": "object",
  "required": ["schema_version", "features"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "features": {
      "type": "object",
      "patternProperties": {
        "^[a-z][a-z0-9-]*$": {
          "type": "object",
          "required": ["paths", "feature_dir"],
          "additionalProperties": false,
          "properties": {
            "paths": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "feature_dir": {"type": "string"}
          }
        }
      },
      "additionalProperties": false
    }
  }
}
```

**Approach:** Standalone contract feature touch. Spec invariant + schema file + shape test. Mirror Inv 40 / 41 / 42 / 51 pattern.

- [ ] **Step 1.2.1: Invoke rabbit-feature-spec for contract**

```
Skill("rabbit-feature-spec", args: "contract Add Inv 59 (PROJECT-MAP schema): .claude/features/contract/schemas/project-map.json.schema.json MUST exist, be valid JSON, draft-07, carry spec-rules.md ownership metadata (schema_version/owner/deprecation_criterion), describe type:object with required [schema_version, features], features is object with patternProperties '^[a-z][a-z0-9-]*$' mapping to objects requiring [paths (array minItems 1 of strings), feature_dir (string)]. Shape enforced by test/test-project-map-schema-shape.py wired into test/run.py. project-map-template.json existing template also validated against the schema."
```

- [ ] **Step 1.2.2: Dispatch rabbit-feature-touch on contract**

```
Skill("rabbit-feature-touch", args: "contract Implement Inv 59 project-map schema as authored")
```

- [ ] **Step 1.2.3: Verify**

Run: `python3 .claude/features/contract/test/run.py` → exit 0
Manual: `python3 -c "import json; json.load(open('.claude/features/contract/schemas/project-map.json.schema.json'))"` → no error

---

## Task 1.3: Mode-detection library in rabbit-meta

**Files:**
- Create: `.claude/features/rabbit-meta/lib/mode_detection.py`
- Create: `.claude/features/rabbit-meta/lib/__init__.py` (empty)
- Modify: `.claude/features/rabbit-meta/docs/spec/spec.md` (refine Inv 1 with library signature)
- Create: `.claude/features/rabbit-meta/test/test-mode-detection.py`

**Approach:** Pure stdlib function. Walks ancestry of given cwd. Returns "plugin" if cwd basename is `.rabbit` AND parent has at least one non-`.rabbit` entry; else "standalone". No side effects — no file writes — that's the SessionStart hook's job in Task 2.1.

**Function signature:**
```python
def detect_mode(cwd: str) -> str:
    """Return 'plugin' if cwd is a rabbit plugin install dir; 'standalone' otherwise.

    Plugin signature: os.path.basename(cwd) == '.rabbit' AND the parent dir
    contains at least one entry whose name != '.rabbit'.
    """
```

**Test cases (test-mode-detection.py):**
- t1: cwd=`/tmp/proj/.rabbit` with parent `/tmp/proj` containing `src/`, `.rabbit/` → returns `"plugin"`
- t2: cwd=`/tmp/rabbit-clone` (no `.rabbit` ancestor) → returns `"standalone"`
- t3: cwd=`/tmp/.rabbit` but parent `/tmp` empty (only contains `.rabbit`) → returns `"standalone"` (degenerate; no project to plug in to)
- t4: cwd=`/home/user/proj/.rabbit/sub` (cwd basename != `.rabbit`) → returns `"standalone"`
- t5: missing cwd path → returns `"standalone"` (safe default)

- [ ] **Step 1.3.1: Spec the function**

```
Skill("rabbit-feature-spec", args: "rabbit-meta Refine Inv 1 with full signature: lib/mode_detection.py exports detect_mode(cwd: str) -> 'plugin' | 'standalone'. Plugin: cwd basename == '.rabbit' AND parent contains at least one non-'.rabbit' entry. Standalone otherwise (including missing cwd, sub-dirs of .rabbit, .rabbit at filesystem root with no project peers). Stdlib only (os.path, os.listdir). Pure function: no writes, no env reads. Test coverage: t1-t5 enumerated in impl-suggestion."
```

- [ ] **Step 1.3.2: Dispatch rabbit-feature-touch**

```
Skill("rabbit-feature-touch", args: "rabbit-meta Implement detect_mode library function per spec")
```

- [ ] **Step 1.3.3: Verify**

Run: `python3 .claude/features/rabbit-meta/test/run.py` → exit 0
Manual: `python3 -c "import sys; sys.path.insert(0, '.claude/features/rabbit-meta'); from lib.mode_detection import detect_mode; print(detect_mode('/tmp'))"` → `standalone`

---

# PHASE 2 — Runtime

Mode detection wired into Claude Code, scope-guard plugin-mode logic, one-shot bypass.

## Task 2.1: SessionStart mode-detection hook in rabbit-cage

**Files:**
- Modify: `.claude/features/rabbit-cage/hooks/session-start-dispatcher.py` (add mode-detection call)
- Modify: `.claude/features/rabbit-cage/feature.json` (add runtime.SessionStart entry for mode-detection)
- Modify: `.claude/features/rabbit-cage/docs/spec/spec.md` (new invariant: SessionStart writes mode file)
- Create: `.claude/features/rabbit-cage/test/test-session-start-mode-detection.py`

**Approach:** Add a new SessionStart runtime API that calls `rabbit-meta.detect_mode(os.getcwd())` and writes the result to `.rabbit/.runtime/mode`. The hook also creates `.rabbit/.runtime/` if absent.

**Cross-feature dep:** rabbit-cage imports from rabbit-meta. The `_dispatcher_lib.py` already enumerates feature runtime APIs by importing modules dynamically — this is a normal cross-feature read pattern, NOT a cross-feature write. Allowed.

- [ ] **Step 2.1.1: Spec the SessionStart entry**

```
Skill("rabbit-feature-spec", args: "rabbit-cage New invariant: SessionStart dispatcher MUST invoke a new runtime API write_mode_marker(repo_root) that calls rabbit-meta.lib.mode_detection.detect_mode(os.getcwd()), creates <repo_root>/.rabbit/.runtime/ if absent, writes the mode string to <repo_root>/.rabbit/.runtime/mode (literal 'plugin' or 'standalone'). Returns ok_result on success, error_result on filesystem error. Runtime.SessionStart entry: {api: 'write_mode_marker', args: {}}. Test: t1 plugin mode writes 'plugin'; t2 standalone writes 'standalone'; t3 idempotent re-run; t4 creates .runtime dir if missing."
```

Also requires a new runtime API in contract.lib.runtime — flag this in impl-suggestion as a cross-feature concern. Either:
- (a) The new `write_mode_marker` API lives in `contract.lib.runtime` (new entry in the closed runtime API set; requires Inv 41 update + Inv 47 update)
- (b) Or rabbit-cage's dispatcher inlines the logic without a runtime API

(a) is cleaner per the meta-contract pattern. Use (a). This expands the cross-feature scope of Task 2.1.

- [ ] **Step 2.1.2: First feature touch — contract (add runtime API)**

```
Skill("rabbit-feature-touch", args: "contract Add write_mode_marker(repo_root) to lib/runtime.py (returns ok_result/error_result; writes plugin|standalone to .rabbit/.runtime/mode; idempotent). Update Inv 47 to document the new API. Update Inv 41 RUNTIME schema closed-enum to include 'write_mode_marker'. Add test/test-runtime-write-mode-marker.py with the four cases."
```

- [ ] **Step 2.1.3: Second feature touch — rabbit-cage (wire it in)**

```
Skill("rabbit-feature-touch", args: "rabbit-cage Add runtime.SessionStart entry {api: 'write_mode_marker', args: {}} to feature.json. Add invariant for the SessionStart write behavior. Add end-to-end test that simulates SessionStart in a tmp dir and asserts .rabbit/.runtime/mode contents.")
```

- [ ] **Step 2.1.4: Verify both green**

Run: contract tests + rabbit-cage tests → all exit 0

---

## Task 2.2: Scope-guard plugin-mode + project-map reader

**Files:**
- Modify: `.claude/features/rabbit-cage/hooks/scope-guard.py` (add plugin-mode branch)
- Modify: `.claude/features/rabbit-cage/docs/spec/spec.md` (new invariants for plugin-mode behavior)
- Create: `.claude/features/rabbit-cage/lib/project_map_reader.py` (parse + glob-match)
- Create: `.claude/features/rabbit-cage/test/test-scope-guard-plugin-mode.py`

**Approach:** Read `.rabbit/.runtime/mode` at scope-guard fire time. If `plugin`, additionally consult `.rabbit/rabbit-project/project-map.json`. For any Edit/Write/Bash target that matches a declared feature's paths (using `pathspec` or stdlib `fnmatch`), check for `.rabbit/.runtime/scope-active-<name>` marker. If absent: DENY with the structured 3-option error message (matches the design's Section 4 prose verbatim).

**Decision tree (in scope-guard plugin-mode branch):**
1. Target in `.rabbit/.claude/**` or `.rabbit/rabbit-project/**` → DENY (always; only via update flow)
2. Target matches declared feature path AND `.rabbit/.runtime/scope-active-<name>` exists → ALLOW
3. Target matches declared feature path AND no marker → DENY with structured message
4. Target matches no declared feature path → ALLOW (undeclared = not under feature discipline)

**Glob library decision:** Use stdlib `fnmatch` for `**` and `*` patterns. If gitignore-style precision needed later, swap to `pathspec`. Defer until v2.

- [ ] **Step 2.2.1: Spec the plugin-mode branch**

```
Skill("rabbit-feature-spec", args: "rabbit-cage New invariants for scope-guard plugin mode: (a) when .rabbit/.runtime/mode contains 'plugin', scope-guard additionally consults .rabbit/rabbit-project/project-map.json; (b) decision tree as written in design v0.2.0 Section 4; (c) glob matching via stdlib fnmatch; (d) structured DENY message text matches design verbatim ([rabbit] BLOCKED: edit to <path> lands in declared feature <name> ...). Reader library at lib/project_map_reader.py exports load_map(repo_root) -> dict and match_path(target_path, map_dict) -> str|None returning feature name on match. Test coverage: t1 standalone unchanged; t2 plugin + no map = ALLOW; t3 plugin + declared path no marker = DENY w/ structured message; t4 plugin + declared path + marker = ALLOW; t5 plugin + .rabbit/.claude/** = DENY always."
```

- [ ] **Step 2.2.2: Dispatch rabbit-feature-touch**

```
Skill("rabbit-feature-touch", args: "rabbit-cage Implement scope-guard plugin-mode branch per spec; include lib/project_map_reader.py")
```

- [ ] **Step 2.2.3: Verify**

Run: `python3 .claude/features/rabbit-cage/test/run.py` → exit 0
Manual e2e: in a tmp dir set up as a plugin install, attempt edits with/without markers and confirm DENY/ALLOW behavior.

---

## Task 2.3: One-shot bypass-once marker

**Files:**
- Modify: `.claude/features/rabbit-cage/hooks/scope-guard.py` (consume-on-use logic)
- Modify: `.claude/features/rabbit-cage/docs/spec/spec.md` (invariant for bypass-once)
- Modify: `.claude/features/rabbit-cage/test/test-scope-guard-plugin-mode.py` (add t6, t7)

**Approach:** Before any Edit/Write evaluation in plugin mode (or even in standalone for parity), check for `.rabbit/.runtime/scope-bypass-once`. If present: consume (delete) atomically, then ALLOW the edit regardless of scope. If the edit fails for non-scope reasons, the marker is still consumed (prevents persistent bypass). Cannot be set by Claude (filesystem write to that path is itself blocked by scope-guard when no override is active — bootstrap problem; solved by the path being in scope-guard's allowlist alongside `.rabbit-scope-override`).

**Test cases (add to existing test file):**
- t6: bypass-once marker present + declared-feature-path edit + no scope-active marker = ALLOW; marker deleted afterward
- t7: bypass-once marker present + ALLOW-eligible edit (undeclared path) = ALLOW; marker still consumed (drained on use, not on guard hit)

- [ ] **Step 2.3.1: Spec the bypass-once mechanism**

```
Skill("rabbit-feature-spec", args: "rabbit-cage New invariant: scope-guard MUST consume .rabbit/.runtime/scope-bypass-once before evaluating any Edit/Write decision; consumption is atomic delete-then-evaluate (delete first so a failed edit cannot leave a persistent bypass). When consumed, ALLOW unconditionally for that one decision. The .rabbit/.runtime/scope-bypass-once path is added to scope-guard's allowlist exclusively for the user's touch command — Claude cannot programmatically create it (allowlist excludes Claude tools; user-typed Bash 'touch' satisfies via the bash command path). Add t6, t7 to test-scope-guard-plugin-mode.py."
```

- [ ] **Step 2.3.2: Dispatch rabbit-feature-touch**

```
Skill("rabbit-feature-touch", args: "rabbit-cage Implement bypass-once consume-before-evaluate logic per spec")
```

- [ ] **Step 2.3.3: Verify**

Run: `python3 .claude/features/rabbit-cage/test/run.py` → exit 0
Manual: set up plugin install, declare a feature, attempt edit (should DENY), `touch .rabbit/.runtime/scope-bypass-once`, attempt edit again (should ALLOW), verify marker is gone.

---

# PHASE 3 — Surfaces

The user-facing tier: feature mapping, spec seeding, CLAUDE.md and README.md generation.

## Task 3.1: Spec-seeding subagent (new feature)

**Files:**
- Create: `.claude/features/spec-seeder/feature.json`
- Create: `.claude/features/spec-seeder/docs/spec/spec.md`
- Create: `.claude/features/spec-seeder/docs/spec/contract.md`
- Create: `.claude/features/spec-seeder/agents/spec-seeder.md` (agent definition: model=sonnet, tools=Read,Grep,Glob ONLY — no Write/Edit/Bash since read-only)
- Create: `.claude/features/spec-seeder/scripts/dispatch-spec-seeder.py` (assembles prompt via build-prompt.py)
- Create: `.claude/features/contract/templates/prompts/spec-seeder.txt` (prompt template — CROSS-FEATURE)
- Create: `.claude/features/spec-seeder/test/run.py`, `test/test-*.py`
- Modify: `.claude/workspace-structure.json` (cross-feature)
- Modify: `.claude/features/contract/docs/spec/spec.md` Inv 57 (cross-feature; enumerate the new template)

**Spec-seeder behavior:** Reads (does NOT write) the matched user-project paths. Emits a draft `spec.md` body with sections: Purpose (one line, inferred from public exports), Paths governed (from project-map), Public surface (exported symbols / entry points), Current behaviour (bullet inventory), Known gaps (TODOs/FIXMEs/obvious smells), Open questions (for user to resolve). The subagent's output is consumed by `rabbit-feature-new` (Task 3.2) which writes the spec.md to disk.

**Prompt slots:** `feature_name`, `paths_globs` (comma-joined globs), `paths_resolved` (newline-joined resolved file list — capped at ~50 files to keep prompt bounded).

**Approach:** Three feature touches:
- (a) rabbit-feature-new style scaffold for spec-seeder
- (b) Cross-feature touch on contract to add the spec-seeder template + Inv 57 enumeration + workspace-structure declaration
- (c) Wire-up tests inside spec-seeder

- [ ] **Step 3.1.1: Scaffold spec-seeder via rabbit-feature-new**

```
Skill("rabbit-feature-new", args: "spec-seeder")
```

- [ ] **Step 3.1.2: Spec spec-seeder**

```
Skill("rabbit-feature-spec", args: "spec-seeder Spec the spec-seeding subagent: read-only agent (tools=Read,Grep,Glob; NO Write/Edit/Bash). Takes feature_name + paths globs + resolved file list (up to 50 files). Emits a draft spec.md body with six sections (Purpose, Paths governed, Public surface, Current behaviour, Known gaps, Open questions). agents/spec-seeder.md declares model=sonnet, tools enumerated. scripts/dispatch-spec-seeder.py mirrors dispatch-tdd-subagent.py pattern — assembles prompt via build-prompt.py with three slots. prompts entry in feature.json declares kind=subagent, inject=[policy/philosophy.md, policy/coding-rules.md], slots=[feature_name, paths_globs, paths_resolved]. Cross-feature template lives in contract.")
```

- [ ] **Step 3.1.3: First touch — spec-seeder feature**

```
Skill("rabbit-feature-touch", args: "spec-seeder Implement agent definition + dispatch script + feature.json prompts entry per spec; tests cover (a) dispatch script produces valid prompt, (b) agent runs read-only on a sample tree and emits draft spec, (c) agent refuses Write/Edit when restricted tools enforced")
```

- [ ] **Step 3.1.4: Second touch — contract (cross-feature template + Inv 57 enumeration + workspace-structure)**

```
Skill("rabbit-feature-touch", args: "contract Add templates/prompts/spec-seeder.txt (slots: feature_name, paths_globs, paths_resolved). Update Inv 57 to expand from EIGHT to NINE bundled templates including spec-seeder.txt. Update .claude/workspace-structure.json to declare spec-seeder node per Inv 31. Update test-templates-prompts-bundle.py to expect 9 files including the new one.")
```

- [ ] **Step 3.1.5: Verify**

Run: spec-seeder tests + contract tests → exit 0
Manual: invoke spec-seeder on a small sample dir, inspect emitted spec draft for the six sections.

---

## Task 3.2: rabbit-feature-new path-glob enhancement

**Files:**
- Modify: `.claude/features/rabbit-feature/skills/rabbit-feature-new/SKILL.md` (route through skill-creator per RED FLAG rule)
- Modify: `.claude/features/rabbit-feature/scripts/rabbit-feature-new.py` (or equivalent — confirm path during impl)
- Modify: `.claude/features/rabbit-feature/docs/spec/spec.md` (new invariants)
- Create: `.claude/features/rabbit-feature/test/test-feature-new-plugin-mode.py`

**Approach:** Detect plugin mode via `.rabbit/.runtime/mode`. If plugin: require `<name> <path-glob> [<path-glob>...]` positional args. Validate (under-project-root; non-overlap; ≥1 match). Scaffold the feature under `.rabbit/rabbit-project/features/<name>/` (NOT `.claude/features/`). Update `project-map.json`. Dispatch spec-seeder agent. Write seeded spec.md. Write empty contract.md placeholder.

**Validation order:** glob expansion → under-project-root check → overlap-with-declared-features check → ≥1 match check → scaffold → seeder → write outputs → register in project-map. Any failure: surface error and roll back partial scaffold.

- [ ] **Step 3.2.1: Spec the plugin-mode enhancement**

```
Skill("rabbit-feature-spec", args: "rabbit-feature New invariants for rabbit-feature-new in plugin mode: (a) accepts <name> <path-glob>+ positional args; (b) validates each glob resolves under parent of .rabbit/ (refuse globs leaving project boundary); (c) refuses overlap with any feature already declared in project-map.json (refuse with conflicting feature name); (d) refuses empty mappings (≥1 path must match); (e) scaffolds feature dir at .rabbit/rabbit-project/features/<name>/ NOT .claude/features/; (f) dispatches spec-seeder agent and writes its output to docs/spec/spec.md; (g) writes empty contract.md placeholder per Inv 57 pattern; (h) registers in project-map.json. Standalone mode unchanged (current behavior preserved). Test coverage: t1 plugin happy path; t2 glob outside boundary rejected; t3 overlap rejected; t4 empty match rejected; t5 standalone path still works.")
```

- [ ] **Step 3.2.2: SKILL.md route through skill-creator**

Per the SKILL.md ROUTING RED FLAG, the rabbit-feature-touch will route through skill-creator for the SKILL.md edit. The dispatcher must not Write/Edit the SKILL.md directly.

```
Skill("rabbit-feature-touch", args: "rabbit-feature Implement plugin-mode path-glob enhancement per spec. SKILL.md edit MUST go through skill-creator:skill-creator. Tests cover the five cases enumerated.")
```

- [ ] **Step 3.2.3: Verify**

Run: `python3 .claude/features/rabbit-feature/test/run.py` → exit 0
Manual e2e: in a tmp plugin install, run `rabbit-feature-new auth ../src/auth/**` and confirm: project-map.json updated, feature dir scaffolded at the right location, spec.md is non-empty (seeder output), contract.md is the empty placeholder.

---

## Task 3.3: .rabbit/CLAUDE.md template + generator

**Files:**
- Create: `.claude/features/rabbit-meta/templates/CLAUDE.md.template`
- Create: `.claude/features/rabbit-meta/lib/generate_claude_md.py`
- Modify: `.claude/features/rabbit-meta/docs/spec/spec.md` (Inv 2 refinement)
- Create: `.claude/features/rabbit-meta/test/test-generate-claude-md.py`

**Template content (`CLAUDE.md.template`):**

```markdown
# Rabbit Plugin Mode

> Install rabbit. `cd .rabbit/ && claude`. Your AI now reads policy on
> every action — no speculative refactors, no orphan files, no
> documentation you didn't ask for. When you want spec-as-memory for a
> slice of code, run `rabbit-feature-new <name> <path-glob>` — and now
> that slice has durable intent that survives every session.

You are operating on the user project at the parent directory.
Edit files at `../`, not inside `.rabbit/`.

@.claude/features/policy/philosophy.md
@.claude/features/policy/spec-rules.md
@.claude/features/policy/coding-rules.md
```

**Generator behavior:** `generate_claude_md(template_path, output_path)` reads the template and writes it to `output_path` verbatim (no slot substitution needed in v1 — the template is static). Idempotent: re-run is a no-op if content unchanged.

- [ ] **Step 3.3.1: Spec the template + generator**

```
Skill("rabbit-feature-spec", args: "rabbit-meta Refine Inv 2 + add Inv 5: templates/CLAUDE.md.template MUST exist with the killer-story prose + policy @-imports + user-project boundary note (verbatim from design v0.2.0 Section Tier 1 step 2). lib/generate_claude_md.py exports generate_claude_md(template_path, output_path) which writes template verbatim to output, idempotent (no-op if content matches). Test coverage: t1 template exists; t2 generator writes correct content; t3 idempotent on re-run; t4 template loaded by Claude Code (manual e2e — out of automated test scope).")
```

- [ ] **Step 3.3.2: Dispatch rabbit-feature-touch**

```
Skill("rabbit-feature-touch", args: "rabbit-meta Implement CLAUDE.md template + generator per spec")
```

- [ ] **Step 3.3.3: Verify**

Run: `python3 .claude/features/rabbit-meta/test/run.py` → exit 0
Manual: generate into tmp, inspect content, confirm @-imports resolve to existing policy files.

---

## Task 3.4: .rabbit/README.md template + generator

**Files:**
- Create: `.claude/features/rabbit-meta/templates/README.md.template`
- Create: `.claude/features/rabbit-meta/lib/generate_readme.py`
- Modify: `.claude/features/rabbit-meta/docs/spec/spec.md` (Inv 3 refinement)
- Create: `.claude/features/rabbit-meta/test/test-generate-readme.py`

**Template content (`README.md.template`):**

```markdown
# Rabbit (Plugin Mode)

> Install rabbit. `cd .rabbit/ && claude`. Your AI now reads policy on
> every action — no speculative refactors, no orphan files, no
> documentation you didn't ask for. When you want spec-as-memory for a
> slice of code, run `rabbit-feature-new <name> <path-glob>` — and now
> that slice has durable intent that survives every session.

## What to do next

1. **Just chat with Claude.** Drift protection is on by default. Try `claude` and ask for changes to files at `../` (your project root). Claude will read policy and stay surgical.
2. **Promote a slice to a feature** when you want spec-as-memory: `rabbit-feature-new <name> <path-glob>`. Example: `rabbit-feature-new auth ../src/auth/**`.
3. **Update rabbit** when a new version is available — `/rabbit-update` (TBD; see install docs).

For full install instructions, design, and contract details, see `https://github.com/changyu87/rabbit-workflow` (or your fork).
```

**Generator behavior:** Same as CLAUDE.md generator — verbatim template write, idempotent.

- [ ] **Step 3.4.1: Spec the template + generator**

```
Skill("rabbit-feature-spec", args: "rabbit-meta Refine Inv 3 + add Inv 6: templates/README.md.template MUST exist with the killer-story prose + 3-line 'what to do next' + link to upstream docs (verbatim from design v0.2.0 — the killer story is the contract with the user). lib/generate_readme.py exports generate_readme(template_path, output_path) verbatim-write, idempotent. Test coverage: t1-t3 mirror Task 3.3 tests.")
```

- [ ] **Step 3.4.2: Dispatch rabbit-feature-touch**

```
Skill("rabbit-feature-touch", args: "rabbit-meta Implement README.md template + generator per spec")
```

- [ ] **Step 3.4.3: Verify**

Run: `python3 .claude/features/rabbit-meta/test/run.py` → exit 0
Manual: generate into tmp, inspect content.

---

# PHASE 4 — Install ritual

Documentation + optional bootstrap script. Can run in parallel with Phase 3.

## Task 4.1: docs/install.md

**Files:**
- Create: `docs/install.md` (root docs — outside any feature; requires one-shot scope override)

**Content (full text — the actual file the engineer writes):**

```markdown
# Installing Rabbit into a Project

Rabbit is installed as a per-project plugin at `<your-project>/.rabbit/`. The install is pure vendoring — `.rabbit/` is fully committed to your project's repo, no submodules, no embedded `.git` inside it.

## Bootstrap (one-time, per project)

From your project root:

```bash
cd <your-project>/
git clone https://github.com/changyu87/rabbit-workflow.git .rabbit/
rm -rf .rabbit/.git
git add .rabbit/
git commit -m "install rabbit"
```

That's it. `.rabbit/` is now a vendored part of your repo, version-pinned by the commit you just made.

## Start a rabbit session

```bash
cd .rabbit/ && claude
```

This enters **plugin mode**: Claude reads the policy block from `.rabbit/CLAUDE.md` on session start, scope-guard protects the rabbit runtime, and you can edit any file in your project at `../`.

When you launch `claude` from anywhere else in your project (or anywhere outside a rabbit install), you get **plain Claude Code** — no policy block, no scope-guard.

## Day-1 value: drift-protected Claude (no setup)

Right away, every Claude action obeys philosophy/coding-rules/spec-rules — no speculative refactors, no orphan files, no documentation you didn't ask for. Just normal Claude, but with constitution. No commands to learn.

## Day-N value: promote a code slice to a feature (opt-in)

When you want spec-as-memory for part of your codebase:

```bash
rabbit-feature-new auth ../src/auth/**
```

Rabbit validates the glob, scaffolds bookkeeping at `.rabbit/rabbit-project/features/auth/`, runs a read-only seeder agent that drafts `spec.md` from your existing auth code, and registers the mapping in `project-map.json`. From then on, scope-guard blocks unsanctioned edits to `../src/auth/**` and Claude reads `auth/spec.md` for context every session.

When you want to make a quick edit to a declared feature without ceremony, you can do a one-shot bypass:

```bash
touch .rabbit/.runtime/scope-bypass-once
```

Then issue your edit. The marker is consumed (deleted) on the next edit, so this is a single-use override. Use sparingly — the bypass exists for quick fixes, not for routine work.

## Sharing across collaborators

Because `.rabbit/` is fully committed, `git clone <your-project>` gives a complete, version-pinned, rabbit-enabled checkout to every collaborator. No per-developer bootstrap. The rabbit version IS the file content in `.rabbit/`; no version skew.

## Updating rabbit

(See `/rabbit-update` — coming in a later cycle. For now, manual update: `cd .rabbit && git pull https://github.com/changyu87/rabbit-workflow.git main && rm -rf .git && cd .. && git add .rabbit && git commit -m 'chore(rabbit): update'`.)
```

- [ ] **Step 4.1.1: One-shot scope override + write file**

```bash
echo -n "one-time" > .rabbit-scope-override
```

Then write the file via the Write tool to `docs/install.md` with the content above.

- [ ] **Step 4.1.2: Verify override consumed**

```bash
ls -la .rabbit-scope-override  # should report missing
```

- [ ] **Step 4.1.3: Commit**

```bash
git add docs/install.md
git commit -m "docs: add user-interfacer install ritual (CONTRACT-BACKLOG-17)"
```

---

## Task 4.2: Bootstrap one-liner / bootstrap.sh

**Files:**
- Create: `.claude/features/rabbit-meta/scripts/bootstrap.sh` (optional — could be just a documented one-liner in install.md)
- Modify: `.claude/features/rabbit-meta/docs/spec/spec.md` (Inv 4 refinement)
- Create: `.claude/features/rabbit-meta/test/test-bootstrap.py`

**Approach:** Decide during impl: bootstrap.sh OR documented one-liner. The design v0.2.0 leaves this open ("one-line shell command, or rabbit ships a bootstrap.sh?"). Recommendation: **just document the 4-line snippet in install.md** (Task 4.1) and skip a separate bootstrap.sh. Reasons: the snippet is short and clear; a script adds another artifact whose deprecation/versioning would need tracking; the install ritual itself is the contract, not the script.

If decision is "ship bootstrap.sh", it would be:

```bash
#!/usr/bin/env bash
set -euo pipefail
RABBIT_UPSTREAM="${RABBIT_UPSTREAM:-https://github.com/changyu87/rabbit-workflow.git}"
if [ -d .rabbit ]; then
  echo ".rabbit/ already exists. Aborting." >&2
  exit 1
fi
git clone "$RABBIT_UPSTREAM" .rabbit/
rm -rf .rabbit/.git
git add .rabbit/
git commit -m "install rabbit"
echo "Rabbit installed. Run: cd .rabbit/ && claude"
```

- [ ] **Step 4.2.1: Decision gate**

Surface to user: "Ship `bootstrap.sh` or keep one-liner only in install.md?" Default: one-liner only (skip Task 4.2 implementation).

- [ ] **Step 4.2.2 (only if shipping bootstrap.sh): Spec + dispatch**

```
Skill("rabbit-feature-spec", args: "rabbit-meta Refine Inv 4: scripts/bootstrap.sh exists, executable, idempotent (refuses if .rabbit/ exists), exits 1 on error, takes RABBIT_UPSTREAM env var with default upstream URL. test/test-bootstrap.py covers the happy path + abort-on-existing-dir.")

Skill("rabbit-feature-touch", args: "rabbit-meta Implement bootstrap.sh per Inv 4")
```

- [ ] **Step 4.2.3: Verify**

Run: `python3 .claude/features/rabbit-meta/test/run.py` → exit 0
Manual e2e: run bootstrap.sh in a tmp dir, confirm install + verify clean output.

---

# Self-review

## Spec coverage

Mapping the design's 10 deliverables to plan tasks:

| Deliverable | Plan task(s) |
|---|---|
| 1. Bootstrap docs (`docs/install.md`) | 4.1 |
| 2. `.rabbit/README.md` auto-generated | 3.4 |
| 3. `.rabbit/CLAUDE.md` for plugin mode | 3.3 |
| 4. Mode detection (SessionStart hook) | 2.1 (+ 1.3 for the lib it calls) |
| 5. `rabbit-feature-new` enhancement | 3.2 |
| 6. Spec-seeding subagent | 3.1 |
| 7. `project-map.json` schema | 1.2 |
| 8. Scope-guard plugin-mode logic | 2.2 (+ 2.3 for bypass-once) |
| 9. Meta-contract (new feature) | 1.1 (scaffold) + the cumulative spec across rabbit-meta tasks 1.3 / 3.3 / 3.4 / 4.2 |
| 10. Tests | distributed across all tasks (every task lists its own test file) |

All 10 covered. ✓

## Placeholder scan

Searched for "TBD", "TODO", "fill in", "implement later", "similar to". One acceptable use of "TBD" is in the README template (referring to the future `/rabbit-update` skill which is explicitly out of scope for this cycle). That's a reference to a known future deliverable, not a plan placeholder.

## Type/name consistency

- `detect_mode(cwd)` used consistently in tasks 1.3, 2.1
- `project-map.json` and the schema file basename consistent across 1.2, 2.2, 3.2
- `.rabbit/.runtime/mode`, `.rabbit/.runtime/scope-active-<name>`, `.rabbit/.runtime/scope-bypass-once` paths consistent
- `write_mode_marker` runtime API consistent in 2.1 (both contract addition + rabbit-cage wiring)
- `rabbit-meta` feature name consistent across 1.1, 1.3, 3.3, 3.4, 4.2
- `spec-seeder` feature name consistent across 3.1 (and the slot names `feature_name`, `paths_globs`, `paths_resolved` reused in 3.2's spec-seeder invocation)

## Scope check

Plan covers one development cycle (user-interfacer) with 4 phases. Each phase is internally coherent. Phases 1-2 are foundation; Phases 3-4 are surfaces + install. Could be sub-divided per phase if the cycle stretches over multiple sessions, but as a single plan it's tractable.

---

# Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-rabbit-user-interfacer.md`. Two execution options:**

**1. Subagent-Driven (recommended for this plan)** — Dispatch a fresh `tdd-subagent` per task (each task = one or more `rabbit-feature-touch` cycles, each cycle already runs its own TDD subagent). Main session reviews HANDOFFs between tasks. Fast iteration; matches the rabbit workflow's existing dispatcher pattern. The plan's task structure already mirrors `rabbit-feature-touch` invocations.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints. Heavier on main-session context; better if the user wants tight per-task review.

**Recommendation: Subagent-Driven, sequential by phase.** Phases 1 and 2 are tightly serial (each task depends on the previous). Phase 3 has parallelization opportunities (3.3 and 3.4 can dispatch in parallel after 3.1+3.2). Phase 4 can run in parallel with any of 3.3/3.4.

**Suggested kickoff sequence:**
1. Start with Task 1.1 (scaffold rabbit-meta) — single dispatcher session, 2 cycles (rabbit-meta scaffold + contract workspace-structure update)
2. Then Task 1.2 (project-map.json schema, contract)
3. Then Task 1.3 (mode-detection lib, rabbit-meta)
4. Phase 2 in order: 2.1 → 2.2 → 2.3
5. Phase 3: 3.1 first, then 3.2; 3.3 + 3.4 in parallel after; Phase 4 also in parallel
6. Final integration: smoke test on a real user project (greenfield + brownfield) before declaring the cycle done

**Which approach?** (Or: pause here, review the plan, come back to dispatch when ready.)
