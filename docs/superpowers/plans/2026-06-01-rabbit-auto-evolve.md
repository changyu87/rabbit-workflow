# rabbit-auto-evolve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new rabbit feature `rabbit-auto-evolve` that converts the rabbit workflow into a self-driving loop (triage open issues, dispatch TDD subagents, merge to dev, tag releases, reschedule via ScheduleWakeup until the user stops it).

**Architecture:** A standard rabbit feature directory (`.claude/features/rabbit-auto-evolve/`) declares one CONFIGURATION entry (`/rabbit-config auto-evolve on|off`), one SKILL.md (`rabbit-auto-evolve` with `start`/`stop`/`status`/`tick` subcommands), and a handful of deterministic Python scripts that the SKILL.md walks the dispatcher (Claude/LLM) through. The loop's per-tick state is persisted on disk in `.rabbit/auto-evolve-state.json` so a Claude restart never nukes progress. Activation flips two existing `rabbit-cage` configurables (`human-approval=false`, `bypass-permissions=true`) as a compound mutation and writes its own marker; the SessionStart banner is then customized to replace the two underlying alerts with a single composite "AUTONOMOUS-EVOLVE MODE ACTIVE" message. The feature itself is built **via the rabbit-feature-touch TDD cycle** — each component below is delivered through one `/rabbit-feature-touch <issue#>` dispatch.

**Tech Stack:** Python 3 stdlib only. `gh` CLI for GitHub Issues and PRs. Existing rabbit infrastructure (`rabbit-feature-touch`, `rabbit-feature-scaffold`, `rabbit-spec-create`, `rabbit-issue`, `contract.lib.mutation`, `contract.lib.runtime`). `ScheduleWakeup` tool for self-paced wake-ups.

**Spec:** `docs/superpowers/specs/2026-06-01-rabbit-auto-evolve-design.md` (committed in `3ccf82a`).

---

## File Structure

All paths below are repo-relative.

### Inside the new feature (created by this plan)

```
.claude/features/rabbit-auto-evolve/
├── feature.json                    # manifest, runtime, configuration, prompts
├── CHANGELOG.md                    # version history
├── docs/spec/spec.md               # invariants (frontmatter: feature, version, owner, deprecation_criterion)
├── docs/spec/contract.md           # provides/reads/invokes/never
├── skills/rabbit-auto-evolve/SKILL.md
├── scripts/
│   ├── set-evolve-mode.py          # compound mutator on|off
│   ├── fetch-queue.py              # list open rabbit-managed issues → JSON
│   ├── triage-issue.py             # per-issue classifier → JSON
│   ├── plan-batch.py               # conflict graph + barrier → JSON
│   ├── safety-check.py             # never-touch-main + 5 bottom-line invariants
│   ├── merge-prs.py                # gh pr merge --squash --auto into dev
│   ├── release-bump.py             # priority → semver bump → tag + release
│   ├── cleanup-branches.py         # delete merged feat/* work branches (local + origin)
│   ├── classify-merge-restart.py   # no-op | refresh | restart-needed
│   ├── update-state.py             # write .rabbit/auto-evolve-state.json
│   └── schemas/
│       └── auto-evolve-state.schema.json
└── test/
    ├── run.py                      # walks every test-*.py
    ├── test-set-evolve-mode.py
    ├── test-banner-suppression.py
    ├── test-triage-rules.py
    ├── test-plan-batch.py
    ├── test-release-bump.py
    ├── test-safety-check.py
    ├── test-classify-merge-restart.py
    ├── test-tick-skill.py
    ├── test-start-stop-skill.py
    ├── test-state-persistence.py
    ├── test-discovered-issues.py
    ├── test-prompts-declared.py
    └── test-feature-shape.py
```

### Touched outside the new feature (must already be merged before this plan starts)

- `.claude/features/contract/lib/runtime.py` — adds `emit_auto_evolve_banner` and `emit_auto_evolve_stop_line`; modifies `iterate_configurables_alerts` and `iterate_configurables_banner` to mute the two underlying alerts when `.rabbit-auto-evolve-active` is present. **Owner: contract feature. Prerequisite issue PR-3 in Phase A.**
- `.claude/features/tdd-subagent/...` — TDD abort/quit mechanism + HANDOFF schema extension (`discovered_issues`, `aborted_reason`). **Owner: tdd-subagent feature. Prerequisite issues PR-1 and PR-2 in Phase A.**

### Touched outside the feature by this plan (allowlisted edits)

- `.claude/features/contract/workspace-structure.json` — declare `rabbit-auto-evolve` as a required feature (per rabbit-config Inv 18 pattern). One small edit in Task 12.

---

## Execution Discipline

Every component task below (Tasks 3–14) is implemented via **one `/rabbit-feature-touch <issue#>` dispatch**. The dispatcher's per-task actions are:

