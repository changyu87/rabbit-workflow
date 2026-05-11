---
feature: rabbit-cage
version: 1.2.0
owner: rabbit-workflow team
template_version: 2.0.0
deprecation_criterion: when Claude Code exposes a native feature-container mechanism that subsumes this role
status: active
---

# rabbit-cage — Spec

## Purpose

rabbit-cage owns the Claude Code surface layer of the rabbit workflow, exposing all feature content to Claude Code via symlinks.

## Surface

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

1. `.claude/commands` is a symlink pointing to `.claude/features/rabbit-cage/commands`.
2. `.claude/hooks` is a symlink pointing to `.claude/features/rabbit-cage/hooks`.
3. `.claude/skills` is a symlink pointing to `.claude/features/rabbit-cage/skills`.
4. `.claude/settings.json` is a symlink pointing to `.claude/features/rabbit-cage/settings.json`.
5. `.claude/policy` is a symlink pointing to `.claude/features/policy`.
6. `.claude/contract` is a symlink pointing to `.claude/features/contract`.
7. `CLAUDE.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/CLAUDE.md`.
8. `README.md` at repo root is a symlink pointing to `.claude/features/rabbit-cage/README.md`.
9. `install.sh` at repo root is a symlink pointing to `.claude/features/rabbit-cage/install.sh`.
10. `CLAUDE.md` contains `@`-imports sourcing files from `.claude/policy/`.

## Out of Scope

- Content authored by other features — rabbit-cage wires their surface, not their content.
- `settings.local.json` — user-local overrides; never written by rabbit-cage.
- Scripts: rabbit-cage owns no runtime scripts beyond `install.sh` and those registered in its contract.

## Visual Styling

Every `systemMessage` emitted by rabbit-cage hooks (`rbt-sync-check.sh`,
`rbt-session-init.sh`, `rbt-refresh.sh`) is wrapped in ANSI deep-green color
codes (`\x1b[32m` … `\x1b[0m`). Markdown is not rendered in `systemMessage`
output; ANSI escape codes are. The deep-green color marks all `[rabbit]`
status/drift/refresh messages as system-emitted (not user-emitted), making
them visually distinguishable in the Claude Code transcript.
