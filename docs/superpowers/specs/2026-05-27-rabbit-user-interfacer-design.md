# Rabbit User-Interfacer — Design

**Status:** Draft
**Date:** 2026-05-27
**Owner:** rabbit-workflow team
**Version (of this design):** 0.2.0
**Supersedes:** `2026-05-18-rabbit-user-project-plugin-architecture-design.md` (0.1.0)
**Tracking item:** CONTRACT-BACKLOG-17

---

## Killer story (user-facing)

> *Install rabbit. `cd .rabbit/ && claude`. Your AI now reads policy on every
> action — no speculative refactors, no orphan files, no documentation you
> didn't ask for. When you want spec-as-memory for a slice of code, run
> `rabbit-feature-new auth src/auth/**` — and now that slice has durable
> intent that survives every session.*

This story is the contract with the user. The deliverables below exist to
make it true. The story itself ships in `.rabbit/README.md` (auto-generated
on bootstrap) and is the first thing a new user reads after install.

---

## Goal

Let a solo AI-augmented dev install rabbit into any of their projects and
immediately get **drift-protected Claude** — no setup, no ceremony.
Optionally, they can promote slices of their codebase to *rabbit features*
for spec-as-durable-memory and scope-guarded edits.

This design supersedes the 2026-05-18 architecture doc by re-scoping the
"user-interfacer" development cycle around a productivity-first wedge:
ship the universal value (drift protection) on day 1; let feature
discipline grow with user appetite; defer TDD and B/B-on-user-code to
later cycles.

---

## Why this scope (the rationale)

The 2026-05-18 design assumed users would adopt the full rabbit discipline
(spec → TDD → ship-it) as a single unit. Two observations during the
2026-05-27 brainstorm reframed this:

1. **TDD might not apply.** Users have their own test suites and
   conventions. Forcing `tdd-subagent` on user code is presumptuous.
2. **B/B duplicates existing tools.** Users already track work in GitHub
   Issues, Linear, etc. Re-inventing issue tracking is friction with no
   payoff.

What remains universal — across every solo AI-augmented dev regardless of
their existing toolchain — is the pain of **AI scope drift** and **context
loss between sessions**. Rabbit's policy block + spec system address both,
and they ship without forcing the user to change anything about their
testing or issue-tracking workflow.

The user-interfacer cycle delivers exactly that universal value, and
nothing more.

---

## Architectural choices inherited from 2026-05-18

These remain load-bearing and are not re-litigated here. See the predecessor
doc for full rationale:

- **Per-project plugin model.** `<user-project>/.rabbit/`; 1-1 binding; no
  central registry; no switch command; parallelism is OS-level (multiple
  terminals in different `.rabbit/` dirs).
- **Pure vendoring.** `.rabbit/` fully committed; no embedded `.git`;
  internal `.gitignore` for ephemerals.
- **Co-located bookkeeping.** `.rabbit/rabbit-project/` holds specs,
  feature registry, and project-map alongside the rabbit runtime in
  `.rabbit/.claude/`.
- **Two modes via filesystem detection.** `.rabbit/` in cwd ancestry →
  plugin mode; otherwise standalone (rabbit-self) mode.
- **Meta-contract owns the structure.** Project signature, required paths,
  commit policy, migration scripts.

What changes from 2026-05-18 is the *scope* of what the user-interfacer
cycle delivers — not these architectural foundations.

---

## The two-tier discipline model

### Tier 1 — Drift protection (default, zero setup)

The user runs:

```
cd <user-project>/.rabbit/
claude
```

This automatically:

1. **Mode detection.** A SessionStart hook walks ancestry of cwd. If the
   cwd basename is `.rabbit` AND its parent contains non-`.rabbit` content
   → **plugin mode**. The result is written to `.rabbit/.runtime/mode` for
   downstream tools.

2. **`.rabbit/CLAUDE.md` auto-loads the policy block.** Claude Code reads
   `CLAUDE.md` on session start. In plugin mode the file contains:
   - The killer story (3-line value reminder for the user)
   - `@.claude/features/policy/philosophy.md`
   - `@.claude/features/policy/spec-rules.md`
   - `@.claude/features/policy/coding-rules.md`
   - A note: *"You are operating on the user project at the parent
     directory. Edit files at `../`, not inside `.rabbit/`."*

