# Installing Rabbit into a Project

Rabbit installs as a per-project plugin at `<your-project>/.rabbit/`. The install is pure vendoring — `.rabbit/` is fully committed to your project's repo, no submodules, no embedded `.git` inside it.

## Install (one-liner)

From your project root:

```bash
curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
```

This downloads the latest rabbit, copies the runtime subset into `./.rabbit/`, and prints the next steps. Then commit it:

```bash
git add .rabbit/
git commit -m "install rabbit"
```

That's it. `.rabbit/` is now a vendored part of your repo, version-pinned by the commit you just made.

**Requirements:** `python3`, `curl`, `tar`. No external Python dependencies.

## Start a rabbit session

```bash
cd .rabbit/ && claude
```

This enters rabbit mode: Claude reads the policy block from `.rabbit/CLAUDE.md` on session start, scope-guard protects the rabbit runtime, and you can edit any file in your project at `../`.

When you launch `claude` from anywhere else in your project (or anywhere outside a rabbit install), you get **plain Claude Code** — no policy block, no scope-guard. The directory you launch from is the mode switch.

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
- Scope-guard blocks unsanctioned edits to `../src/auth/**` (prevents accidental drift)
- Claude reads `auth/spec.md` for context every session
- The seeder draft survives across sessions — never re-explain auth context

## Quick override for one-off edits

When scope-guard blocks an edit and you want to make a single change without ceremony:

```bash
touch .rabbit/.runtime/scope-bypass-once
```

The marker is consumed (deleted) on the next edit — single-use only. Use sparingly; the bypass exists for quick fixes, not routine work.

## Sharing across collaborators

Because `.rabbit/` is fully committed, `git clone <your-project>` gives every collaborator a complete, version-pinned, rabbit-enabled checkout. No per-developer install step. The rabbit version IS the file content in `.rabbit/`; no version skew between collaborators.

## Updating rabbit

To pull the latest rabbit into your existing install:

```bash
rm -rf .rabbit/
curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
git add .rabbit/
git commit -m "chore(rabbit): update to latest"
```

A first-class `/rabbit-update` skill is on the roadmap; until then, the re-install snippet above is the contract.

## Pinning to a specific version

Override the default `main` ref via env vars:

```bash
RABBIT_REF=v1.0.0 curl -sSL https://raw.githubusercontent.com/changyu87/rabbit-workflow/main/install.sh | bash
```

`RABBIT_REF` accepts any branch, tag, or commit SHA. `RABBIT_REPO` overrides the repo (default `changyu87/rabbit-workflow`).
