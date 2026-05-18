# Rabbit User Project Plugin Architecture — Design

**Status:** Draft
**Date:** 2026-05-18
**Owner:** rabbit-self
**Version (of this design):** 0.1.0

---

## Goal

Extend rabbit to manage user projects — not just self-evolve. A user should
be able to install rabbit into any of their projects (greenfield or
brownfield), use rabbit's TDD discipline and contract machinery on that
project's code, and ship work via the user's existing git workflow.

## Motivation

Today rabbit's machinery (rabbit-feature-touch, tdd-subagent, rabbit-spec,
rabbit-file, the scope-guard, the contract system) is wired to rabbit's
own `.claude/features/` directory. There is no path for a user to apply
the same discipline to their own codebase.

The current `/rabbit-project` command scaffolds a `project-<name>/` folder
inside rabbit's tree but does not extend the TDD or scope-guard machinery
to user code; the rest of rabbit ignores it.

## Architectural choices (made during brainstorming, 2026-05-18)

These are the load-bearing decisions; everything else follows from them.

### 1. Per-project plugin model

Rabbit installs as a plugin **inside each user project** at
`<user-project>/.rabbit/`. There is no central rabbit installation that
manages multiple projects.

- **1-1 rule:** one rabbit process targets one project at a time.
- **Parallel work:** multiple terminals, each in a different project's
  `.rabbit/`, each running its own rabbit. The OS provides the
  parallelism; rabbit makes no claim to multi-project awareness.
- **No `switch` command, no central registry.** The filesystem is the
  registry. To switch projects, exit and re-launch in a different
  `.rabbit/`. The 1-1 rule is enforced by process boundaries, not by
  in-rabbit state.

### 2. `.rabbit/` is fully committed to the user's repo

`.rabbit/` is **pure vendored** — no embedded `.git` inside it. The user's
outer repo tracks all files in `.rabbit/` as normal files. An internal
`.gitignore` inside `.rabbit/` excludes ephemerals (locks, scope markers,
scratch).

This guarantees:

- **Reproducibility.** `git clone <user-repo>` gives a complete,
  version-pinned, rabbit-enabled checkout with no bootstrap step.
- **No version skew between collaborators.** The rabbit version IS the
  file content; everyone gets the same.
- **Spec travel.** Every commit that touches code also commits any
  spec/registry/items changes. Drift is impossible.
- **Multi-user coordination via git.** Concurrent contract edits surface
  as merge conflicts at push time. (Git arbitrates between people;
  file locks arbitrate between same-machine processes.)

### 3. Co-located bookkeeping inside `.rabbit/`

The per-project bookkeeping — specs, features registry, project-map,
items — lives inside `.rabbit/rabbit-project/`, alongside the rabbit
runtime in `.rabbit/.claude/`. Both committed.

```
<user-project>/                       (user's github repo)
├── src/...                           (user's source code)
├── .gitignore                        (user's; does NOT mention .rabbit/)
└── .rabbit/                          (fully committed, vendored)
    ├── .gitignore                    (rabbit-owned; ignores ephemerals)
    ├── .claude/                      (rabbit runtime — skills, hooks, schemas)
    ├── .runtime/                     (ephemerals — locks, scope markers, scratch; gitignored)
    └── rabbit-project/               (bookkeeping — committed)
        ├── project-map.json
        ├── features/registry.json
        ├── features/<name>/spec.md
        ├── features/<name>/state.json
        └── items/{bugs,backlog}/
```

### 4. Meta-contract owns the structure

A new top-level contract — the **meta-contract** — declares what makes a
directory a rabbit-managed project. It is the only thing rabbit needs to
know natively; everything else is derived by validation.

Meta-contract fields:

- **Project signature** — `.rabbit/` exists in the directory ancestry of
  cwd. Detection is filesystem-walk; no registry lookup.
- **Required files and their fixed locations** — enumerated in the
  meta-contract; no per-project configurability. (Decided: simpler,
  enforceable, no path-resolution logic.)
- **Per-path commit policy** — declares which paths inside `.rabbit/` are
  gitignored (ephemerals) vs committed (specs, registry, items, runtime).
  Ships the internal `.gitignore` so the user does not author it.
- **Per-version migration scripts** — each rabbit version ships
  `migrations/<from>-to-<to>.py` (or equivalent). Run as part of
  post-sync check on update. Migrations are additive by default,
  per `spec-rules.md` section 3.