3. **Scope-guard is configured for plugin mode.** It blocks:
   - Edits to `.rabbit/.claude/**` (rabbit runtime — vendored, untouchable
     except via the rabbit-update flow)
   - Edits to `.rabbit/rabbit-project/**` (bookkeeping — managed by rabbit
     skills)

   It allows:
   - Edits to anything in the user project (`../**`)
   - Edits to `.rabbit/CLAUDE.md` and `.rabbit/.gitignore`
     (user-customisable)

4. **No feature-scope enforcement yet.** Because no features are declared,
   per-feature scope-guard does not fire. The policy block is the entire
   discipline. It works on every Edit/Write because Claude reads CLAUDE.md
   before acting.

**What the user experiences:**

- Claude obeys philosophy/spec-rules/coding-rules on every interaction
  (no speculative features, no adjacent refactors, no unsolicited
  docs/emojis, read-before-edit).
- Claude knows where the rabbit runtime ends and user code begins.
- Zero new commands to learn. Just normal Claude chatting, with a
  constitution.

**Policy block delivery:** via CLAUDE.md alone (version-pinned through
vendoring). Belt-and-suspenders injection via SessionStart `additionalContext`
is rejected — if the user edits CLAUDE.md, they are explicitly opting out,
which is acceptable. Single source of truth beats redundancy.

### Tier 2 — Feature mode (opt-in, per feature)

When the user wants spec-as-memory for a slice of code, they run:

```
rabbit-feature-new <name> <path-glob> [<path-glob> ...]
```

Examples:

```
rabbit-feature-new auth        ../src/auth/**
rabbit-feature-new checkout    ../src/checkout/** ../src/billing/types.ts
rabbit-feature-new ui-shell    ../web/components/Layout/** ../web/app/layout.tsx
```

**Conceptual shift from rabbit-self:** A user feature is not a directory
you create — it is a **mapping from existing user code paths to a feature
identity**. The feature's bookkeeping (spec, contract, registry entry)
lives inside `.rabbit/rabbit-project/features/<name>/`. The code it governs
lives at `../src/...` (or wherever in the user tree).

**What `rabbit-feature-new` does (atomic operation):**

1. **Validate path globs.**
   - Each glob must resolve under the user-project root (parent of
     `.rabbit/`) — refuse globs outside the project boundary.
   - Each matched path must not already belong to another declared feature
     — refuse on overlap, name the conflicting feature.
   - At least one path must currently match — refuse empty mappings
     (prevents typos creating dead features).

2. **Scaffold bookkeeping** under
   `.rabbit/rabbit-project/features/<name>/`:
   - `feature.json` — `{name, version: "0.1.0", owner, paths: [<globs>],
     created, deprecation_criterion: null}`
   - `docs/spec/spec.md` — seeded by subagent (see below)
   - `docs/spec/contract.md` — minimal placeholder (see below)
   - No `test/run.py` in the user-interfacer cycle. TDD is deferred; if a
     later cycle introduces user-side TDD, this directory grows then.

3. **Register in `project-map.json`** at
   `.rabbit/rabbit-project/project-map.json`:

   ```json
   {
     "schema_version": "1.0.0",
     "features": {
       "auth": {
         "paths": ["../src/auth/**"],
         "feature_dir": "rabbit-project/features/auth"
       },
       "checkout": {
         "paths": ["../src/checkout/**", "../src/billing/types.ts"],
         "feature_dir": "rabbit-project/features/checkout"
       }
     }
   }
   ```

   Scope-guard reads this map to decide whether an edit lands in
   declared-feature territory.

4. **Seed `spec.md`** by dispatching a read-only default-model subagent
   that:
   - Reads (does not write) the matched files.
   - Emits sections: *Purpose* (one line), *Paths governed* (from
     project-map), *Public surface* (exported symbols / entry points),
     *Current behaviour* (bullet inventory), *Known gaps* (TODOs/FIXMEs/
     obvious smells), *Open questions* (for the user to resolve).
   - The user reviews and edits before adopting.

   Rationale: solo devs hate empty templates. A seeded draft from existing
   code is the difference between "I'll fill this in later" (never) and
   "let me fix these three things" (now).

**User-feature `spec.md` template (lighter than rabbit-self):**