1. File an issue via `Skill("rabbit-issue", "<file args>")` with labels `feature:rabbit-auto-evolve`, `priority:medium` (unless noted), `rabbit-managed`.
2. Invoke `Skill("rabbit-feature-touch", "<issue#>")` — the standard 7-step cycle runs: scope → branch → spec → approval → TDD subagent → HANDOFF verify → PR.
3. Verify the PR is opened against `dev`, CI is green, then merge with `gh pr merge --squash --auto`.
4. Delete the local + origin work branch.
5. **Commit checkpoint:** the merged PR is the commit. No separate dispatcher-level commit per step.

The TDD subagent inside each cycle does the actual test-red → impl → test-green dance. The plan task body specifies **what** the subagent must produce (test code, script code, spec invariants); the subagent decides **how** within its sandbox.

Spec invariants accumulate. After all component tasks merge, the feature's `docs/spec/spec.md` carries the union of all invariants and the version reflects the latest bump.

---

## Phase A — Prerequisite Issues (file now, work first)

These three issues must be filed at the start of this plan and worked through their own `/rabbit-feature-touch` cycles before Phase B begins. The plan's component tasks (Phase C+) depend on the merged state of all three.

### Task 1: File and complete prerequisite issues

**Files:** none in this repo (the work lands in `tdd-subagent` and `contract` features).

- [ ] **Step 1: File PR-1 (TDD abort/quit mechanism)**

```
Skill("rabbit-issue", args: "file bug
title: tdd-subagent: add abort/quit mechanism mid-cycle
labels: feature:tdd-subagent, priority:high, rabbit-managed
body: |
  The TDD state machine currently assumes every cycle reaches test-green
  (test-red → impl → test-green). There is no abort path for the case
  where the subagent discovers, mid-cycle, that the work is blocked by
  another issue or that a discovery requires filing a new issue before
  proceeding.

  rabbit-auto-evolve (see docs/superpowers/specs/2026-06-01-rabbit-auto-evolve-design.md)
  depends on this: when its loop dispatches a TDD cycle and the subagent
  hits a blocker, the subagent must be able to:
  1. Emit a HANDOFF with aborted_reason and discovered_issues fields
     (see PR-2)
  2. Release any scope locks (.rabbit-scope-active-<feature>)
  3. Roll back the tdd_state to test-red (or whatever was the pre-touch
     state)
  4. Exit cleanly so the dispatcher sees the HANDOFF and can react

  Acceptance: tdd-subagent's docs/spec/spec.md gains invariants
  documenting the abort path; tdd-step.py supports an `abort` transition;
  a test demonstrates a mid-cycle abort releases locks and rolls back
  state.
")
```

Expected: GitHub issue created with a numeric ID. Record the ID.

- [ ] **Step 2: File PR-2 (HANDOFF schema extension)**

```
Skill("rabbit-issue", args: "file enhancement
title: tdd-subagent: extend HANDOFF schema with discovered_issues and aborted_reason
labels: feature:tdd-subagent, priority:high, rabbit-managed
body: |
  rabbit-auto-evolve needs the TDD subagent's HANDOFF JSON to carry two
  optional fields:

    discovered_issues: [{title: string, body: string, labels: [string]}]
    aborted_reason: string | null

  These are populated when the subagent (a) discovers a follow-up issue
  worth filing during its cycle, or (b) aborts mid-cycle because of a
  blocker (paired with PR-1's abort mechanism).

  Both fields must be optional/nullable so existing TDD cycles that don't
  populate them remain valid.

  The contract.md for tdd-subagent must declare both fields under
  provides.handoff and the HANDOFF schema version must bump.
")
```

Expected: issue ID recorded.

- [ ] **Step 3: File PR-3 (contract.lib.runtime banner-suppression hook)**

```
Skill("rabbit-issue", args: "file enhancement
title: contract.lib.runtime: emit_auto_evolve_banner + suppression rule
labels: feature:contract, priority:high, rabbit-managed
body: |
  rabbit-auto-evolve needs three additive changes in contract.lib.runtime:

  1. iterate_configurables_alerts and iterate_configurables_banner must
     skip emitting per-configurable lines for `human-approval=false` and
     `bypass-permissions=true` when the marker `.rabbit-auto-evolve-active`
     is present at <repo_root>. Suppression must be opt-in (driven by the
     marker), not a refactor of the existing iteration logic.

  2. New runtime API `emit_auto_evolve_banner(repo_root)`: emits two
     `rabbit_subline` lines on SessionStart matching the spec
     Section 8 prose (active line + start/restart/aborted line per marker
     state).

  3. New runtime API `emit_auto_evolve_stop_line(repo_root)`: emits at
     most one `rabbit_subline` on Stop describing the loop's current
     state (running, stop-requested, restart-needed, aborted).

  The actual SessionStart/Stop registration of these APIs lives in
  rabbit-auto-evolve's feature.json runtime block (not here). This issue
  just adds the callable APIs and the suppression hook.

  Tests in contract/test/ must lock the new APIs' emission shape and the
  suppression behavior when the marker is present vs absent.
")
```