- **Owner and version** — rabbit-self owns the meta-contract;
  meta-contract carries its own semver version; bumps follow the
  contract-version rules already in `spec-rules.md`.

### 5. The standalone-rabbit-self case

When the user is developing rabbit-self (the rabbit repo itself), there is
no `.rabbit/` ancestor; cwd IS rabbit. Detection rule:

- `.rabbit/` exists in ancestry → **plugin mode** (operate on the user
  project at the `.rabbit/` parent).
- No `.rabbit/` in ancestry → **standalone mode** (operate on `$cwd` as
  the rabbit being edited; this is today's behavior).

Same machinery, two modes, disambiguated by filesystem detection at
session start.

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

### Greenfield (new project, new rabbit install)

1. User runs bootstrap (above) in a fresh or existing empty repo.
2. First session: rabbit instantiates meta-contract files from greenfield
   template (empty `features/registry.json`, default `project-map.json`).
3. User starts adding features via the existing `rabbit-feature-touch`
   flow, now operating on user source files at `$cwd/..`.

### Brownfield (existing project, new to rabbit)

1. User runs bootstrap in their existing repo with code.
2. First session: rabbit instantiates the same meta-contract files
   (empty registry).
3. **No auto-discovery of feature boundaries in v1.** User maps existing
   source paths to feature names organically as they touch code.
   (Auto-discovery is deferred.)

### Already-rabbit-touched project (clone existing)

1. User does `git clone <user-repo>` — `.rabbit/` arrives complete.
2. `cd .rabbit && claude` — ready to work, version-pinned, spec history
   intact. No install step.

### TDD lifecycle (unchanged in shape)

`rabbit-feature-touch` runs the existing SPEC-READ → HUMAN-APPROVAL →
LOCK → TEST-WRITE → TEST-RED → IMPLEMENT → CODE-REVIEW → TEST-GREEN →
UNLOCK state machine. The only change: test commands and source paths
target the user project (parent of `.rabbit/`), not rabbit's own
`.claude/features/`.

`tdd-subagent` reads the project's test command from `project-map.json`
(new field). Defaults provided per common toolchains; user can override.

### Ship a feature

1. User: "ship it."
2. Rabbit verifies the feature is at TDD step TEST-GREEN; refuses
   otherwise (don't ship un-green code).
3. Rabbit `git add` user source files + spec changes + state transitions.
4. Rabbit `git commit` with a meaningful message derived from feature
   spec and state.
5. Rabbit `git push` to the current branch's upstream.

Rabbit operates on whatever branch is checked out. It does not impose a
branch model; PRs, releases, tagging are user's call.

### Self-update

1. On session start, rabbit checks upstream for a newer version (compare
   pinned version in `.rabbit/` vs upstream tag/SHA).
2. If newer, banner: "newer version available, update?"
3. User approves → update skill (TBD: extend `/rabbit-config` or new
   `/rabbit-update`) runs:
   - Fetch latest rabbit to temp directory.
   - Compute diff vs current `.rabbit/`, excluding `rabbit-project/`
     (user-owned) and ephemerals (gitignored).
   - Apply changes in place.
   - Run per-version migration scripts (post-sync check).
4. **Pass:** rabbit makes an explicit commit:
   `chore(rabbit): update to <version>`. User's next code commit is
   separate. (Decided: explicit commit, not piggyback, for bisectability.)
5. **Fail:** revert all changes in `.rabbit/`, report what failed. The
   user's working tree is unchanged.

### Working on rabbit-self

Standalone mode: `cd <rabbit-clone>; claude`. No `.rabbit/` in ancestry,
so rabbit operates on `$cwd` as the repo being edited. This is today's
behavior; no change required.

## Concurrency model

| Layer | Mechanism |
|---|---|
| Multiple terminals, different projects | OS process isolation; nothing rabbit-specific |
| Multiple terminals, same project (one machine) | File locks on contract files inside `.rabbit/rabbit-project/`; standard `flock` pattern. Same-project concurrent rabbits allowed with a warning. |
| Multiple users, same project (different machines) | Git's job. Concurrent contract edits surface as merge conflicts at push time. Rabbit does not invent distributed locking. |
| Stale lock cleanup | Lock files carry PID + hostname; subsequent rabbit checks if holder is alive and reclaims if dead. Standard pattern, implementation deferred to v1 build. |

## Updates and migrations

Each rabbit version owns the migration from its predecessor:

- `migrations/0.1.0-to-0.2.0.py` (etc.) — runs on update.
- Validates contract instances against the new schema.
- Performs additive migrations in place.
- On failure: meta-contract guarantees the entire update reverts; the
  user's `.rabbit/` is restored to pre-update state.

The combination of per-project version pinning + on-update migration +
revert-on-failure means: **one installed rabbit version per project, no
runtime needs to support multiple versions in one process**. The
"harder, not easier" version-pinning concern raised during brainstorming
dissolves under this model.

## What rabbit does NOT do (out of scope)

- **Impose a branch model** on the user project. User's git workflow is
  untouched outside of bootstrap, ship-it, and update commits.
- **Push or pull user code** outside the three named operations
  (bootstrap clones rabbit into `.rabbit/`; ship-it commits + pushes;
  update commits the rabbit version bump).
- **Cross-project dependency management.** Each project is fully
  isolated. If project A's code depends on project B's code, that is
  the user's concern, handled outside rabbit.
- **Multi-version rabbit runtime support in one process.** Per-project
  pinning makes this unnecessary; the value of supporting it is too low
  for the complexity.
- **Submodule-based vendoring.** Considered and rejected during
  brainstorming in favor of pure file vendoring (simpler UX, no
  submodule incantations for the user).
- **Auto-discovery of feature boundaries in brownfield projects** (v1).
  Deferred to a possible v2.
- **Activity log and project-history recap** (v1). Deferred. The
  contract state at any time gives "current state"; "what changed since
  last time" can be added later if real demand emerges.
- **A central project registry.** Not needed in this model — filesystem
  presence of `.rabbit/` is the only registration.

## Deferred items (to be designed later or as v2)

| Item | Reason for deferral |
|---|---|
| Activity log shape (events, retention) | No clear demand; spec recap can be derived from contracts on demand |
| Brownfield auto-discovery of features | Sophisticated; not blocking v1 |
| Stale lock cleanup details | Standard pattern; implementation detail, not architectural |
| Multi-user coordination beyond git | Git is sufficient for v1 |
| Update skill name (`/rabbit-config update` vs `/rabbit-update`) | Bikesheddable; decide during build |
| Default test commands per toolchain | Build-time concern; ship reasonable defaults, allow override |

## Open implementation questions (for the writing-plans phase)

These are not architectural concerns but will need to be decided when
writing the implementation plan:

1. Exact path layout inside `.rabbit/.claude/` vs today's structure.
2. Default test-command field name in `project-map.json` and
   precedence rules with user override.
3. The bootstrap script: is it a one-line shell command, or does rabbit
   ship a `bootstrap.sh` to be `curl`'d?
4. How the session-start version-check works (file timestamp? cached
   upstream fetch? on-demand?).
5. Migration script discovery — directory scan or manifest?

## Lifecycle

- **Owner:** rabbit-self team.
- **Version of this design:** 0.1.0.
- **Deprecation criterion:** Superseded when (a) the v1 implementation
  lands and replaces this design with a `v1-as-built.md`, or (b) a
  fundamentally different model is chosen (e.g., move away from
  per-project plugin).

## Brainstorming history (key decision points)

For traceability, the architectural choices above were reached by
sequential pruning during a 2026-05-18 brainstorming session. Key
decisions and what they replaced:

1. **Venv-style isolation** (early proposal) → rejected in favor of
   contract-driven structure (avoid override/precedence complexity).
2. **Central rabbit + registry + `switch` command** (intermediate model)
   → rejected in favor of per-project plugin (filesystem replaces
   registry; process boundaries replace `switch`).
3. **`.rabbit/` gitignored, specs live elsewhere** (intermediate) →
   rejected in favor of fully committed `.rabbit/` (specs travel with
   code; reproducibility; no bootstrap on clone).
4. **Submodule for `.rabbit/`** (considered) → rejected in favor of
   pure vendoring (no submodule UX pain).
5. **Update commit piggybacks on next code commit** (considered) →
   rejected in favor of explicit `chore(rabbit): update to X` commit
   (bisectability).
6. **Switch-mid-TDD allowed with suspend** (considered) → moot under
   per-project model (no switch command), but the underlying rule
   "refuse to drop TDD state implicitly" survives: rabbit refuses to
   exit cleanly with unreleased locks; user must commit or abandon.
