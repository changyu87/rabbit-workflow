# root-management

> Source of truth: [`feature.json`](./feature.json).
> Canonical files live under `artifacts/`. Root entries are symlinks.

## Purpose

Own the three root-level files that users and Claude Code interact with
directly: `install.sh`, `CLAUDE.md`, and `README.md`. Moving canonical
content into this feature directory lets the scope-guard enforce that
these files are only edited by an authorized breeder dispatch.

Root symlinks:
- `install.sh -> .claude/features/root-management/artifacts/install.sh`
- `CLAUDE.md  -> .claude/features/root-management/artifacts/CLAUDE.md`
- `README.md  -> .claude/features/root-management/artifacts/README.md`

## What this feature does NOT define

The contents of these files — those belong to install-distribute,
policy-enforcement, etc. This feature owns only placement and scope protection.

## Tests

`test/run.sh` delegates to `test/test-scope-guard-symlink.sh` (4 cases).