Expected: issue ID recorded.

- [ ] **Step 4: Work each prerequisite via standard feature-touch**

For each of PR-1, PR-2, PR-3 in order (PR-1 → PR-2 → PR-3; PR-1 blocks PR-2, PR-2 and PR-1 unblock PR-3):

```
Skill("rabbit-feature-touch", args: "<issue-id>")
```

Wait for the HANDOFF, verify the PR opens and CI is green, then `gh pr merge --squash --auto`.

- [ ] **Step 5: Verify all three prerequisites are merged**

Run:

```bash
git fetch origin dev
git log --oneline origin/dev -n 20 | grep -E "tdd-subagent|contract" | head -10
```

Expected: at least three merge commits visible matching the prerequisite issue numbers.

Manually verify on disk:

```bash
test -f .claude/features/tdd-subagent/scripts/tdd-step.py && \
  grep -q "abort" .claude/features/tdd-subagent/scripts/tdd-step.py && \
  echo "PR-1 OK"

grep -q "discovered_issues" .claude/features/tdd-subagent/docs/spec/contract.md && \
  echo "PR-2 OK"

grep -q "emit_auto_evolve_banner" .claude/features/contract/lib/runtime.py && \
  echo "PR-3 OK"
```

Expected: three "OK" lines printed. If any fails, do not proceed to Phase B.

---

## Phase B — Scaffold the feature

### Task 2: Scaffold `rabbit-auto-evolve`

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/feature.json` (via scaffold)
- Create: `.claude/features/rabbit-auto-evolve/docs/spec/spec.md` (via scaffold)
- Create: `.claude/features/rabbit-auto-evolve/docs/spec/contract.md` (via scaffold)
- Create: `.claude/features/rabbit-auto-evolve/test/run.py` (via scaffold)

- [ ] **Step 1: Scaffold via `rabbit-feature-scaffold` skill**

This invocation runs in standalone mode (no path-globs), creating the standard rabbit feature skeleton:

```
Skill("rabbit-feature-scaffold", args: "rabbit-auto-evolve")
```

Expected: directory created with `feature.json`, `docs/spec/spec.md`, `docs/spec/contract.md`, `test/run.py`. The scaffolded `feature.json` declares `name: rabbit-auto-evolve`, `version: 0.1.0`, `template_version`, `owner` (from `$USER` or git config), `deprecation_criterion`, empty `manifest`, empty `runtime`, empty `configuration`, empty `prompts`, empty `surface`.

- [ ] **Step 2: Validate the scaffold immediately**

```bash
python3 .claude/features/contract/scripts/validate-feature.py .claude/features/rabbit-auto-evolve
```

Expected: exit 0, "validation passed" or equivalent.

- [ ] **Step 3: Author the seed spec via `rabbit-spec-create`**

```
Skill("rabbit-spec-create", args: "rabbit-auto-evolve")
```

Expected: `docs/spec/spec.md` populated with the six-section seed (Purpose, Paths governed, Public surface, Current behaviour, Known gaps, Open questions). This is just the seed — invariants are added per component task below.

- [ ] **Step 4: Commit the scaffold + seed spec**

```bash
git checkout -b feat/rabbit-auto-evolve-scaffold
git add .claude/features/rabbit-auto-evolve/
git commit -m "feat(rabbit-auto-evolve): scaffold + seed spec"
git push -u origin feat/rabbit-auto-evolve-scaffold
gh pr create --base dev --title "feat(rabbit-auto-evolve): scaffold + seed spec" --body "Initial scaffold + spec seed for the rabbit-auto-evolve feature. Follow-up PRs implement components per docs/superpowers/plans/2026-06-01-rabbit-auto-evolve.md."
```

Then `gh pr merge --squash --auto` once CI is green. Delete the work branch.

---

## Phase C — Build components (one feature-touch cycle each)

Each task in this phase: file an issue, invoke `rabbit-feature-touch <issue#>`, verify merge. The subagent inside the cycle writes the test, writes the script, updates the spec to add the named invariant, and ensures `test/run.py` green.

