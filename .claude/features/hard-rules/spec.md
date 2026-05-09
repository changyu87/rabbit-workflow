# hard-rules

> Source of truth: [`feature.json`](./feature.json).

## Purpose

A staging area for rules that are too specific or too operational to live in
`philosophy.md` (which is principle-level) or `work-guide.md` (which is
construction discipline). Each rule here either:

1. Is a deterministic check shipped as a script under `scripts/`, with tests; OR
2. Is documented policy that complements other features' enforcement.

When a rule matures or proves load-bearing across many features, it can be
promoted into `work-guide.md` directly. Until then, hard-rules is the seam.

## Rules

### R1 — Branch per feature; never work on main

Source: `my_request.txt` rule #24.

**Statement:** Every feature mutation (creation, update, deletion of files
under `.claude/features/<name>/`) MUST be authored on a new branch and
proposed via a PR. Direct commits to `main` (or `master`, `trunk`,
`develop`) are forbidden.

**Enforcement:** `scripts/check-no-main-edits.sh`. Run as a pre-commit
guard. Rejects with non-zero exit if the current branch is `main`/`master`/
`trunk`/`develop`.

**Rationale:** Per Bounded Scope, every change is reviewable in isolation.
Direct main commits skip the review boundary.

---

### R2 — Opus-with-max-effort for brainstorming / spec / planning subagents

Source: `my_request.txt` rule #23.

**Statement:** Any subagent whose `description:` mentions brainstorming,
spec-writing, planning, design, or architecture work MUST declare
`model: opus` in its frontmatter. Lesser models risk shallow analysis on
load-bearing decisions.

**Enforcement:** `scripts/check-opus-for-planning-agents.sh`. Scans
`.claude/agents/*.md`, matches the description against
`brainstorm|spec|plan|design|architect`, and fails if matched agents do
not declare `model: opus`.

**Effort level:** "max effort" is a session-level Claude Code setting
(`effortLevel: "high"` or `xhigh` in settings) and cannot be enforced at
the agent-definition level. Document for spawners: "When dispatching a
planning-class subagent, also set the session effort level to `xhigh` if
not already."

---

### R3 — Tests are end-to-end, no human intervention

Source: `my_request.txt` rule #22.

**Statement:** Every test under any feature's `test/` directory MUST run to
completion without human input. Forbidden constructs: bare `read`, `select`
menus, `dialog`-style UIs, anything that blocks waiting for input.

**Enforcement:** `scripts/check-tests-non-interactive.sh <feature-dir>`.
Scans `test/*.sh`, ignoring comment-only lines, and fails if any forbidden
construct is found.

**False-positive guard:** Lines starting with `#` (comments) are stripped
before scanning. So `# we used to call 'read' here` is allowed.

---

### R4 — TDD step transitions go through `tdd-step.sh`; no manual `feature.json` edits to `tdd_state`

Source: `my_request.txt` rules #3, #19.

**Statement:** Every transition of `feature.json:tdd_state` MUST be
performed via `tdd-step.sh transition <feature-dir> <new-state>`. Manual
edits bypass the forward-only gate and the drift check.

**Enforcement:** Documented policy. The `breeder` subagent's system prompt
encodes this; PR review enforces it. (A git-log scanner could detect
unauthorized direct edits, but adds little value over PR review.)

---

### R5 — Non-rabbit features follow the same pattern under a user-specified root

Source: `my_request.txt` rule #11.

**Statement:** When the same workflow is applied to a user's own project
(e.g. `projA/features/<name>/`), the schema and the scripts work without
modification. Validators, TDD scripts, and bug-filing scripts all accept
arbitrary directory paths and honor `$BUG_ROOT`. Spawned subagents working
on a user feature should be scoped (in their prompt) to that feature's
folder.

**Enforcement:** None at file level. The schema is intentionally portable;
the rule is documentation.

---

## Scripts

### `scripts/check-no-main-edits.sh`

```
check-no-main-edits.sh
```

No args. Reads current branch via `git rev-parse --abbrev-ref HEAD`.
Exit 0 if not on main/master/trunk/develop; 1 if on one of those; 2 if not
in a git repo.

### `scripts/check-opus-for-planning-agents.sh`

```
check-opus-for-planning-agents.sh
```

Scans `$AGENTS_DIR` (default `.claude/agents/`). Exit 0 if all agents whose
description matches the planning regex declare `model: opus`; exit 1 with
violations listed on stderr otherwise.

### `scripts/check-tests-non-interactive.sh`

```
check-tests-non-interactive.sh <feature-dir>
```

Scans `<feature-dir>/test/*.sh` for forbidden interactive constructs. Exit
0 if none found; 1 with violations on stderr otherwise.

## Tests

`test/run.sh` runs three test files, 17 cases total:

- `test-no-main-edits.sh` (4) — fixture git repos to verify branch
  detection, including main, master, feature branch, outside-repo.
- `test-opus-for-planning.sh` (7) — fixture agent files with various
  description / model combinations.
- `test-tests-non-interactive.sh` (6) — fixture test files with various
  shell constructs, including comment-only false-positive guard.

## What this feature does NOT define

- TDD state machine itself — that is `tdd-state-machine`.
- Feature schema — that is `feature-skeleton`.
- Bug filing schema — that is `bug-filing`.
- The breeder discipline that wraps writes — that is `breeder`.

Bounded scope: this feature owns the rule **set** and its **enforcement
checks**, not the underlying schemas they enforce against.