```markdown
---
feature: <name>
version: 0.1.0
owner: <git user>
deprecation_criterion: null
---

# <name>

## Purpose
[seeded by subagent — one line of intent]

## Paths governed
[from project-map.json]

## Public surface
[seeded — exported APIs / entry points]

## Current behaviour
[seeded — bullet inventory]

## Open questions
[seeded — for user to resolve]
```

No `Hard Rules R1-R9`, no `Invariants 1-N` enumeration. Those are
rabbit-self conventions, justified by rabbit being a multi-feature system
with rigid cross-feature interfaces. A user's `auth/` feature usually does
not need that ceremony on day 1; it can be promoted later if real
interfaces emerge.

**`contract.md` placeholder:**

Ships with standard frontmatter and an empty contract block:

```json
{"schema_version": "1.0.0", "provides": [], "reads": [], "invokes": [], "never": []}
```

A short comment explains: *"This contract is intentionally empty. Populate
when this feature needs to expose APIs to, read from, or invoke other
features. Until then, the empty block satisfies the structural integrity
invariant."*

This keeps the auditor/tooling happy — every feature has a contract; the
invariant is checkable — without forcing the user to invent imaginary
cross-feature interfaces.

---

## Scope-guard behaviour in plugin mode

Once features are declared, scope-guard consults `project-map.json` on
every `Edit`/`Write`/`Bash` tool call.

**Decision tree:**

1. Target path under `.rabbit/.claude/**` or `.rabbit/rabbit-project/**`
   (with the carve-outs above) → block. Always.

2. Target path matches a declared feature's `paths` AND a scope marker
   exists for that feature (`.rabbit/.runtime/scope-active-<name>`) →
   allow. This is the normal `rabbit-feature-touch` path.

3. Target path matches a declared feature's `paths` AND no matching scope
   marker → **block, with structured error**:

   ```
   [rabbit] BLOCKED: edit to ../src/auth/login.ts lands in declared feature 'auth'.
   This edit needs scoped intent. Two options:
     (1) Proper path: invoke Skill("rabbit-feature-touch") with feature=auth
         — runs the full spec-aware flow (recommended for real work).
     (2) One-shot override: ask the user to run
           touch .rabbit/.runtime/scope-bypass-once
         — scope-guard will consume (delete) this marker on the next edit,
         allowing exactly one bypass.
   Ask the user which path they want before proceeding.
   ```

4. Target path does not match any declared feature → allow. (Undeclared
   code is, by definition, not under feature discipline.)

**One-shot override mechanism — `.rabbit/.runtime/scope-bypass-once`:**

- Created by the user with a single `touch` command. Explicit, auditable.
- Lives in `.runtime/` (gitignored — never travels in commits).
- Consumed (deleted) by scope-guard on the next Edit/Write, even if that
  edit fails (atomic consume-before-evaluate so a failed edit cannot leave
  a persistent bypass).
- **Cannot be set programmatically by Claude.** Only the human types
  `touch`. This preserves the "human approves the bypass" property without
  needing a slash-command ceremony.

Blocking (not warning) is the user-interfacer cycle default because it
forces a real decision: the user either commits to the heavier
feature-touch flow or explicitly grants a one-shot bypass. Warning-only
invites silent drift.

---

## User flows

### Bootstrap (one-time, per project)

```
cd <user-project>/
git clone <rabbit-upstream> .rabbit/
rm -rf .rabbit/.git                  # drop embedded git → pure vendoring
git add .rabbit/
git commit -m "install rabbit"
```

After this, `cd .rabbit && claude` starts a rabbit session bound to this
project.

On first session, rabbit detects empty bookkeeping and instantiates
greenfield templates:
- `.rabbit/rabbit-project/project-map.json` — `{"schema_version":
  "1.0.0", "features": {}}`
- `.rabbit/README.md` — generated from template; contains the killer
  story + 3-line "what to do next" + link to upstream docs.

### Daily use, no features declared

User runs `cd .rabbit && claude`, chats with Claude as usual. Drift
protection applies via the policy block. Nothing else changes.

### Promoting a slice to a feature

```
rabbit-feature-new auth ../src/auth/**
```

Rabbit validates, scaffolds, seeds spec, registers in project-map.
User reviews the seeded spec, commits.

### Scoped work on a declared feature

User asks Claude to change something in `../src/auth/`. Scope-guard
intercepts, prints the structured error, Claude relays the two options to
the user. User picks: feature-touch (full flow) or one-shot override
(`touch .rabbit/.runtime/scope-bypass-once`).