### Task 3: `set-evolve-mode.py` — compound mutator (on/off)

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/set-evolve-mode.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-set-evolve-mode.py`
- Modify: `.claude/features/rabbit-auto-evolve/docs/spec/spec.md` (add Inv: compound activation)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: set-evolve-mode.py compound mutator
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/set-evolve-mode.py as a CLI:

    set-evolve-mode.py on   # flips human-approval=false, bypass-permissions=true, writes .rabbit-auto-evolve-active
    set-evolve-mode.py off  # reverses, in inverse order

  Both forms perform deterministic mutations in order, aborting on first
  error and rolling back any prior step (best-effort: write/delete marker
  + flip json-key back).

  Script imports contract.lib.mutation and calls the same APIs that
  rabbit-config's dispatcher would call for the underlying configurables
  (delete_marker / write_marker, set_json_key / delete_json_key).

  Exit codes: 0 on full success, non-zero on any step failure (with
  rollback attempted and reported on stderr).

  Add Inv: 'set-evolve-mode.py on performs the three mutations in order
  (human-approval, bypass-permissions, marker) and rolls back on any
  failure; off reverses in inverse order'.

  Test (test-set-evolve-mode.py) uses tempfile.TemporaryDirectory(),
  simulates failure by monkey-patching contract.lib.mutation, and asserts
  the rollback restores the prior state.
")
```

- [ ] **Step 2: Dispatch the feature-touch cycle**

```
Skill("rabbit-feature-touch", args: "<issue#>")
```

- [ ] **Step 3: Verify and merge**

Wait for HANDOFF, then:

```bash
gh pr view <pr#>   # confirm base=dev
gh pr merge <pr#> --squash --auto
```

Once merged: `git push origin --delete feat/rabbit-auto-evolve-<keywords>; git branch -D feat/rabbit-auto-evolve-<keywords>`.

### Task 4: `fetch-queue.py` — list open rabbit-managed issues

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/fetch-queue.py`
- Modify: `.claude/features/rabbit-auto-evolve/docs/spec/spec.md` (add Inv: queue-fetch contract)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: fetch-queue.py
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/fetch-queue.py as a CLI that prints JSON to stdout:

    fetch-queue.py

  Calls `gh issue list --repo <RABBIT_ISSUE_REPO or default> --state open
  --label rabbit-managed --json number,title,labels,body,createdAt` and
  emits the parsed JSON, sorted by priority label (critical > high >
  medium > low) then createdAt ascending.

  Issues missing a priority: label sort to the end.

  Use the same RABBIT_REPO_DEFAULT / RABBIT_ISSUE_REPO discovery as
  rabbit-issue's _gh.py — do NOT call `git remote get-url origin`. Import
  is allowed: `from rabbit_issue._gh import resolve_repo`.

  Add Inv: 'fetch-queue.py emits a deterministic JSON array sorted by
  priority then createdAt; only open issues with label rabbit-managed
  appear; the script never reads or writes anything other than the gh
  CLI output stream'.

  No test for this task beyond a smoke test that asserts the script
  --help exits 0 (network-dependent listing is covered by the integration
  smoke test in Phase H).
")
```

- [ ] **Step 2: Dispatch + verify + merge** (same pattern as Task 3 Steps 2–3).

