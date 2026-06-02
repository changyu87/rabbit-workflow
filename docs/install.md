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

When you launch `claude` from anywhere else in your project (or anywhere outside a rabbit install), you get **plain Claude Code** — no policy block, no scope-guard. The directory you launch from IS the mode switch.

## Day-1 value: drift-protected Claude (no setup)

Right away, every Claude action obeys philosophy/coding-rules/spec-rules:

- No speculative refactors of code you didn't ask Claude to touch
- No orphan files (Claude reads your project boundary)
- No surprise documentation files Claude generates on its own
- Surgical changes: each edit traces to your request

Just normal Claude, but with constitution. No commands to learn.

## Day-N value: promote a code slice to a feature (opt-in)

When you want spec-as-memory for part of your codebase:

```bash
rabbit-feature-new auth ../src/auth/**
```

Rabbit:
1. Validates the glob (resolves under your project root, doesn't overlap declared features, matches at least one file)
2. Scaffolds bookkeeping at `.rabbit/rabbit-project/features/auth/`
3. Runs a read-only seeder agent that drafts `spec.md` from your existing `auth` code (you review and edit)
4. Registers the mapping in `.rabbit/rabbit-project/project-map.json`

From then on:
- Scope-guard blocks unsanctioned edits to `../src/auth/**` (forces intentional scoped work)
- Claude reads `auth/spec.md` for context every session
- The seeder draft survives across sessions — never re-explain auth context

## When you want to make a quick edit to a declared feature

Two options when scope-guard blocks an edit to declared-feature code:

**Option 1 — Proper path (recommended for real work):**
```
rabbit-feature-touch auth "<your request>"
```
Runs the full spec-aware flow with TDD discipline.

**Option 2 — One-shot override (for quick fixes):**
```bash
touch .rabbit/.runtime/scope-bypass-once
```
The marker is consumed (deleted) on the next edit — single-use only. Use sparingly; the bypass exists for quick fixes, not routine work.

## Sharing across collaborators

Because `.rabbit/` is fully committed, `git clone <your-project>` gives every collaborator a complete, version-pinned, rabbit-enabled checkout. No per-developer bootstrap step. The rabbit version IS the file content in `.rabbit/`; no version skew.

## Updating rabbit

For now, manual update:

```bash
cd .rabbit/
git clone https://github.com/changyu87/rabbit-workflow.git /tmp/rabbit-update
rm -rf /tmp/rabbit-update/.git
rsync -a --delete /tmp/rabbit-update/ .rabbit/
rm -rf /tmp/rabbit-update
cd ..
git add .rabbit
git commit -m "chore(rabbit): update to latest"
```

A first-class `/rabbit-update` skill is on the roadmap; until then, the manual update is the contract.

## Why no bootstrap.sh?

The 5-line snippet above IS the install contract. A shipped `bootstrap.sh` would be another artifact requiring its own version/owner/deprecation criterion, and the snippet is short and clear enough to type or paste directly. The trade-off favors transparency: when you read the install steps you know exactly what lands on your filesystem.
