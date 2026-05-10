---
feature: rabbit-cage
version: 1.0.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native feature-container mechanism that subsumes this role
status: active
---

# rabbit-cage — Spec

## Purpose

rabbit-cage owns the Claude Code surface layer of the rabbit workflow, exposing all feature content to Claude Code via symlinks.

## Surface

- `.claude/agents/` — symlink to `rabbit-cage/agents/`
- `.claude/commands/` — symlink to `rabbit-cage/commands/`
- `.claude/hooks/` — symlink to `rabbit-cage/hooks/`
- `.claude/skills/` — symlink to `rabbit-cage/skills/`
- `.claude/settings.json` — symlink to `rabbit-cage/settings.json`
- `.claude/policy/` — symlink to `.claude/features/policy/`
- `.claude/contract/` — symlink to `.claude/features/contract/`
- `CLAUDE.md` — symlink to `rabbit-cage/CLAUDE.md`
- `README.md` — symlink to `rabbit-cage/README.md`
- `install.sh` — symlink to `rabbit-cage/install.sh`

## Invariants

1. `.claude/agents` is a symlink pointing to `.claude/features/rabbit-cage/agents`.
2. `.claude/commands` is a symlink pointing to `.claude/features/rabbit-cage/commands`.
3. `.claude/hooks` is a symlink pointing to `.claude/features/rabbit-cage/hooks`.
4. `.claude/skills` is a symlink pointing to `.claude/features/rabbit-cage/skills`.
5. `.claude/settings.json` is a symlink pointing to `.claude/features/rabbit-cage/settings.json`.
6. `.claude/policy` is a symlink pointing to `.claude/features/policy`.
7. `.claude/contract` is a symlink pointing to `.claude/features/contract`.
8. `CLAUDE.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/CLAUDE.md`.
9. `README.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/README.md`.
10. `install.sh` at repo root is a symlink pointing to `.claude/features/rabbit-cage/install.sh`.
11. `CLAUDE.md` contains `@`-imports sourcing files from `.claude/policy/`.

## Out of Scope

- Content authored by other features — rabbit-cage wires their surface, not their content.
- `settings.local.json` — user-local overrides; never written by rabbit-cage.
- Scripts: rabbit-cage owns no runtime scripts beyond `install.sh` and those registered in its contract.