### Task 5: `triage-issue.py` — per-issue classifier

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/triage-issue.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-triage-rules.py`
- Modify: spec.md (add Inv: triage decision table)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: triage-issue.py with deterministic decision table
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/triage-issue.py as a CLI:

    triage-issue.py <issue#>

  Reads issue body, labels, comments via gh, plus the named feature's
  docs/spec/spec.md head matter (front matter + first section only).
  NEVER reads the codebase at large.

  Emits JSON to stdout:
    {
      issue: int,
      decision: 'work' | 'close-not-planned' | 'defer',
      reason_code: string,
      rationale: string (one sentence),
      feature: string,
      contract_touch: bool,
      blocked_by: [int]
    }

  Decision rules (top-down, first match wins):
    1. Issue lacks feature:<name> or priority:<level> label
       → defer, reason_code=malformed-labels
    2. Feature named by label does not exist on disk
       → close-not-planned, reason_code=unknown-feature
    3. Issue title/body matches a closed issue in last 30 days
       (case-folded substring on title)
       → close-not-planned, reason_code=duplicate
    4. Feature has feature.json.status == 'retired'
       → close-not-planned, reason_code=feature-retired
    5. Issue body declares 'blocked-by: #N' AND any #N is still open
       → defer, reason_code=blocked, blocked_by=[N…]
    6. Feature's spec already documents the requested behavior verbatim
       (substring match on issue summary line)
       → close-not-planned, reason_code=already-spec'd
    7. Otherwise → work, reason_code=actionable

  contract_touch is true iff label == feature:contract OR body declares
  a path under .claude/features/contract/.

  Default for any ambiguous case is defer with reason_code=needs-judgment.

  Add Inv: 'triage-issue.py implements the seven-rule decision table
  in spec Section 5; rules evaluate top-down, first match wins; any
  ambiguity defaults to defer/needs-judgment (never silently to work)'.

  test-triage-rules.py covers each row of the table against a synthetic
  issue corpus (fixture JSON files under test/fixtures/triage/).
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 6: `plan-batch.py` — conflict graph + barrier

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/plan-batch.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-plan-batch.py`
- Modify: spec.md (add Inv: conflict graph + barrier)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: plan-batch.py conflict-graph coloring + contract barrier
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/plan-batch.py as a CLI that reads triage JSON from
  stdin and emits a dispatch plan to stdout:

    cat work-set.json | plan-batch.py [--max-parallel N]

  Input: array of triage JSON objects (only decision=='work' items).

  Output JSON:
    {
      barrier_first: [issue#…],
      groups: [[issue#…], …]
    }

  Algorithm:
    1. Partition: items with contract_touch=true → barrier_first list,
       sorted by priority desc then issue# asc.
    2. Remainder builds a conflict graph: nodes = issues; edge iff
       A.feature == B.feature.
    3. Greedy graph coloring on the remainder: sort by priority desc
       then issue# asc; walk and assign lowest color (group index) not
       used by a neighbor.
    4. Apply --max-parallel cap (default 4): if a group exceeds the cap,
       split into sub-groups of size ≤ cap (still parallel-safe within
       sub-group; sub-groups process sequentially).

  Output groups in color order.

  Add Inv: 'plan-batch.py implements the 4-step algorithm in spec
  Section 6; contract issues always land in barrier_first; same-feature
  issues never share a group; max_parallel cap is respected'.

  test-plan-batch.py covers: a contract-only set (everything to
  barrier_first), a same-feature set of 3 (3 separate groups), a
  mixed-feature set (single group), and an over-cap set (split into
  sub-groups).
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 7: `safety-check.py` — bottom-line invariants

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/safety-check.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-safety-check.py`
- Modify: spec.md (add Inv: bottom-line safety invariants)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: safety-check.py with five bottom-line invariants
labels: feature:rabbit-auto-evolve, priority:high, rabbit-managed
body: |
  Implement scripts/safety-check.py as a CLI:

    safety-check.py <pr#> [--phase merge|release|cleanup]

  Validates the five bottom-line invariants from spec Section 9 against
  the current git state and the named PR. Exits 0 on pass, 1 on
  violation (with violation details on stderr).

  Invariants:
    1. Current branch is 'dev'. Never 'main'.
    2. PR base branch (via `gh pr view <#> --json baseRefName`) is 'dev'.
    3. The work branch about to be deleted (head branch from gh) matches
       regex ^feat/.+ AND is not 'dev', 'main', or 'release/.*'.
    4. The tag about to be created (passed via env $RABBIT_AUTO_EVOLVE_NEXT_TAG
       when phase=release) does not already exist
       (`git rev-parse <tag>` fails).
    5. Working tree is clean (`git status --porcelain` empty).

  Add Inv: 'safety-check.py implements the five bottom-line invariants
  from spec Section 9; abort on any violation; never main, never a tag
  collision, always clean tree'.

  test-safety-check.py uses tempfile.TemporaryDirectory() + a fake git
  init to assert each invariant fails when violated and passes on valid
  state.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 8: `merge-prs.py` + `cleanup-branches.py`

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/merge-prs.py`
- Create: `.claude/features/rabbit-auto-evolve/scripts/cleanup-branches.py`
- Modify: spec.md (add Inv: merge target is dev, never main)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: merge-prs.py + cleanup-branches.py
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement two scripts:

  scripts/merge-prs.py: takes a comma-separated list of PR numbers,
  calls safety-check.py --phase merge for each, then
  `gh pr merge <#> --squash --auto`. Prints per-PR result JSON on
  stdout. Skips (does not error) when a PR's base is not dev.

  scripts/cleanup-branches.py: takes a comma-separated list of merged
  PR numbers, derives the head branch from each via
  `gh pr view <#> --json headRefName`, calls safety-check.py
  --phase cleanup, then deletes the branch locally
  (`git branch -D <branch>`) and on origin
  (`git push origin --delete <branch>`). Skips (with stderr warning) any
  branch that does not match ^feat/.+.

  Add Inv: 'merge-prs.py refuses to merge anything whose base is not
  dev; cleanup-branches.py refuses to delete anything not matching
  ^feat/.+'.

  No new test file (safety-check.py tests cover the invariants); a
  smoke test in test-tick-skill.py asserts the SKILL.md names both
  scripts in Phases 6 and 8.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 9: `release-bump.py` — priority → semver

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/release-bump.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-release-bump.py`
- Modify: spec.md (add Inv: bump table)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: release-bump.py with priority-derived semver
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/release-bump.py as a CLI:

    release-bump.py <pr#>

  Reads the merged PR's priority label and diff scope, computes the next
  semver per spec Section 9 table, then:
    1. git describe --tags --abbrev=0 → current top tag
    2. Compute next version
    3. git tag -a v<X.Y.Z> -m '<auto-evolve> #<issue> <title>'
    4. git push origin v<X.Y.Z>
    5. gh release create v<X.Y.Z> --notes-from-tag --target dev

  Calls safety-check.py --phase release before any git op.

  Bump table:
    low|medium → patch (Z+1)
    high|critical → minor (Y+1, Z=0)
    body contains 'bump:major' OR PR touches ≥ N features (default N=3)
      OR PR touches .claude/features/contract/schemas/* → major
      (X+1, Y=0, Z=0)

  --features-threshold N defaults to 3.

  Add Inv: 'release-bump.py applies the Section 9 table deterministically;
  the major-bump triggers are body directive OR feature-count threshold
  OR contract/schemas touch'.

  test-release-bump.py covers each row of the table against fixture PR
  metadata; gh and git calls are stubbed via the same shim pattern as
  rabbit-issue tests.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 10: `classify-merge-restart.py` — refresh ladder

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/classify-merge-restart.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-classify-merge-restart.py`
- Modify: spec.md (add Inv: three-rung refresh ladder)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: classify-merge-restart.py
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/classify-merge-restart.py as a CLI:

    classify-merge-restart.py <pr#>

  Reads the merged PR's file list via `gh pr view <#> --json files`,
  classifies into one of three rungs:

    no-op       — none of the patterns below match
    refresh     — touches .claude/features/policy/*.md OR CLAUDE.md
    restart     — touches settings.json OR adds a new skill
                  (.claude/skills/*/SKILL.md not previously present)
                  OR modifies a hook (.claude/hooks/*.py)

  Emits one of three literal strings on stdout: 'no-op', 'refresh',
  'restart'.

  Add Inv: 'classify-merge-restart.py implements the three-rung ladder
  in spec Section 7; rung is selected by the first matching pattern
  (restart > refresh > no-op)'.

  test-classify-merge-restart.py covers each rung against fixture PR
  file-list JSON.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 11: `update-state.py` + state schema

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/scripts/update-state.py`
- Create: `.claude/features/rabbit-auto-evolve/scripts/schemas/auto-evolve-state.schema.json`
- Create: `.claude/features/rabbit-auto-evolve/test/test-state-persistence.py`
- Modify: spec.md (add Inv: state schema + round-trip)

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: update-state.py + state schema
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Implement scripts/update-state.py and the JSON schema for
  .rabbit/auto-evolve-state.json.

  State JSON shape:
    {
      schema_version: '1.0.0',
      updated_at: ISO8601 UTC,
      queue: [{issue: int, decision: string, feature: string}],
      in_flight: [int],
      last_merged_sha: string|null,
      last_tagged_version: string|null,
      consecutive_failures: int,
      stop_requested: bool,
      restart_needed: bool|null  # reason string when set, else null
    }

  update-state.py reads --stdin-json, validates against the schema,
  writes atomically to .rabbit/auto-evolve-state.json (write to .tmp then
  rename). Refuses to write if the validation fails.

  Add Inv: 'update-state.py writes .rabbit/auto-evolve-state.json
  conforming to schemas/auto-evolve-state.schema.json; writes are atomic
  via temp+rename; round-trips through validate→write→read→validate'.

  test-state-persistence.py asserts round-trip equality and schema
  rejection on malformed input.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

---

## Phase D — SKILL.md and feature.json wiring

### Task 12: SKILL.md (start/stop/status/tick) + feature.json wiring

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/skills/rabbit-auto-evolve/SKILL.md`
- Create: `.claude/features/rabbit-auto-evolve/test/test-tick-skill.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-start-stop-skill.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-prompts-declared.py`
- Create: `.claude/features/rabbit-auto-evolve/test/test-discovered-issues.py`
- Modify: `.claude/features/rabbit-auto-evolve/feature.json` (manifest, configuration, prompts, runtime)
- Modify: `.claude/features/rabbit-auto-evolve/docs/spec/spec.md` (add Inv: SKILL.md shape, configuration entry, prompts entry)
- Modify: `.claude/features/contract/workspace-structure.json` (declare rabbit-auto-evolve as a required feature)

- [ ] **Step 1: File the issue (high priority — wires the whole feature together)**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: SKILL.md (start/stop/status/tick) + feature.json wiring
labels: feature:rabbit-auto-evolve, priority:high, rabbit-managed
body: |
  Author skills/rabbit-auto-evolve/SKILL.md per spec Section 3:
    - frontmatter declares model: opus
    - Subcommands: start, stop, status, tick
    - start: precondition check (marker present + human-approval off +
      bypass-permissions on), writes .rabbit-auto-evolve-running, runs
      one tick, ends with ScheduleWakeup chaining the next
    - stop: writes .rabbit-auto-evolve-stop-requested
    - status: read-only inspect (queue, in-flight, last-merged,
      last-tagged, consec failures, restart-marker)
    - tick: internal subcommand documenting the 12 phases (0–11) of
      spec Section 4 in order, naming every script and the disk-state
      path

  Update feature.json:
    1. manifest: one publish_skill entry for the SKILL.md
    2. configuration: one entry per spec Section 2 (subcommand
       'auto-evolve', values on/off via run_feature_script →
       set-evolve-mode.py, restart_required: true,
       alert-message describing the composite mode)
    3. prompts: one entry { id: 'rabbit-auto-evolve', kind: 'skill',
       inject: [philosophy, spec-rules, coding-rules], slots: ['args'] }
       plus matching passthrough template at
       .claude/features/contract/templates/prompts/rabbit-auto-evolve.txt
    4. runtime.SessionStart: one entry
       { api: 'emit_auto_evolve_banner', args: {} }
    5. runtime.Stop: one entry
       { api: 'emit_auto_evolve_stop_line', args: {} }
    6. surface.skills: ['rabbit-auto-evolve']

  Update .claude/features/contract/workspace-structure.json: declare
  rabbit-auto-evolve under features.children (per rabbit-config Inv 18
  pattern).

  Tests:
    test-tick-skill.py: SKILL.md documents all 12 phases (0–11) in
      order, names every script invoked, names the disk-state path,
      explains the ScheduleWakeup reschedule logic
    test-start-stop-skill.py: SKILL.md start refuses unless all three
      preconditions hold; stop writes the stop marker; status is
      read-only
    test-prompts-declared.py: feature.json declares the prompts entry
      with the documented inject list and slots
    test-discovered-issues.py: the SKILL.md describes the in-loop
      discovery handling (file via rabbit-issue, label blocked-by:#N on
      abort)

  Add Invs covering each of the above test points.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 13: Banner integration (SessionStart + Stop)

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/test/test-banner-suppression.py`
- Modify: spec.md (add Inv: banner shape + suppression contract)

This task adds the test that confirms PR-3's runtime hooks behave correctly when driven by rabbit-auto-evolve's feature.json runtime entries. The runtime APIs themselves landed in Phase A (PR-3); feature.json wired them in Task 12; this task locks the end-to-end behavior.

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: end-to-end banner suppression test
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Write test-banner-suppression.py to exercise the SessionStart and Stop
  dispatchers end-to-end against a synthetic .claude/features/ tree
  inside tempfile.TemporaryDirectory():

    Scenario 1: .rabbit-auto-evolve-active absent
      Expected: iterate_configurables_alerts emits two lines (one for
      human-approval=false, one for bypass-permissions=true);
      emit_auto_evolve_banner is a no-op.

    Scenario 2: .rabbit-auto-evolve-active present
      Expected: iterate_configurables_alerts emits ZERO lines for those
      two configurables; emit_auto_evolve_banner emits exactly two
      rabbit_subline lines (active + start command).

    Scenario 3: marker + .rabbit-auto-evolve-restart-needed
      Expected: line 2 of banner reads 'resume after restart: paste
      /rabbit-auto-evolve start'.

    Scenario 4: marker + .rabbit-auto-evolve-aborted
      Expected: line 2 of banner reads 'loop aborted on safety violation
      …'.

  Add Inv: 'When .rabbit-auto-evolve-active is present, the SessionStart
  and Stop dispatchers emit the auto-evolve composite banner instead of
  the per-configurable alerts for human-approval and bypass-permissions'.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

---

## Phase E — Feature-shape compliance + final integration

### Task 14: Feature-shape compliance + audit

**Files:**
- Create: `.claude/features/rabbit-auto-evolve/test/test-feature-shape.py`
- Modify: `.claude/features/rabbit-auto-evolve/CHANGELOG.md` (initial entry for 0.1.0)
- Modify: spec.md frontmatter version → 0.1.0 (matches feature.json)
- Modify: contract.md frontmatter version → 0.1.0

- [ ] **Step 1: File the issue**

```
Skill("rabbit-issue", args: "file enhancement
title: rabbit-auto-evolve: feature-shape + audit compliance
labels: feature:rabbit-auto-evolve, priority:medium, rabbit-managed
body: |
  Add test-feature-shape.py asserting:
    - feature.json.version == spec.md frontmatter version == contract.md
      frontmatter version
    - feature.json has non-empty owner and deprecation_criterion
    - SKILL.md frontmatter has non-empty version, owner,
      deprecation_criterion
    - feature.json.summary mentions the rabbit-auto-evolve skill
    - Every skill in feature.json.surface.skills has a matching entry
      in contract.md provides.skills

  Author CHANGELOG.md with the 0.1.0 entry summarizing components.

  Sync spec.md and contract.md frontmatter version fields to 0.1.0.

  Run `Skill('rabbit-feature-audit', 'rabbit-auto-evolve')` and resolve
  any reported issues.
")
```

- [ ] **Step 2: Dispatch + verify + merge.**

### Task 15: Full test suite green + final PR

- [ ] **Step 1: Run the feature's test suite**

```bash
cd .claude/features/rabbit-auto-evolve
python3 test/run.py
```

Expected: every `test-*.py` passes, summary line shows 13 tests passed (one per test file in the Files section above).

- [ ] **Step 2: Run the broader audit**

```
Skill("rabbit-feature-audit", "all")
```

Expected: rabbit-auto-evolve listed as PASS alongside every other feature.

- [ ] **Step 3: Verify deployment via the build pipeline**

```bash
python3 install.py
ls .claude/skills/rabbit-auto-evolve/SKILL.md
```

Expected: skill deployed.

---

## Phase F — Smoke test on a synthetic issue

### Task 16: End-to-end manual smoke test

This task is **not** auto-mergeable; it's a manual verification that the loop works on a real `gh` issue against the upstream rabbit-workflow repo.

- [ ] **Step 1: Enter the mode**

```
/rabbit-config auto-evolve on
```

Expected: three flags flipped, restart prompt emitted in yellow.

- [ ] **Step 2: Exit Claude and relaunch**

After relaunch, expected SessionStart banner: two rabbit_subline lines
- "AUTONOMOUS-EVOLVE MODE ACTIVE …"
- "to start the loop, paste: /rabbit-auto-evolve start"

The two underlying per-configurable alerts must NOT appear.

- [ ] **Step 3: File one synthetic test issue**

```
Skill("rabbit-issue", args: "file enhancement
title: smoke: rabbit-auto-evolve end-to-end test (safe-no-op)
labels: feature:rabbit-auto-evolve, priority:low, rabbit-managed
body: |
  Smoke test for rabbit-auto-evolve loop. Triage should classify this
  as work (or close-not-planned as 'duplicate' if a prior smoke is
  open). No real code change is expected.

  Acceptance: the loop observes this issue and either closes it as
  not-planned or dispatches a feature-touch that no-ops.
")
```

- [ ] **Step 4: Start the loop and observe one tick**

```
/rabbit-auto-evolve start
```

Expected log of phases 0–11. Then the wake-up is scheduled.

- [ ] **Step 5: Stop the loop**

```
/rabbit-auto-evolve stop
```

Expected: stop marker written, next tick (if it fires before stop) summarizes and exits.

- [ ] **Step 6: Exit the mode**

```
/rabbit-config auto-evolve off
```

Expected: three flags reverted, restart prompt emitted.

---

## Self-Review

After writing the full plan, I checked it against the spec:

**Spec coverage:**
- Section 1 Purpose → captured in Goal/Architecture header.
- Section 2 Activation → Task 3 (set-evolve-mode.py) + Task 12 (CONFIGURATION entry in feature.json).
- Section 3 Skill surface → Task 12.
- Section 4 One tick → Task 12 (SKILL.md documents all 12 phases) + Tasks 3–11 (each phase's underlying script).
- Section 5 Triage contract → Task 5.
- Section 6 Conflict graph → Task 6.
- Section 7 Live-update/catch-up → Task 10 (classify-merge-restart.py) + Task 11 (state persistence) + Task 12 (SKILL.md describes the ladder).
- Section 8 Banner customization → Phase A PR-3 (runtime APIs) + Task 12 (feature.json runtime entries) + Task 13 (end-to-end test).
- Section 9 Release/merge/safety → Task 7 (safety-check.py) + Task 8 (merge-prs.py, cleanup-branches.py) + Task 9 (release-bump.py).
- Section 10 Tests → tests are bundled into the task that creates the script under test (13 tests across Tasks 3, 5, 6, 7, 9, 10, 11, 12, 13, 14).
- Section 11 Prerequisites → Phase A Task 1 files them all and verifies merge.

**Placeholder scan:** searched for "TBD", "TODO", "implement later", "Similar to Task N", "Add appropriate error handling". None found in the plan body. The phrase "<keywords>" in branch names is a placeholder, but it's pre-filled by `rabbit-feature-touch` itself (the dispatcher reads the resolved name from the skill's output), not by the implementer.

**Type consistency:** state schema field names (`schema_version`, `updated_at`, `queue`, `in_flight`, `last_merged_sha`, `last_tagged_version`, `consecutive_failures`, `stop_requested`, `restart_needed`) used in Task 11 match Section 3 status output and Section 7 disk-state references in the spec. Triage JSON field names (`issue`, `decision`, `reason_code`, `rationale`, `feature`, `contract_touch`, `blocked_by`) used in Task 5 match Section 5 of the spec. Plan-batch JSON field names (`barrier_first`, `groups`) used in Task 6 match Section 6 of the spec.

**Gaps fixed inline:**
- Initially I had no plan for `.claude/features/contract/workspace-structure.json` registration; folded into Task 12.
- Initially Task 13 lacked a paired spec invariant; added the "When marker present, dispatchers emit composite banner" invariant.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-01-rabbit-auto-evolve.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