### Working on rabbit-self

Standalone mode: `cd <rabbit-clone>; claude`. No `.rabbit/` in ancestry,
so rabbit operates on `$cwd` as the repo being edited. Today's behaviour;
no change.

---

## Explicitly out of scope for the user-interfacer cycle

| Item | Why deferred |
|---|---|
| `tdd-subagent` on user code | User says TDD might not apply; their test suite, their rules. Bring back only if real demand emerges. |
| B/B system on user projects | User keeps GitHub Issues or whatever they already have. Rabbit does not re-invent issue tracking. |
| GitHub Issues integration | Separate backlog item; valuable but orthogonal to this cycle. |
| Auto-discovery of feature boundaries | Brownfield wizard belongs to a later cycle. This cycle: user invokes `rabbit-feature-new` when ready. |
| Ship-it (git commit + push) automation | User commits via their normal git workflow. Removing this also removes the "TEST-GREEN gate" question entirely. |
| Multi-version rabbit runtime in one process | Per-project pinning already makes this unnecessary. |
| Cross-project dependency management | Out of scope. |
| Activity log / project-history recap | No clear demand. |
| Central project registry | Filesystem presence of `.rabbit/` is the only registration. |

---

## Deliverables (concrete)

1. **Bootstrap docs** (`docs/install.md` in rabbit-self) — the 4-step
   install ritual: clone, drop embedded `.git`, commit, `cd .rabbit &&
   claude`.
2. **`.rabbit/README.md`** — auto-generated on bootstrap; carries the
   killer story + 3-line "what to do next" + link to upstream docs.
3. **`.rabbit/CLAUDE.md`** for plugin mode — loads policy block, names the
   user-project boundary, points at README.
4. **Mode detection** — SessionStart hook that writes
   `.rabbit/.runtime/mode` (`plugin` or `standalone`) for downstream
   tools.
5. **`rabbit-feature-new` enhancement** — accepts `<name>
   <path-glob>...` in plugin mode; validates non-overlap; scaffolds
   `feature.json` + seeded `spec.md` + placeholder `contract.md`; updates
   `project-map.json`.
6. **Spec-seeding subagent** — read-only default-model agent that drafts
   `spec.md` from matched paths.
7. **`project-map.json`** — schema_version 1.0.0; `features: {<name>:
   {paths, feature_dir}}`.
8. **Scope-guard plugin-mode logic** — reads `project-map.json`; blocks
   edits to declared-feature paths without an active feature-touch scope
   marker; emits the structured error message; consumes
   `.rabbit/.runtime/scope-bypass-once` on use.
9. **Meta-contract** (new top-level contract) — declares project
   signature, required paths, commit policy, per-version migration script
   convention. Single source of truth for "what is a rabbit-managed
   project."
10. **Tests** — behavioural tests for: mode detection, feature-new path
    validation + non-overlap, scope-guard block + bypass-once consumption,
    spec seeding produces non-empty output for a sample input tree.

---

## Lifecycle

- **Owner:** rabbit-workflow team.
- **Version of this design:** 0.2.0.
- **Supersedes:** `2026-05-18-rabbit-user-project-plugin-architecture-design.md` (0.1.0).
- **Deprecation criterion:** Superseded when (a) the user-interfacer
  cycle ships and is replaced by a `user-interfacer-as-built.md`, or
  (b) measured user adoption shows the lean-wedge thesis is wrong and a
  fuller install (TDD/B/B on day 1) wins.

---

## Open implementation questions (for the writing-plans phase)

These are not architectural concerns but will need decision in the
implementation plan:

1. Exact path layout inside `.rabbit/.claude/` vs today's structure — does
   anything need to change, or does pure vendoring of today's tree work?
2. The bootstrap script — one-line shell command, or rabbit ships a
   `bootstrap.sh`?
3. Mode-detection hook implementation — pure shell, or Python via the
   existing dispatcher pattern?
4. Glob matching library for `project-map.json` path resolution — stdlib
   `fnmatch`/`pathlib` or `pathspec` (gitignore-style)?
5. Spec-seeding subagent prompt — where does its template live, what slots
   does it carry, how is it dispatched (existing `build-prompt.py` flow)?
6. Meta-contract version-bump policy — additive-only, or stricter?
